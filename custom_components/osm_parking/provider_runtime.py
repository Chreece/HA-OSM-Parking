"""Isolate provider eligibility, deadlines, payload validation and retry state.

No old occupancy is replayed when a feed fails. Every refresh merges only
successful current responses, so an overlapping healthy source can take over.
Retry state belongs to one config entry, never a different user's API key.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
from time import monotonic
from typing import Any

from .const import CATEGORIES
from .parking_quality import normalize_facility, merge_facilities
from .providers.base import ProviderFetchResult, haversine_m, bounding_box
from .providers.zone_geometry import validated_geometry, intersects_bbox

MAX_RECORDS = 5000
RETRY_SECONDS = (60, 300, 1800, 21600)


@dataclass
class FailureState:
    failures: int = 0
    retry_at: float = 0.0
    reason: str = ''


def clean_result(result: Any, uid: str, lat: float, lon: float, radius: int) -> ProviderFetchResult:
    """Sanitize inside the provider boundary, including per-record failures."""
    if not isinstance(result, ProviderFetchResult) or not isinstance(result.suggestions, list) or not isinstance(result.zones, list):
        raise ValueError('Invalid provider response')
    if len(result.suggestions) > MAX_RECORDS or len(result.zones) > 500:
        raise ValueError('Provider result exceeds safety limit')
    rows, valid_rows = [], 0
    for raw in result.suggestions:
        try:
            item = normalize_facility(raw)
            if item is None:
                continue
            json.dumps(item, allow_nan=False)
            distance = haversine_m(lat, lon, item['latitude'], item['longitude'])
            if not math.isfinite(distance):
                continue
            valid_rows += 1
            if distance > radius:
                continue
            item['distance_m'] = round(distance)
            if item.get('category') not in CATEGORIES:
                item['category'] = 'other'
            if item['availability_kind'] not in ('live', 'reported'):
                for key in ('free_capacity', 'occupied_capacity', 'closed_capacity', 'accessible_free_capacity', 'ev_free_capacity'):
                    item.pop(key, None)
            rows.append(item)
        except Exception:
            # One malformed record must not discard the rest of its source.
            continue
    zones, valid_zones = [], 0
    bbox = bounding_box(lat, lon, radius)
    for raw in result.zones:
        try:
            if not isinstance(raw, dict) or raw.get('type') != 'Feature':
                continue
            props = raw.get('properties')
            if not isinstance(props, dict) or props.get('record_type') != 'zone':
                continue
            geom = validated_geometry(raw.get('geometry'))
            if geom is None:
                continue
            json.dumps(props, allow_nan=False)
            valid_zones += 1
            if intersects_bbox(geom, bbox):
                zones.append({'type': 'Feature', 'geometry': geom, 'properties': dict(props)})
        except Exception:
            continue
    if (result.suggestions or result.zones) and not (valid_rows or valid_zones):
        raise ValueError('No structurally usable records')
    interval = result.live_refresh_seconds
    if interval is not None:
        if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not math.isfinite(interval) or interval <= 0:
            interval = None
        else:
            interval = max(60, min(86400, int(interval)))
    return ProviderFetchResult(uid, rows, interval if rows or zones else None, zones)


class ProviderSupervisor:
    """All failures are source-local; cancellation is deliberately propagated."""

    def __init__(self) -> None:
        self._failures: dict[str, FailureState] = {}
        self.status: dict[str, dict] = {}
        self.errors: dict[str, str] = {}
        self.queried: list[str] = []
        self.retry_seconds: int | None = None

    def _failed(self, uid: str, exc: Exception) -> None:
        state = self._failures.setdefault(uid, FailureState())
        state.failures += 1
        state.reason = type(exc).__name__
        seconds = RETRY_SECONDS[min(state.failures - 1, len(RETRY_SECONDS) - 1)]
        hint = getattr(exc, 'retry_after_seconds', 0)
        if isinstance(hint, (int, float)) and math.isfinite(hint):
            seconds = max(seconds, min(86400, int(hint)))
        state.retry_at = monotonic() + seconds
        self._cooldown(uid, state, 'failed')

    def _cooldown(self, uid: str, state: FailureState, status='cooldown') -> None:
        seconds = max(1, math.ceil(state.retry_at - monotonic()))
        self.status[uid] = {'status': status, 'error_type': state.reason,
                            'retry_after_seconds': seconds, 'consecutive_failures': state.failures}
        self.errors[uid] = f'{state.reason}; retry in {seconds}s'
        self.retry_seconds = min(self.retry_seconds or seconds, seconds)

    async def _one(self, provider: Any, uid: str, session: Any, lat: float,
                   lon: float, radius: int, options: dict) -> ProviderFetchResult | None:
        try:
            budget = getattr(provider, 'fetch_timeout', 30)
            if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget):
                budget = 30
            async with asyncio.timeout(max(0.01, min(45, budget))):
                result = await provider.async_fetch(session, lat, lon, radius, options)
                clean = clean_result(result, uid, lat, lon, radius)
            self._failures.pop(uid, None)
            status = {'status': 'ok' if clean.suggestions or clean.zones else 'no_coverage',
                      'facilities': len(clean.suggestions), 'zones': len(clean.zones)}
            coverage_source = getattr(provider, 'coverage_source', None)
            if coverage_source:
                status['coverage_source'] = str(coverage_source)
                status['coverage_license'] = str(
                    getattr(provider, 'coverage_license', '')
                )
                status['coverage_source_url'] = str(
                    getattr(provider, 'coverage_source_url', '')
                )
            pool = getattr(provider, '_endpoints', None)
            if pool is not None and pool.last_source:
                status['active_endpoint'] = pool.last_source
                status['fallback_used'] = pool.last_source != pool.endpoints[0].url
            self.status[uid] = status
            return clean
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._failed(uid, exc)
            return None

    async def fetch(self, providers: Any, session: Any, lat: float, lon: float,
                    radius: int, options: dict) -> list[ProviderFetchResult]:
        self.status, self.errors, self.queried, self.retry_seconds = {}, {}, [], None
        tasks = []
        seen = set()
        for index, provider in enumerate(providers):
            uid = f'provider_{index}'
            try:
                uid = str(provider.uid)
                if uid in seen:
                    continue
                seen.add(uid)
                if not provider.applies(lat, lon):
                    continue
                flag = getattr(provider, 'enabled_option', None)
                if flag and not options.get(flag, getattr(provider, 'enabled_default', True)):
                    continue
                if any(not str(options.get(key) or '').strip() for key in getattr(provider, 'required_options', ())):
                    continue
                state = self._failures.get(uid)
                if state is not None and state.retry_at > monotonic():
                    self._cooldown(uid, state)
                    continue
                self.queried.append(uid)
                tasks.append(self._one(provider, uid, session, lat, lon, radius, options))
            except Exception as exc:
                state = self._failures.get(uid)
                if state is not None and state.retry_at > monotonic():
                    self._cooldown(uid, state)
                else:
                    self._failed(uid, exc)
        responses = await asyncio.gather(*tasks)
        return [result for result in responses if result is not None]

    def merge(self, current: list[dict], result: ProviderFetchResult) -> list[dict]:
        try:
            return merge_facilities(current, result.suggestions)
        except Exception as exc:
            self._failed(result.provider, exc)
            return current
