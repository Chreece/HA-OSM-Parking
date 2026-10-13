from __future__ import annotations

import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

STATIC_ENDPOINT = "https://data.gov.sg/api/action/datastore_search"
STATIC_DATASET_ID = "d_23f946fa557947f93a8043bbef41dd09"
AVAILABILITY_ENDPOINT = "https://api.data.gov.sg/v1/transport/carpark-availability"
PROVIDER_NAME = "Singapore HDB / data.gov.sg"
PROVIDER_URL = "https://data.gov.sg/datasets/d_ca933a644e55d34fe21f28b8052fac63/view"

_STATIC_CACHE_SECONDS = 24 * 60 * 60

# SVY21 / Singapore TM (EPSG:3414) parameters.
_A = 6_378_137.0
_F = 1 / 298.257223563
_ORIGIN_LAT = 1.366666666666667
_ORIGIN_LON = 103.833333333333
_FALSE_NORTHING = 38_744.572
_FALSE_EASTING = 28_001.642
_K0 = 1.0


def _svy21_to_wgs84(northing: float, easting: float) -> tuple[float, float]:
    """Convert EPSG:3414 SVY21 coordinates to WGS84 latitude/longitude."""
    b = _A * (1 - _F)
    e2 = (2 * _F) - (_F * _F)
    e4 = e2 * e2
    e6 = e4 * e2

    a0 = 1 - (e2 / 4) - (3 * e4 / 64) - (5 * e6 / 256)
    a2 = (3 / 8) * (e2 + (e4 / 4) + (15 * e6 / 128))
    a4 = (15 / 256) * (e4 + (3 * e6 / 4))
    a6 = 35 * e6 / 3072

    def meridional_arc(latitude_deg: float) -> float:
        latitude = math.radians(latitude_deg)
        return _A * (
            a0 * latitude
            - a2 * math.sin(2 * latitude)
            + a4 * math.sin(4 * latitude)
            - a6 * math.sin(6 * latitude)
        )

    n_prime = northing - _FALSE_NORTHING
    m_origin = meridional_arc(_ORIGIN_LAT)
    m_prime = m_origin + (n_prime / _K0)

    n = (_A - b) / (_A + b)
    n2 = n * n
    n3 = n2 * n
    n4 = n2 * n2
    g = (
        _A
        * (1 - n)
        * (1 - n2)
        * (1 + (9 * n2 / 4) + (225 * n4 / 64))
        * (math.pi / 180)
    )
    sigma = (m_prime * math.pi) / (180 * g)

    lat_prime = (
        sigma
        + ((3 * n / 2) - (27 * n3 / 32)) * math.sin(2 * sigma)
        + ((21 * n2 / 16) - (55 * n4 / 32)) * math.sin(4 * sigma)
        + (151 * n3 / 96) * math.sin(6 * sigma)
        + (1097 * n4 / 512) * math.sin(8 * sigma)
    )

    sin_lat = math.sin(lat_prime)
    sin2_lat = sin_lat * sin_lat
    rho = _A * (1 - e2) / math.pow(1 - e2 * sin2_lat, 1.5)
    nu = _A / math.sqrt(1 - e2 * sin2_lat)
    psi = nu / rho

    psi2 = psi * psi
    psi3 = psi2 * psi
    psi4 = psi3 * psi
    t = math.tan(lat_prime)
    t2 = t * t
    t4 = t2 * t2
    t6 = t4 * t2

    e_prime = easting - _FALSE_EASTING
    x = e_prime / (_K0 * nu)
    x2 = x * x
    x3 = x2 * x
    x5 = x3 * x2
    x7 = x5 * x2

    lat_factor = t / (_K0 * rho)
    lat = (
        lat_prime
        - lat_factor * ((e_prime * x) / 2)
        + lat_factor
        * ((e_prime * x3) / 24)
        * ((-4 * psi2) + (9 * psi) * (1 - t2) + (12 * t2))
        - lat_factor
        * ((e_prime * x5) / 720)
        * (
            (8 * psi4) * (11 - 24 * t2)
            - (12 * psi3) * (21 - 71 * t2)
            + (15 * psi2) * (15 - 98 * t2 + 15 * t4)
            + (180 * psi) * (5 * t2 - 3 * t4)
            + 360 * t4
        )
        + lat_factor
        * ((e_prime * x7) / 40320)
        * (1385 - 3633 * t2 + 4095 * t4 + 1575 * t6)
    )

    sec_lat = 1 / math.cos(lat)
    lon = (
        math.radians(_ORIGIN_LON)
        + x * sec_lat
        - ((x3 * sec_lat) / 6) * (psi + 2 * t2)
        + ((x5 * sec_lat) / 120)
        * (
            (-4 * psi3) * (1 - 6 * t2)
            + psi2 * (9 - 68 * t2)
            + 72 * psi * t2
            + 24 * t4
        )
        - ((x7 * sec_lat) / 5040)
        * (61 + 662 * t2 + 1320 * t4 + 720 * t6)
    )

    return math.degrees(lat), math.degrees(lon)


