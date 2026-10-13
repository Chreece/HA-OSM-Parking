from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://data.strasbourg.eu/api/explore/v2.1/catalog/datasets/"
    "occupation-parkings-temps-reel/records"
)
PROVIDER_NAME = "Eurométropole de Strasbourg Open Data"
PROVIDER_URL = (
    "https://data.strasbourg.eu/explore/dataset/"
    "occupation-parkings-temps-reel/"
)


class StrasbourgParkingProvider:
    """Realtime structured car parks from Strasbourg Open Data."""

    uid = "strasbourg_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside greater Strasbourg."""
        return 48.40 <= lat <= 48.75 and 7.45 <= lon <= 7.95

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch current capacity and vacancy from the official feed."""
        try:
            async with session.get(
                ENDPOINT,
                params={"limit": "100"},
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.7.0",
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
            normalized = self._normalize(item, lat, lon, radius_m)
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_live = has_live or bool(normalized.get("has_realtime_data"))

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=180 if has_live else None,
        )

    @staticmethod
    def _normalize(
        item: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        position = item.get("position")
        if not isinstance(position, dict):
            return None
        try:
            lat = float(position["lat"])
            lon = float(position["lon"])
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        try:
            status_code = int(item.get("etat"))
        except (TypeError, ValueError):
            status_code = 0

        # The official schema defines 0 as realtime unavailable, 1 as open,
        # 2 as closed and 3 as full.
        has_live = status_code in {1, 2, 3}

        parking_id = str(
            item.get("idsurfs")
            or item.get("ident")
            or item.get("nom_parking")
            or "unknown"
        )

        result: dict[str, Any] = {
            "provider": "strasbourg",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"strasbourg:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(item.get("nom_parking") or "Parking"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "multi_storey",
            "parking_type": "structured_parking",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": has_live,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Eurométropole de Strasbourg Open Data",
        }

        try:
            total = int(item.get("total"))
            if total >= 0:
                result["capacity"] = total
        except (TypeError, ValueError):
            pass

        if has_live:
            try:
                free = int(item.get("libre"))
                if free >= 0:
                    result["free_capacity"] = free
                    if result.get("capacity") is not None:
                        result["occupied_capacity"] = max(
                            0,
                            int(result["capacity"]) - free,
                        )
            except (TypeError, ValueError):
                pass

            if status_code == 1:
                result["opening_status"] = "open"
            elif status_code in {2, 3}:
                result["opening_status"] = (
                    "closed" if status_code == 2 else "full"
                )

        if item.get("etat_descriptif"):
            result["status_description"] = str(item["etat_descriptif"])
        if item.get("realtimestatus"):
            result["realtime_status"] = str(item["realtimestatus"])
        if item.get("taux_occup") is not None:
            try:
                result["occupancy_ratio"] = float(item["taux_occup"])
            except (TypeError, ValueError):
                pass

        return result
