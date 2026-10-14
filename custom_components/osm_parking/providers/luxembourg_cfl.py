"""CFL Luxembourg official Park & Ride list/details API.

The JSON details publish exact free-space counts but no producer measurement
timestamp. Counts are therefore deliberately classified as REPORTED, not live.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

LIST_URL = "https://pr-mobile-a.cfl.lu/OpenData/ParkAndRide/"
DETAIL_URL = "https://pr-mobile-a.cfl.lu/OpenData/ParkAndRide/{id}"
PROVIDER_NAME = "CFL Park & Ride Open Data"
PROVIDER_URL = "https://data.public.lu/en/datasets/liste-des-p-r-cfl/"


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        if math.isfinite(number) and number >= 0 and number.is_integer():
            return int(number)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _coords(raw: Any) -> tuple[float, float] | None:
    if not isinstance(raw, dict):
        return None
    point = raw.get("wgS84Coordinate")
    if not isinstance(point, dict):
        return None
    try:
        lat = float(point["latitude"])
        lon = float(point["longitude"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and 49.3 <= lat <= 50.3
        and 5.5 <= lon <= 6.7
    ):
        return None
    return lat, lon


def _address(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("address")
    if not isinstance(value, dict):
        return None
    parts = [
        str(value.get(key)).strip()
        for key in ("streetAndNumber", "zipCode", "city")
        if value.get(key) not in (None, "")
    ]
    return ", ".join(parts) if parts else None


class CflParkAndRideProvider:
    uid = "luxembourg_cfl_pr"
    name = PROVIDER_NAME
    fetch_timeout = 25

    def applies(self, lat: float, lon: float) -> bool:
        return 49.30 <= lat <= 50.20 and 5.55 <= lon <= 6.65

    async def _json(
        self,
        session: ClientSession,
        url: str,
    ) -> Any:
        try:
            async with session.get(
                url,
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.7.0",
                },
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        payload = await self._json(session, LIST_URL)
        if not isinstance(payload, list) or len(payload) > 500:
            raise RuntimeError(f"{PROVIDER_NAME}: invalid P+R list")

        nearby: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            point = _coords(row)
            if point is None:
                continue
            if (
                haversine_m(lat, lon, point[0], point[1])
                <= radius_m
            ):
                nearby.append(row)

        async def detail(row: dict[str, Any]):
            parking_id = row.get("id")
            if parking_id in (None, ""):
                return row, None
            try:
                value = await self._json(
                    session,
                    DETAIL_URL.format(id=str(parking_id)),
                )
                return row, value if isinstance(value, dict) else None
            except RuntimeError:
                # A failing details endpoint must not hide the static site.
                return row, None

        details = await asyncio.gather(
            *(detail(row) for row in nearby)
        )
        checked_at = datetime.now(UTC).isoformat()
        suggestions = [
            item
            for row, value in details
            if (
                item := self._normalize(
                    value or row,
                    lat,
                    lon,
                    radius_m,
                    checked_at if value is not None else None,
                )
            ) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        raw: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
        checked_at: str | None,
    ) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        parking_id = raw.get("id")
        point = _coords(raw)
        if parking_id in (None, "") or point is None:
            return None
        lat, lon = point
        distance = round(
            haversine_m(
                destination_lat, destination_lon, lat, lon
            )
        )
        if distance > radius_m:
            return None

        capacity = _count(raw.get("totalCapacity"))
        result: dict[str, Any] = {
            "provider": "luxembourg_cfl_pr",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"cfl-pr:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(raw.get("name") or parking_id).strip(),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "park_and_ride",
            "parking_type": "park_and_ride",
            "fee": "unknown",
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "CFL Open Data",
        }
        address = _address(raw)
        if address:
            result["address"] = address
        if capacity is not None:
            result["capacity"] = capacity

        for source, target in (
            ("totalPMRCapacity", "accessible_capacity"),
            ("totalECarCapacity", "ev_capacity"),
        ):
            count = _count(raw.get(source))
            if count is not None:
                result[target] = count

        opening = raw.get("openingHours")
        if isinstance(opening, str) and opening.strip():
            result["opening_hours"] = opening.strip()
        access = raw.get("typeOfAccess")
        if isinstance(access, str) and access.strip():
            result["access_description"] = access.strip()

        free = _count(raw.get("currentTotalFreeSpaces"))
        if (
            checked_at is not None
            and free is not None
            and (capacity is None or free <= capacity)
        ):
            result["availability_kind"] = "reported"
            result["availability_freshness"] = "unverified"
            result["free_capacity"] = free
            result["availability_checked_at"] = checked_at
            if capacity is not None:
                result["occupied_capacity"] = capacity - free

            accessible_free = _count(
                raw.get("currentPMRFreeSpaces")
            )
            ev_free = _count(raw.get("currentECarFreeSpaces"))
            if (
                accessible_free is not None
                and (
                    result.get("accessible_capacity") is None
                    or accessible_free
                    <= result["accessible_capacity"]
                )
            ):
                result["accessible_free_capacity"] = accessible_free
            if (
                ev_free is not None
                and (
                    result.get("ev_capacity") is None
                    or ev_free <= result["ev_capacity"]
                )
            ):
                result["ev_free_capacity"] = ev_free
        return result
