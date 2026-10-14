"""Fintraffic LIIPI official Finland park-and-ride facilities and utilization."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from ..coverage_geometry import load_coverage
from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

FACILITIES_URL = "https://parking.fintraffic.fi/api/v1/facilities.geojson"
UTILIZATIONS_URL = "https://parking.fintraffic.fi/api/v1/utilizations"
PROVIDER_NAME = "Fintraffic LIIPI Park & Ride"
PROVIDER_URL = "https://parking.fintraffic.fi/docs/index.html"
COVERAGE_FILE = "fintraffic_liipi_10km.geojson"
STATIC_CACHE_SECONDS = 12 * 60 * 60
LIVE_MAX_AGE_SECONDS = 10 * 60
MAX_FACILITIES = 2_000
MAX_UTILIZATIONS = 5_000


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


def _fresh_timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        utc = stamp.astimezone(UTC)
        age = (datetime.now(UTC) - utc).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return utc.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _site_point(feature: dict[str, Any]) -> tuple[float, float] | None:
    """Prefer an official entry port, then the published polygon bbox centre."""
    props = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(props, dict) or not isinstance(geometry, dict):
        return None

    ports = props.get("ports")
    if isinstance(ports, list):
        candidates = [
            port
            for port in ports
            if isinstance(port, dict) and port.get("entry") is True
        ] or [port for port in ports if isinstance(port, dict)]
        for port in candidates:
            location = port.get("location")
            coords = (
                location.get("coordinates")
                if isinstance(location, dict)
                else None
            )
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                try:
                    lon = float(coords[0])
                    lat = float(coords[1])
                except (TypeError, ValueError, OverflowError):
                    continue
                if (
                    math.isfinite(lat)
                    and math.isfinite(lon)
                    and 58 <= lat <= 71
                    and 19 <= lon <= 33
                ):
                    return lat, lon

    bbox = geometry.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        bbox = feature.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            west, south, east, north = map(float, bbox[:4])
            lat = (south + north) / 2
            lon = (west + east) / 2
        except (TypeError, ValueError, OverflowError):
            return None
        if (
            math.isfinite(lat)
            and math.isfinite(lon)
            and 58 <= lat <= 71
            and 19 <= lon <= 33
        ):
            return lat, lon
    return None


class FintrafficLiipiProvider:
    uid = "fintraffic_liipi"
    name = PROVIDER_NAME
    fetch_timeout = 25
    coverage_file = COVERAGE_FILE
    coverage_source = "Fintraffic / LIIPI official facility inventory"
    coverage_license = "CC BY 4.0"
    coverage_source_url = (
        "https://parking.fintraffic.fi/api/v1/facilities.geojson?limit=-1"
    )

    def __init__(self) -> None:
        self._facilities: list[dict[str, Any]] | None = None
        self._facilities_at = 0.0
        self._lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return load_coverage(COVERAGE_FILE).contains(lat, lon)

    async def _static_facilities(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        if (
            self._facilities is not None
            and monotonic() - self._facilities_at < STATIC_CACHE_SECONDS
        ):
            return self._facilities
        async with self._lock:
            if (
                self._facilities is not None
                and monotonic() - self._facilities_at < STATIC_CACHE_SECONDS
            ):
                return self._facilities
            try:
                async with session.get(
                    FACILITIES_URL,
                    params={"limit": "-1"},
                    timeout=20,
                    headers={
                        "Accept": "application/geo+json, application/json",
                        "Digitraffic-User": "ha-osm-parking",
                        "User-Agent": "HomeAssistant-OSM-Parking/1.8.0",
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME} facilities: {err}") from err

            features = payload.get("features") if isinstance(payload, dict) else None
            if (
                payload.get("type") != "FeatureCollection"
                or payload.get("hasMore") not in (False, None)
                or not isinstance(features, list)
                or not features
                or len(features) > MAX_FACILITIES
            ):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid/truncated facility inventory")

            facilities = []
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                props = feature.get("properties")
                capacity = (
                    props.get("builtCapacity")
                    if isinstance(props, dict)
                    else None
                )
                if not isinstance(capacity, dict):
                    continue
                if (_count(capacity.get("CAR")) or 0) <= 0:
                    continue
                if _site_point(feature) is None:
                    continue
                facilities.append(feature)

            if len(facilities) < 50:
                raise RuntimeError(f"{PROVIDER_NAME}: too few usable car facilities")

            self._facilities = facilities
            self._facilities_at = monotonic()
            return facilities

    async def _utilizations(
        self,
        session: ClientSession,
    ) -> dict[int, dict[str, Any]]:
        try:
            async with session.get(
                UTILIZATIONS_URL,
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "Digitraffic-User": "ha-osm-parking",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.8.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} utilization: {err}") from err

        if not isinstance(payload, list) or len(payload) > MAX_UTILIZATIONS:
            raise RuntimeError(f"{PROVIDER_NAME}: invalid utilization response")
        result: dict[int, dict[str, Any]] = {}
        for raw in payload:
            if (
                not isinstance(raw, dict)
                or str(raw.get("capacityType") or "").upper() != "CAR"
            ):
                continue
            try:
                facility_id = int(raw["facilityId"])
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            # Prefer park-and-ride utilization when duplicate CAR records exist.
            if (
                facility_id not in result
                or str(raw.get("usage") or "").upper() == "PARK_AND_RIDE"
            ):
                result[facility_id] = raw
        return result

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        static, live = await asyncio.gather(
            self._static_facilities(session),
            self._utilizations(session),
            return_exceptions=True,
        )
        if isinstance(static, BaseException):
            raise static
        # Static facilities remain useful if the utilization endpoint is down.
        current = {} if isinstance(live, BaseException) else live

        suggestions = [
            item
            for feature in static
            if (
                item := self._normalize(
                    feature,
                    current,
                    lat,
                    lon,
                    radius_m,
                )
            ) is not None
        ]
        has_live = any(
            item.get("availability_kind") == "live"
            for item in suggestions
        )
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=120 if suggestions and has_live else None,
        )

    @staticmethod
    def _normalize(
        feature: Any,
        utilizations: dict[int, dict[str, Any]],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(feature, dict):
            return None
        props = feature.get("properties")
        if not isinstance(props, dict):
            return None
        point = _site_point(feature)
        if point is None:
            return None
        lat, lon = point
        distance = round(
            haversine_m(destination_lat, destination_lon, lat, lon)
        )
        if distance > radius_m:
            return None

        try:
            facility_id = int(feature["id"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

        capacity_data = props.get("builtCapacity")
        if not isinstance(capacity_data, dict):
            return None
        capacity = _count(capacity_data.get("CAR"))
        if capacity is None or capacity <= 0:
            return None

        names = props.get("name")
        if isinstance(names, dict):
            name = str(
                names.get("en")
                or names.get("fi")
                or names.get("sv")
                or facility_id
            )
        else:
            name = str(names or facility_id)

        usages = {
            str(value).upper()
            for value in (props.get("usages") or [])
            if isinstance(value, str)
        }
        is_pr = "PARK_AND_RIDE" in usages
        result: dict[str, Any] = {
            "provider": "fintraffic_liipi",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"fintraffic-liipi:{facility_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "park_and_ride" if is_pr else "other",
            "parking_type": "park_and_ride" if is_pr else "car_park",
            "fee": "unknown",
            "access": "unknown",
            "capacity": capacity,
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Fintraffic LIIPI (CC BY 4.0)",
        }

        ev = _count(capacity_data.get("ELECTRIC_CAR"))
        if ev is not None:
            result["ev_capacity"] = ev

        status = str(props.get("status") or "").upper()
        if status in {"INACTIVE", "TEMPORARILY_CLOSED"}:
            result["opening_status"] = "closed"
            return result

        current = utilizations.get(facility_id)
        if not isinstance(current, dict):
            return result
        if str(current.get("capacityType") or "").upper() != "CAR":
            return result

        live_capacity = _count(current.get("capacity"))
        free = _count(current.get("spacesAvailable"))
        updated_at = _fresh_timestamp(current.get("timestamp"))
        open_now = current.get("openNow")
        if open_now is False:
            result["opening_status"] = "closed"
            return result
        effective_capacity = live_capacity if live_capacity is not None else capacity
        if (
            updated_at is not None
            and free is not None
            and effective_capacity is not None
            and free <= effective_capacity
        ):
            result["capacity"] = effective_capacity
            result["free_capacity"] = free
            result["occupied_capacity"] = effective_capacity - free
            result["realtime_updated_at"] = updated_at
            result["availability_kind"] = "live"
            result["availability_freshness"] = "verified"
            result["has_realtime_data"] = True
            result["opening_status"] = "full" if free == 0 else "open"
        return result
