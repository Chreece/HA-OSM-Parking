"""Transport for London official car-park Places with optional occupancy."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from ..coverage_geometry import load_coverage
from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

PLACES_URL = "https://api.tfl.gov.uk/Place/Type/CarPark"
OCCUPANCY_URL = "https://api.tfl.gov.uk/Occupancy/CarPark"
PROVIDER_NAME = "Transport for London Car Parks"
PROVIDER_URL = "https://api.tfl.gov.uk/"
COVERAGE_FILE = "tfl_carpark_10km.geojson"
STATIC_CACHE_SECONDS = 12 * 60 * 60
MAX_PLACES = 500
MAX_OCCUPANCY = 500


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


def _props(place: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    values = place.get("additionalProperties")
    if not isinstance(values, list):
        return result
    for raw in values:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        value = raw.get("value")
        if isinstance(key, str) and value not in (None, ""):
            result[key] = str(value)
    return result


class TflCarParkProvider:
    uid = "tfl_carpark"
    name = PROVIDER_NAME
    fetch_timeout = 25
    coverage_file = COVERAGE_FILE
    coverage_source = "Transport for London Unified API Place/Type/CarPark"
    coverage_license = "TfL Open Data terms"
    coverage_source_url = PLACES_URL

    def __init__(self) -> None:
        self._places: list[dict[str, Any]] | None = None
        self._places_at = 0.0
        self._lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return load_coverage(COVERAGE_FILE).contains(lat, lon)

    async def _static_places(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        if (
            self._places is not None
            and monotonic() - self._places_at < STATIC_CACHE_SECONDS
        ):
            return self._places
        async with self._lock:
            if (
                self._places is not None
                and monotonic() - self._places_at < STATIC_CACHE_SECONDS
            ):
                return self._places
            try:
                async with session.get(
                    PLACES_URL,
                    timeout=20,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "HomeAssistant-OSM-Parking/1.8.0",
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME} places: {err}") from err
            if (
                not isinstance(payload, list)
                or len(payload) < 10
                or len(payload) > MAX_PLACES
            ):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid Place inventory")
            places = [
                item
                for item in payload
                if isinstance(item, dict)
                and item.get("id") not in (None, "")
            ]
            if len(places) < 10:
                raise RuntimeError(f"{PROVIDER_NAME}: too few usable Places")
            self._places = places
            self._places_at = monotonic()
            return places

    async def _occupancy(
        self,
        session: ClientSession,
    ) -> dict[str, dict[str, Any]]:
        try:
            async with session.get(
                OCCUPANCY_URL,
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.8.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError):
            # TfL has intermittently returned HTTP 500 from this endpoint.
            # Static authoritative Place data remains useful and must not fail.
            return {}
        if not isinstance(payload, list) or len(payload) > MAX_OCCUPANCY:
            return {}
        result: dict[str, dict[str, Any]] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id") or "")
            if ident:
                result[ident] = item
        return result

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        places = await self._static_places(session)
        nearby = [
            place
            for place in places
            if self._distance(place, lat, lon) <= radius_m
        ]
        if not nearby:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        occupancy = await self._occupancy(session)
        checked_at = datetime.now(UTC).isoformat()
        suggestions = [
            item
            for place in nearby
            if (
                item := self._normalize(
                    place,
                    occupancy.get(str(place.get("id") or "")),
                    lat,
                    lon,
                    radius_m,
                    checked_at,
                )
            ) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            # TfL's occupancy endpoint can fail independently of Places. Retry
            # it without sacrificing the authoritative static car-park list.
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _distance(
        place: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
    ) -> float:
        try:
            lat = float(place["lat"])
            lon = float(place["lon"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return math.inf
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and 49 <= lat <= 53
            and -2 <= lon <= 2
        ):
            return math.inf
        return haversine_m(destination_lat, destination_lon, lat, lon)

    @staticmethod
    def _normalize(
        place: Any,
        occupancy: dict[str, Any] | None,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
        checked_at: str,
    ) -> dict[str, Any] | None:
        if not isinstance(place, dict):
            return None
        try:
            lat = float(place["lat"])
            lon = float(place["lon"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        distance = round(
            haversine_m(destination_lat, destination_lon, lat, lon)
        )
        if (
            not math.isfinite(distance)
            or distance > radius_m
            or not 49 <= lat <= 53
            or not -2 <= lon <= 2
        ):
            return None

        ident = str(place.get("id") or "").strip()
        if not ident:
            return None
        props = _props(place)
        capacity = _count(props.get("NumberOfSpaces"))
        accessible = _count(props.get("NumberOfDisabledBays"))
        station_code = str(props.get("StationAtcoCode") or "").strip()
        is_pr = bool(station_code)

        result: dict[str, Any] = {
            "provider": "tfl_carpark",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"tfl:{ident}",
            "provider_url": str(place.get("url") or PROVIDER_URL),
            "name": str(place.get("commonName") or ident),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "park_and_ride" if is_pr else "other",
            "parking_type": "park_and_ride" if is_pr else "car_park",
            "fee": "unknown",
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Transport for London Open Data",
        }

        if capacity is not None:
            result["capacity"] = capacity
        if accessible is not None:
            result["accessible_capacity"] = accessible

        address = str(
            props.get("Address")
            or props.get("FullAddress")
            or ""
        ).strip()
        if address:
            result["address"] = address
        hours = str(props.get("OpeningHours") or "").strip()
        if hours:
            result["opening_hours"] = hours
        opened = str(props.get("Open") or "").strip().casefold()
        if opened in {"false", "0", "no"}:
            result["opening_status"] = "closed"

        daily = props.get("StandardTariffsCashlessDaily")
        try:
            price = float(daily) if daily is not None else math.nan
        except (TypeError, ValueError, OverflowError):
            price = math.nan
        if math.isfinite(price) and price >= 0:
            result["price"] = f"£{price:.2f} / day"
            result["fee"] = "no" if price == 0 else "yes"

        if result.get("opening_status") == "closed":
            return result
        if not isinstance(occupancy, dict):
            return result

        bays = occupancy.get("bays")
        if not isinstance(bays, list):
            bays = occupancy.get("bay") if isinstance(occupancy.get("bay"), list) else []
        total = 0
        free = 0
        seen = False
        for bay in bays:
            if not isinstance(bay, dict):
                continue
            bay_count = _count(bay.get("bayCount"))
            bay_free = _count(bay.get("free"))
            if bay_count is None or bay_free is None or bay_free > bay_count:
                continue
            total += bay_count
            free += bay_free
            seen = True
        if not seen:
            return result
        effective_capacity = capacity if capacity is not None else total
        if effective_capacity is None or free > effective_capacity:
            return result

        result["capacity"] = effective_capacity
        result["free_capacity"] = free
        result["occupied_capacity"] = effective_capacity - free
        result["availability_kind"] = "reported"
        result["availability_freshness"] = "unverified"
        result["availability_checked_at"] = checked_at
        result["opening_status"] = "full" if free == 0 else "open"
        return result
