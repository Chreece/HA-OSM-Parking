"""Kanton Basel-Stadt official minute-updated parking occupancy."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://data.bs.ch/api/explore/v2.1/catalog/datasets/"
    "100088/records"
)
PROVIDER_NAME = "Kanton Basel-Stadt Parkleitsystem"
PROVIDER_URL = "https://data.bs.ch/explore/dataset/100088/"
LIVE_MAX_AGE_SECONDS = 10 * 60


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


def _fresh_time(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
        if stamp.tzinfo is None:
            return None
        utc = stamp.astimezone(UTC)
        age = (datetime.now(UTC) - utc).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return utc.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return None


class BaselStadtParkingProvider:
    uid = "basel_stadt"
    name = PROVIDER_NAME
    fetch_timeout = 20

    def applies(self, lat: float, lon: float) -> bool:
        return 47.42 <= lat <= 47.68 and 7.42 <= lon <= 7.78

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
                params={
                    "limit": "100",
                    "timezone": "Europe/Zurich",
                },
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.7.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        rows = payload.get("results") if isinstance(payload, dict) else None
        total_count = payload.get("total_count") if isinstance(payload, dict) else None
        if (
            not isinstance(rows, list)
            or len(rows) > 100
            or (
                isinstance(total_count, int)
                and total_count > len(rows)
            )
        ):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid/truncated inventory")

        suggestions = [
            item
            for row in rows
            if (
                item := self._normalize(
                    row, lat, lon, radius_m
                )
            ) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        raw: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        point = raw.get("geo_point_2d")
        if isinstance(point, dict):
            try:
                lat = float(point["lat"])
                lon = float(point["lon"])
            except (KeyError, TypeError, ValueError, OverflowError):
                return None
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                lat = float(point[0])
                lon = float(point[1])
            except (TypeError, ValueError, OverflowError):
                return None
        else:
            return None
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and 47.3 <= lat <= 47.8
            and 7.3 <= lon <= 7.9
        ):
            return None
        distance = round(
            haversine_m(
                destination_lat, destination_lon, lat, lon
            )
        )
        if distance > radius_m:
            return None

        ident = raw.get("id2") or raw.get("id")
        if ident in (None, ""):
            return None
        lot_type = str(raw.get("lot_type") or "").casefold()
        category = (
            "open"
            if "parkplatz" in lot_type
            else "multi_storey"
        )
        result: dict[str, Any] = {
            "provider": "basel_stadt",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"basel:{ident}",
            "provider_url": PROVIDER_URL,
            "name": str(
                raw.get("title")
                or raw.get("name")
                or ident
            ),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": lot_type or "off_street",
            "fee": "unknown",
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": (
                "Kanton Basel-Stadt / Parkhäuser Basel-Stadt (CC BY 4.0)"
            ),
        }
        if raw.get("address"):
            result["address"] = str(raw["address"])
        link = str(raw.get("link") or "")
        if link.startswith("https://"):
            result["provider_url"] = link

        capacity = _count(raw.get("total"))
        free = _count(raw.get("free"))
        if capacity is not None:
            result["capacity"] = capacity

        status = str(raw.get("status") or "").strip().casefold()
        if status in {"geschlossen", "closed", "fermé", "ferme"}:
            result["opening_status"] = "closed"
            return result

        recorded_at = _fresh_time(raw.get("published"))
        if (
            status in {"offen", "open", "ouvert"}
            and recorded_at is not None
            and free is not None
            and capacity is not None
            and free <= capacity
        ):
            result["availability_kind"] = "live"
            result["availability_freshness"] = "verified"
            result["has_realtime_data"] = True
            result["free_capacity"] = free
            result["occupied_capacity"] = capacity - free
            result["realtime_updated_at"] = recorded_at
            result["opening_status"] = "full" if free == 0 else "open"
        return result
