"""Singapore URA Car Park Details + Car Park Availability (official API).

URA supplies SVY21 coordinates, a daily details feed and available-lot counts
every 3-5 minutes. Its availability response has no measurement timestamp:
numbers are REPORTED, never timestamp-verified live. Requires a user's URA
AccessKey, exchanged for a daily token; cached per credential fingerprint.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from ..const import CONF_URA_ACCESS_KEY, CONF_URA_ENABLED
from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url
from .singapore import _svy21_to_wgs84

BASE_URL = "https://eservice.ura.gov.sg/uraDataService"
TOKEN_URL = f"{BASE_URL}/insertNewToken/v1"
DATA_URL = f"{BASE_URL}/invokeUraDS/v1"
PROVIDER_NAME = "Singapore URA Car Park API"
PROVIDER_URL = "https://eservice.ura.gov.sg/maps/api/"
STATIC_CACHE_SECONDS = 12 * 60 * 60
TOKEN_CACHE_SECONDS = 20 * 60 * 60


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if math.isfinite(number) and number >= 0 and number.is_integer():
        return int(number)
    return None


def _coords(record: Any) -> list[tuple[float, float]]:
    if not isinstance(record, dict):
        return []
    shapes = record.get("geometries")
    if not isinstance(shapes, list):
        return []
    results: list[tuple[float, float]] = []
    for shape in shapes:
        if not isinstance(shape, dict):
            continue
        text = shape.get("coordinates")
        if not isinstance(text, str):
            continue
        components = text.split(",")
        if len(components) != 2:
            continue
        try:
            # Official geometries contain SVY21 Easting, Northing (metres).
            easting, northing = float(components[0]), float(components[1])
            if not all(math.isfinite(x) for x in (easting, northing)):
                continue
            lat, lon = _svy21_to_wgs84(northing, easting)
        except (ValueError, TypeError, OverflowError):
            continue
        if math.isfinite(lat) and math.isfinite(lon) and 1.10 <= lat <= 1.52 and 103.55 <= lon <= 104.12:
            results.append((lat, lon))
    return results


class SingaporeUraProvider:
    uid = "singapore_ura"
    name = PROVIDER_NAME
    enabled_option = CONF_URA_ENABLED
    required_options = (CONF_URA_ACCESS_KEY,)

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[float, str]] = {}
        self._details: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
        self._token_lock = asyncio.Lock()
        self._details_lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return 1.15 <= lat <= 1.50 and 103.55 <= lon <= 104.10

    @staticmethod
    def _fingerprint(access_key: str) -> str:
        return hashlib.sha256(access_key.encode("utf-8")).hexdigest()

    async def _token(
        self, session: ClientSession, access_key: str, key_id: str,
    ) -> str:
        cached = self._tokens.get(key_id)
        if cached and monotonic() < cached[0]:
            return cached[1]
        async with self._token_lock:
            cached = self._tokens.get(key_id)
            if cached and monotonic() < cached[0]:
                return cached[1]
            try:
                async with session.get(
                    TOKEN_URL,
                    headers={"AccessKey": access_key, "Accept": "application/json",
                             "User-Agent": "HomeAssistant-OSM-Parking/1.1.0"},
                    timeout=20,
                ) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME} token request: {err}") from err
            token = data.get("Result") if isinstance(data, dict) and data.get("Status") == "Success" else None
            if not isinstance(token, str) or not token.strip():
                raise RuntimeError(f"{PROVIDER_NAME}: unable to obtain daily token")
            self._tokens[key_id] = (monotonic() + TOKEN_CACHE_SECONDS, token)
            return token

    async def _fetch(
        self, session: ClientSession, access_key: str,
        key_id: str, service: str,
    ) -> list[dict[str, Any]]:
        # Refresh an invalid/expired daily token at most once; never log it.
        for attempt in range(2):
            token = await self._token(session, access_key, key_id)
            try:
                async with session.get(
                    DATA_URL,
                    params={"service": service},
                    headers={
                        "AccessKey": access_key, "Token": token,
                        "Accept": "application/json",
                        "User-Agent": "HomeAssistant-OSM-Parking/1.1.0",
                    },
                    timeout=25,
                ) as response:
                    if response.status in (401, 403) and attempt == 0:
                        self._tokens.pop(key_id, None)
                        continue
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME} {service}: {err}") from err

            rows = payload.get("Result") if isinstance(payload, dict) and payload.get("Status") == "Success" else None
            if not isinstance(rows, list):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid {service} response")
            return [item for item in rows if isinstance(item, dict)]
        raise RuntimeError(f"{PROVIDER_NAME}: access token rejected")

    async def _static(
        self, session: ClientSession, access_key: str, key_id: str,
    ) -> dict[str, dict[str, Any]]:
        cached = self._details.get(key_id)
        if cached and monotonic() < cached[0]:
            return cached[1]
        async with self._details_lock:
            cached = self._details.get(key_id)
            if cached and monotonic() < cached[0]:
                return cached[1]
            rows = await self._fetch(session, access_key, key_id, "Car_Park_Details")
            sites = {}
            for record in rows:
                code = str(record.get("ppCode") or "").strip()
                vehicle = str(record.get("vehCat") or "").strip().lower()
                if code and vehicle in ("c", "car") and _coords(record):
                    sites[code] = record
            if not sites:
                raise RuntimeError(f"{PROVIDER_NAME}: empty usable car-park inventory")
            self._details[key_id] = (monotonic() + STATIC_CACHE_SECONDS, sites)
            return sites

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        access_key = str((options or {}).get(CONF_URA_ACCESS_KEY) or "").strip()
        if not access_key:
            return ProviderFetchResult(provider=self.uid, suggestions=[])
        key_id = self._fingerprint(access_key)
        details = await self._static(session, access_key, key_id)
        availability = await self._fetch(
            session, access_key, key_id, "Car_Park_Availability",
        )
        live = {
            str(row.get("carparkNo")): row
            for row in availability
            if str(row.get("lotType") or "").upper() == "C"
            and row.get("carparkNo") not in (None, "")
        }
        checked_at = datetime.now(UTC).isoformat()
        suggestions: list[dict[str, Any]] = []
        # A site in the daily details feed remains visible when the live feed
        # omits it, but without a misleading zero-vacancy count.
        for code, item in details.items():
            normalized = self._normalize(
                item, live.get(code), lat, lon, radius_m, checked_at,
            )
            if normalized is not None:
                suggestions.append(normalized)
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        detail: dict[str, Any],
        availability: dict[str, Any] | None,
        dest_lat: float,
        dest_lon: float,
        radius_m: int,
        checked_at: str | None = None,
    ) -> dict[str, Any] | None:
        code = str(detail.get("ppCode") or "").strip()
        if not code:
            return None
        coordinates = _coords(detail)
        if not coordinates:
            return None
        candidate = min(
            coordinates,
            key=lambda xy: haversine_m(dest_lat, dest_lon, xy[0], xy[1]),
        )
        lat, lon = candidate
        distance = round(haversine_m(dest_lat, dest_lon, lat, lon))
        if distance > radius_m:
            return None

        result: dict[str, Any] = {
            "provider": "singapore_ura",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"sg-ura:{code}",
            "provider_url": PROVIDER_URL,
            "name": str(detail.get("ppName") or code),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "other",
            "parking_type": "ura_public_car_park",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "availability_kind": "static",
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Urban Redevelopment Authority Singapore Open Data",
        }
        capacity = _count(detail.get("parkCapacity"))
        if capacity is not None:
            result["capacity"] = capacity

        rate = str(detail.get("weekdayRate") or "").strip()
        duration = str(detail.get("weekdayMin") or "").strip()
        if rate and duration:
            result["price"] = f"{rate} / {duration} (weekday)"
            if rate.startswith("$") and _count(rate.lstrip("$")) is not None:
                result["fee"] = "yes"

        if availability is not None:
            free = _count(availability.get("lotsAvailable"))
            if free is not None and (capacity is None or free <= capacity):
                result["availability_kind"] = "reported"
                result["availability_freshness"] = "unverified"
                result["free_capacity"] = free
                if capacity is not None:
                    result["occupied_capacity"] = capacity - free
                if checked_at:
                    result["availability_checked_at"] = checked_at
        return result