class SingaporeHdbProvider:
    """Singapore HDB parking information + realtime lot availability."""

    uid = "singapore_hdb"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._static_cache: dict[str, dict[str, Any]] = {}
        self._static_loaded_at = 0.0

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside Singapore."""
        return 1.15 <= lat <= 1.50 and 103.55 <= lon <= 104.10

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch and normalize nearby HDB parking with realtime availability."""
        static = await self._async_static_data(session)
        availability = await self._async_availability(session)

        suggestions: list[dict[str, Any]] = []
        for live_item in availability:
            carpark_no = str(live_item.get("carpark_number") or "")
            static_item = static.get(carpark_no)
            if not static_item:
                continue

            normalized = self._normalize(
                static_item,
                live_item,
                lat,
                lon,
                radius_m,
            )
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if suggestions else None,
        )

    async def _async_static_data(
        self,
        session: ClientSession,
    ) -> dict[str, dict[str, Any]]:
        now = monotonic()
        if self._static_cache and now - self._static_loaded_at < _STATIC_CACHE_SECONDS:
            return self._static_cache

        params = {
            "resource_id": STATIC_DATASET_ID,
            "limit": "5000",
        }
        try:
            async with session.get(
                STATIC_ENDPOINT,
                params=params,
                timeout=20,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.4.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} static data: {err}") from err

        records = (
            payload.get("result", {}).get("records")
            if isinstance(payload, dict)
            else None
        )
        if not isinstance(records, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid static response")

        cache: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            carpark_no = str(record.get("car_park_no") or "")
            if not carpark_no:
                continue
            try:
                northing = float(record["y_coord"])
                easting = float(record["x_coord"])
                record_lat, record_lon = _svy21_to_wgs84(northing, easting)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue

            enriched = dict(record)
            enriched["_latitude"] = record_lat
            enriched["_longitude"] = record_lon
            cache[carpark_no] = enriched

        if not cache:
            raise RuntimeError(f"{PROVIDER_NAME}: static dataset was empty")

        self._static_cache = cache
        self._static_loaded_at = now
        return cache

    async def _async_availability(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        try:
            async with session.get(
                AVAILABILITY_ENDPOINT,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.4.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} availability: {err}") from err

        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            raise RuntimeError(f"{PROVIDER_NAME}: invalid availability response")

        carpark_data = items[0].get("carpark_data")
        if not isinstance(carpark_data, list):
            raise RuntimeError(f"{PROVIDER_NAME}: missing carpark_data")
        return [item for item in carpark_data if isinstance(item, dict)]

    @staticmethod
    def _normalize(
        static: dict[str, Any],
        live: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        lat = float(static["_latitude"])
        lon = float(static["_longitude"])
        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        car_lots = None
        for row in live.get("carpark_info") or []:
            if isinstance(row, dict) and str(row.get("lot_type") or "") == "C":
                car_lots = row
                break
        if car_lots is None:
            return None

        carpark_type = str(static.get("car_park_type") or "").upper()
        if "MULTI-STOREY" in carpark_type:
            category = "multi_storey"
        elif "BASEMENT" in carpark_type:
            category = "underground"
        elif "SURFACE" in carpark_type:
            category = "open"
        else:
            category = "other"

        carpark_no = str(static.get("car_park_no") or live.get("carpark_number") or "")
        result: dict[str, Any] = {
            "provider": "singapore_hdb",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"sg-hdb:{carpark_no}",
            "provider_url": PROVIDER_URL,
            "name": str(static.get("address") or carpark_no or "Parking"),
            "address": str(static.get("address") or ""),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": carpark_type.lower() or "unknown",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": True,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        try:
            result["capacity"] = int(car_lots["total_lots"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            result["free_capacity"] = int(car_lots["lots_available"])
        except (KeyError, TypeError, ValueError):
            pass

        if live.get("update_datetime"):
            result["realtime_updated_at"] = str(live["update_datetime"])

        for source, target in (
            ("short_term_parking", "opening_hours"),
            ("free_parking", "free_parking"),
            ("night_parking", "night_parking"),
            ("gantry_height", "max_height"),
        ):
            value = static.get(source)
            if value not in (None, ""):
                result[target] = value

        return result
