"""İzmir Metropolitan Municipality / İZUM public parking API.

The municipal feed carries free + occupied spaces but has no source-side
measurement timestamp. Its values are *reported*, never verified realtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://openapi.izmir.bel.tr/api/ibb/izum/otoparklar"
PROVIDER_NAME = "İzmir Municipality / İZUM"
PROVIDER_URL = "https://acikveri.bizizmir.com/dataset/otopark-doluluk-ve-lokasyon-bilgileri"


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
        if math.isfinite(numeric) and numeric >= 0 and numeric.is_integer():
            return int(numeric)
    except (ValueError, TypeError, OverflowError):
        pass
    return None


class IzmirIzumProvider:
    uid = "izmir_izum"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        return 37.65 <= lat <= 39.0 and 26.45 <= lon <= 28.20

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
                timeout=35,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.0.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if not isinstance(payload, list):
            raise RuntimeError(f"{PROVIDER_NAME}: expected a JSON list")

        checked_at = datetime.now(UTC).isoformat()
        suggestions = [
            item for row in payload
            if (item := self._normalize(row, lat, lon, radius_m, checked_at)) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        row: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
        checked_at: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        parking_id = row.get("ufid")
        if parking_id in (None, ""):
            return None
        try:
            lat = float(row["lat"])
            lon = float(row["lng"])
        except (TypeError, ValueError, KeyError, OverflowError):
            return None
        if not (
            math.isfinite(lat) and math.isfinite(lon)
            and 37.0 <= lat <= 40.0 and 25.5 <= lon <= 29.0
        ):
            return None
        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        is_street = str(row.get("type") or "").casefold() == "onstreet"
        category = "street" if is_street else "other"
        fee_flag = row.get("isPaid")
        fee = (
            "yes" if fee_flag is True else
            "no" if fee_flag is False else "unknown"
        )
        if fee == "yes" and not is_street:
            category = "paid"
        status = str(row.get("status") or "").strip().casefold()

        result: dict[str, Any] = {
            "provider": "izum",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"izum:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(row.get("name") or "Otopark"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": "on_street" if is_street else "off_street",
            "fee": fee,
            "access": "unknown",
            "has_realtime_data": False,
            "availability_kind": "static",
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "İzmir Metropolitan Municipality (CC BY 4.0)",
        }
        if is_street:
            result["merge_with_other_sources"] = False
        if row.get("provider"):
            result["operator"] = str(row["provider"])
        if row.get("address"):
            result["address"] = str(row["address"])
        if row.get("nonstop") is True:
            result["opening_hours"] = "24/7"
        if status in {"closed", "kapalı", "kapali"}:
            result["opening_status"] = "closed"
        elif status in {"opened", "open"}:
            result["opening_status"] = "open"

        occupancy = row.get("occupancy")
        total = occupancy.get("total") if isinstance(occupancy, dict) else None
        if isinstance(total, dict):
            free = _count(total.get("free"))
            occupied = _count(total.get("occupied"))
            if free is not None and occupied is not None:
                result["capacity"] = free + occupied
                if result.get("opening_status") != "closed":
                    result["free_capacity"] = free
                    result["occupied_capacity"] = occupied
                    result["availability_kind"] = "reported"
                    result["availability_freshness"] = "unverified"
                    if checked_at:
                        result["availability_checked_at"] = checked_at

            accessible = occupancy.get("disabled")
            if isinstance(accessible, dict):
                free_accessible = _count(accessible.get("free"))
                occupied_accessible = _count(accessible.get("occupied"))
                if free_accessible is not None and occupied_accessible is not None:
                    result["accessible_capacity"] = free_accessible + occupied_accessible
                    # Accessibility vacancies are still only reported counts.
                    if result["availability_kind"] == "reported":
                        result["accessible_free_capacity"] = free_accessible

        return result
