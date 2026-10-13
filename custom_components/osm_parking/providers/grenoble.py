"""SMMAG / M Mobilités Grenoble official car parks and live vacancy feed.

The geo catalogue and live availability are separate official resources; live
entries are keyed by the catalogue's id. Missing/stale measurements never mean
zero free spaces. Static catalogue responses are cached for six hours.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

_LOGGER = logging.getLogger(__name__)

CATALOG_URL = "https://data.mobilites-m.fr/api/points/json"
LIVE_URL = "https://data.mobilites-m.fr/api/dyn/parking/json"
PROVIDER_NAME = "SMMAG / M Mobilités Open Data"
PROVIDER_URL = "https://data.metropolegrenoble.fr/visualisation/?id=parkings"
CATALOG_TTL_SECONDS = 6 * 3600
LIVE_MAX_AGE_SECONDS = 10 * 60


def _count(value: Any) -> int | None:
    """Parse actual nonnegative integer counts without rounding or guessing."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return None
    return int(number)


def _fresh_time(value: Any) -> str | None:
    """Check producer Unix time (seconds or milliseconds), not request time."""
    if value is None or isinstance(value, bool):
        return None
    try:
        stamp = float(value)
        if not math.isfinite(stamp):
            return None
        if stamp > 10_000_000_000:
            stamp /= 1000
        recorded = datetime.fromtimestamp(stamp, UTC)
        age = (datetime.now(UTC) - recorded).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return recorded.isoformat()
    except (ValueError, OverflowError, OSError, TypeError):
        return None
    return None


def _fee(value: Any) -> str:
    if isinstance(value, bool):
        return "no" if value else "yes"
    raw = str(value or "").strip().casefold()
    if raw in {"oui", "true", "1", "gratuit"}:
        return "no"
    if raw in {"non", "false", "0", "payant"}:
        return "yes"
    return "unknown"


class GrenobleParkingProvider:
    """The official Grenoble-area static/live join, with cached static data."""

    uid = "grenoble_smmag"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._catalog: list[dict[str, Any]] | None = None
        self._catalog_updated = 0.0
        self._catalog_lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return 44.90 <= lat <= 45.65 and 5.25 <= lon <= 6.35

    async def _fetch_json(
        self, session: ClientSession, url: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with session.get(
                url,
                params=params,
                timeout=20,
                headers={
                    "Accept": "application/json, application/geo+json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.9.0",
                },
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

    async def _catalog_features(
        self, session: ClientSession,
    ) -> list[dict[str, Any]]:
        if (
            self._catalog is not None
            and monotonic() - self._catalog_updated < CATALOG_TTL_SECONDS
        ):
            return self._catalog
        async with self._catalog_lock:
            if (
                self._catalog is not None
                and monotonic() - self._catalog_updated < CATALOG_TTL_SECONDS
            ):
                return self._catalog
            payload = await self._fetch_json(
                session, CATALOG_URL, {"types": "parking"},
            )
            features = payload.get("features") if isinstance(payload, dict) else None
            if not isinstance(features, list):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid GeoJSON catalogue")
            self._catalog = [f for f in features if isinstance(f, dict)]
            self._catalog_updated = monotonic()
            return self._catalog

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        catalogue = await self._catalog_features(session)
        live = await self._fetch_json(session, LIVE_URL)
        if not isinstance(live, dict):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid live parking response")

        suggestions = [
            item for feature in catalogue
            if (
                item := self._normalize(
                    feature, live, lat, lon, radius_m,
                )
            ) is not None
        ]
        # Recheck while relevant sites exist, even if all meters currently lack
        # valid readings; no polling outside the provider's search area.
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=120 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        feature: Any,
        live: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(feature, dict):
            return None
        props, geometry = feature.get("properties"), feature.get("geometry")
        if not isinstance(props, dict) or not isinstance(geometry, dict):
            return None
        if geometry.get("type") != "Point":
            return None
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, (tuple, list)) or len(coordinates) < 2:
            return None
        try:
            lon, lat = float(coordinates[0]), float(coordinates[1])
        except (ValueError, TypeError, OverflowError):
            return None
        if not (
            math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180
        ):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = props.get("id")
        if parking_id in (None, ""):
            return None
        name = str(props.get("nom") or "Parking")
        layout = str(props.get("type_ouvrage") or "").casefold()
        relay_spaces = _count(props.get("nb_pr"))
        if (relay_spaces is not None and relay_spaces > 0) or "relais" in name.casefold():
            category = "park_and_ride"
        elif "souterrain" in layout or "enterr" in layout:
            category = "underground"
        elif "surface" in layout or "enclos" in layout or "plein air" in layout:
            category = "open"
        elif "ouvrage" in layout or "étage" in layout or "etage" in layout:
            category = "multi_storey"
        else:
            category = "other"

        fee = _fee(props.get("gratuit"))
        if fee == "yes" and category != "park_and_ride":
            category = "paid"

        item: dict[str, Any] = {
            "provider": "grenoble",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"grenoble:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": layout or "off_street",
            "fee": fee,
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "M Mobilités / SMMAG (ODbL 1.0)",
        }

        for field, target in (
            ("adresse", "address"),
            ("url", "facility_url"),
        ):
            value = props.get(field)
            if value not in (None, ""):
                if field == "url":
                    if str(value).startswith(("https://", "http://")):
                        item["provider_url"] = str(value)
                else:
                    item[target] = str(value)

        capacity = _count(props.get("nb_places"))
        if capacity is not None:
            item["capacity"] = capacity
        for source, target in (
            ("nb_pmr", "accessible_capacity"),
            ("nb_voitures_electriques", "ev_capacity"),
        ):
            count = _count(props.get(source))
            if count is not None:
                item[target] = count

        tariff = props.get("tarif_1h")
        try:
            amount = float(tariff) if tariff is not None else -1
            if math.isfinite(amount) and amount >= 0:
                item["price"] = f"{amount:.2f} € / 1 h"
        except (TypeError, ValueError):
            pass

        observation = live.get(str(parking_id))
        if not isinstance(observation, dict):
            return item
        recorded_at = _fresh_time(observation.get("time"))
        free = _count(observation.get("nb_places_libres"))
        if (
            recorded_at is not None
            and free is not None
            and (capacity is None or free <= capacity)
        ):
            item["has_realtime_data"] = True
            item["free_capacity"] = free
            item["realtime_updated_at"] = recorded_at
            if capacity is not None:
                item["occupied_capacity"] = capacity - free
            if free == 0:
                item["opening_status"] = "full"
        return item
