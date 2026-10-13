"""Official Istanbul Metropolitan Municipality (İBB / İSPARK) parking feed.

The public Park list returns current-looking counts without source measurement
timestamps. Numbers are clearly labelled REPORTED, never verified realtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://api.ibb.gov.tr/ispark/Park"
PROVIDER_NAME = "İBB / İSPARK"
PROVIDER_URL = "https://data.ibb.gov.tr/dataset/ispark-otopark-bilgileri"


def _count(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        number = float(raw)
        if math.isfinite(number) and number >= 0 and number.is_integer():
            return int(number)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


class IstanbulIsparkProvider:
    """İSPARK parking places, occupancy snapshots and working hours."""

    uid = "istanbul_ispark"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        return 40.70 <= lat <= 41.70 and 27.50 <= lon <= 30.15

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        try:
            async with session.get(
                ENDPOINT,
                timeout=25,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.0.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        records = payload.get("value") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid parking response")

        checked_at = datetime.now(UTC).isoformat()
        suggestions = [
            item for row in records
            if (item := self._normalize(row, lat, lon, radius_m, checked_at)) is not None
        ]
        # A new successful fetch provides a new observation, not a verified
        # upstream measurement timestamp. Poll only when facilities are nearby.
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        row: Any, destination_lat: float, destination_lon: float,
        radius_m: int, checked_at: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        parking_id = row.get("parkID")
        if parking_id in (None, ""):
            return None
        try:
            lat, lon = float(row["lat"]), float(row["lng"])
        except (KeyError, ValueError, TypeError, OverflowError):
            return None
        if not (
            math.isfinite(lat) and math.isfinite(lon)
            and 40.0 <= lat <= 42.0 and 27.0 <= lon <= 31.0
        ):
            return None
        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_type = str(row.get("parkType") or "").strip()
        parking_type_casefold = parking_type.casefold()
        if "yol üstü" in parking_type_casefold or "yolustu" in parking_type_casefold:
            category = "street"
            facility_type = "on_street"
        elif "kapalı" in parking_type_casefold:
            category = "multi_storey"
            facility_type = "covered"
        elif "açık" in parking_type_casefold:
            category = "open"
            facility_type = "surface"
        else:
            category = "other"
            facility_type = "off_street"

        result: dict[str, Any] = {
            "provider": "ispark",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"ispark:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(row.get("parkName") or "Otopark"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": facility_type,
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "availability_kind": "static",
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "İstanbul Metropolitan Municipality / İSPARK",
        }
        if category == "street":
            # Street segments and discrete bays can share near-identical points.
            result["merge_with_other_sources"] = False
        if row.get("district"):
            result["district"] = str(row["district"])
        if row.get("workHours"):
            result["opening_hours"] = str(row["workHours"])

        capacity = _count(row.get("capacity"))
        free = _count(row.get("emptyCapacity"))
        if capacity is not None:
            result["capacity"] = capacity

        status_raw = row.get("isOpen")
        status = str(status_raw).strip().casefold() if status_raw is not None else ""
        if status in {"0", "false"}:
            result["opening_status"] = "closed"
            return result
        if status in {"1", "true"}:
            result["opening_status"] = "open"

        if free is not None and (capacity is None or free <= capacity):
            result["free_capacity"] = free
            if capacity is not None:
                result["occupied_capacity"] = capacity - free
            result["availability_kind"] = "reported"
            result["availability_freshness"] = "unverified"
            if checked_at:
                result["availability_checked_at"] = checked_at

        return result
