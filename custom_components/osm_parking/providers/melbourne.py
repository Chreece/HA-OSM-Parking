from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
    "on-street-parking-bay-sensors/records"
)
PROVIDER_NAME = "City of Melbourne Parking Bay Sensors"
PROVIDER_URL = (
    "https://data.melbourne.vic.gov.au/explore/dataset/"
    "on-street-parking-bay-sensors/information/"
)
_LIVE_MAX_AGE_SECONDS = 15 * 60


class MelbourneParkingProvider:
    """Near-real-time City of Melbourne individual parking-bay sensors."""

    uid = "melbourne_bay_sensors"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in central Melbourne."""
        return -38.05 <= lat <= -37.65 and 144.75 <= lon <= 145.20

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby live parking-bay sensor states."""
        where = (
            "within_distance(location, "
            f"geom'POINT({lon:.7f} {lat:.7f})', {radius_m} m)"
        )
        try:
            async with session.get(
                ENDPOINT,
                params={
                    "where": where,
                    "limit": "100",
                    "order_by": (
                        "distance(location, "
                        f"geom'POINT({lon:.7f} {lat:.7f})')"
                    ),
                },
                timeout=15,
                headers={
                    "User-Agent": "HomeAssistant-OSM-Parking/0.5.0"
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")

        suggestions: list[dict[str, Any]] = []
        has_fresh_live = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized = self._normalize(row, lat, lon, radius_m)
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_fresh_live = has_fresh_live or bool(
                normalized.get("has_realtime_data")
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if has_fresh_live else None,
        )

    @staticmethod
    def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
        location = item.get("location")
        if isinstance(location, dict):
            try:
                return float(location["lat"]), float(location["lon"])
            except (KeyError, TypeError, ValueError):
                pass

        if isinstance(location, (list, tuple)) and len(location) >= 2:
            try:
                first = float(location[0])
                second = float(location[1])
            except (TypeError, ValueError):
                return None

            # Melbourne latitude is negative and longitude positive. ODS geo
            # points can be exposed either as [lat, lon] or [lon, lat].
            if -90 <= first <= 90 and 100 <= second <= 180:
                return first, second
            if 100 <= first <= 180 and -90 <= second <= 90:
                return second, first

        return None

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @classmethod
    def _normalize(
        cls,
        item: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        coordinates = cls._coordinates(item)
        if coordinates is None:
            return None
        lat, lon = coordinates

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        kerbside_id = str(item.get("kerbsideid") or "")
        zone_number = str(item.get("zone_number") or "")
        status = str(item.get("status_description") or "").strip()
        status_lower = status.casefold()

        updated = cls._parse_time(
            item.get("status_timestamp") or item.get("lastupdated")
        )
        fresh = False
        if updated is not None:
            age = (datetime.now(UTC) - updated).total_seconds()
            fresh = -300 <= age <= _LIVE_MAX_AGE_SECONDS

        free: int | None = None
        if fresh:
            if (
                "unoccupied" in status_lower
                or "vacant" in status_lower
                or status_lower in {"free", "available"}
            ):
                free = 1
            elif (
                "present" in status_lower
                or "occupied" in status_lower
            ):
                free = 0

        bay_label = kerbside_id or zone_number or f"{lat:.6f},{lon:.6f}"
        result: dict[str, Any] = {
            "provider": "melbourne",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"melbourne:{bay_label}",
            "provider_url": PROVIDER_URL,
            "name": f"Parking bay {bay_label}",
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "street",
            "parking_type": "on_street_bay",
            "fee": "unknown",
            "access": "unknown",
            "capacity": 1,
            "has_realtime_data": free is not None,
            # Every row is a distinct physical bay. Never collapse adjacent bays
            # into a nearby OSM street-parking object or another sensor bay.
            "merge_with_other_sources": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if free is not None:
            result["free_capacity"] = free
        if updated is not None:
            result["realtime_updated_at"] = updated.isoformat()
        if status:
            result["sensor_status"] = status
        if zone_number:
            result["zone_number"] = zone_number

        return result
