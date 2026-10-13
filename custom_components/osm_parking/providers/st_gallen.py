from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://daten.stadt.sg.ch/api/explore/v2.1/catalog/datasets/"
    "freie-parkplatze-in-der-stadt-stgallen-pls/records"
)
PROVIDER_NAME = "Stadt St.Gallen Open Data"
PROVIDER_URL = (
    "https://daten.stadt.sg.ch/explore/dataset/"
    "freie-parkplatze-in-der-stadt-stgallen-pls/"
)
LIVE_MAX_AGE_SECONDS = 15 * 60


class StGallenParkingProvider:
    """Minute-updated public parking guidance data from St.Gallen."""

    uid = "st_gallen_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in the St.Gallen city area."""
        return 47.30 <= lat <= 47.55 and 9.15 <= lon <= 9.60

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch live St.Gallen parking capacity and free spaces."""
        try:
            async with session.get(
                ENDPOINT,
                params={"limit": "100"},
                timeout=15,
                headers={
                    "User-Agent": "HomeAssistant-OSM-Parking/0.6.0"
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        records = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")

        suggestions: list[dict[str, Any]] = []
        has_live = False

        for item in records:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize(
                item,
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_live = has_live or bool(
                normalized.get("has_realtime_data")
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if has_live else None,
        )

    @classmethod
    def _normalize(
        cls,
        item: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        coordinates = cls._coordinates(item.get("koordinaten"))
        if coordinates is None:
            coordinates = cls._coordinates(item.get("geo_point_2d"))
        if coordinates is None:
            return None

        lat, lon = coordinates
        distance = round(
            haversine_m(
                destination_lat,
                destination_lon,
                lat,
                lon,
            )
        )
        if distance > radius_m:
            return None

        name = str(item.get("ph_name") or "Parking")
        name_folded = name.casefold()
        category = (
            "multi_storey"
            if any(
                token in name_folded
                for token in ("parkhaus", "parkgarage", "cityparking")
            )
            else "open"
        )

        parking_id = str(item.get("ph_id") or name)
        updated = item.get("letzte_aktualisierung")
        fresh = cls._is_fresh(updated)

        result: dict[str, Any] = {
            "provider": "st_gallen",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"st-gallen:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": (
                "multi_storey" if category == "multi_storey" else "open"
            ),
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": fresh,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Stadt St.Gallen Open Data",
        }

        for source, target in (
            ("anzahl_parkplatze", "capacity"),
            ("besetzt", "occupied_capacity"),
            ("anzahl_elektro_parkplatze", "ev_capacity"),
            ("frei_elektro", "ev_free_capacity"),
            ("anzahl_behindertenparkplatze", "accessible_capacity"),
            ("frei_behindertenparkplatze", "accessible_free_capacity"),
        ):
            value = item.get(source)
            if value is None:
                continue
            try:
                result[target] = int(value)
            except (TypeError, ValueError):
                pass

        # Never present an old vacancy number as live.
        if fresh:
            try:
                if item.get("frei") is not None:
                    result["free_capacity"] = int(item["frei"])
            except (TypeError, ValueError):
                pass

            status_code = item.get("ph_status_code")
            try:
                status_number = int(status_code)
            except (TypeError, ValueError):
                status_number = -1

            status_text = str(item.get("ph_status") or "").casefold()
            if status_number == 1 or status_text in {
                "offen",
                "open",
            }:
                result["opening_status"] = "open"
            elif status_number >= 0 or status_text:
                result["opening_status"] = "closed"

            if updated:
                result["realtime_updated_at"] = str(updated)

        return result

    @staticmethod
    def _coordinates(value: Any) -> tuple[float, float] | None:
        if isinstance(value, dict):
            for lat_key, lon_key in (
                ("lat", "lon"),
                ("latitude", "longitude"),
            ):
                if lat_key in value and lon_key in value:
                    try:
                        lat = float(value[lat_key])
                        lon = float(value[lon_key])
                    except (TypeError, ValueError):
                        continue
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return lat, lon

        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                first = float(value[0])
                second = float(value[1])
            except (TypeError, ValueError):
                return None

            # Opendatasoft geo_point_2d commonly serializes [lat, lon].
            if -90 <= first <= 90 and -180 <= second <= 180:
                return first, second
            if -90 <= second <= 90 and -180 <= first <= 180:
                return second, first

        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2:
                try:
                    first = float(parts[0])
                    second = float(parts[1])
                except ValueError:
                    return None
                if -90 <= first <= 90 and -180 <= second <= 180:
                    return first, second

        return None

    @staticmethod
    def _is_fresh(value: Any) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age = (
                datetime.now(UTC) - parsed.astimezone(UTC)
            ).total_seconds()
            return -300 <= age <= LIVE_MAX_AGE_SECONDS
        except (TypeError, ValueError):
            return False
