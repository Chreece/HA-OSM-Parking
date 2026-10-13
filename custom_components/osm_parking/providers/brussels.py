from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/"
    "bruxelles_parkings_publics/records"
)
PROVIDER_NAME = "Brussels Open Data"
PROVIDER_URL = (
    "https://opendata.brussels.be/explore/assets/"
    "bruxelles_parkings_publics/view/"
)


class BrusselsParkingProvider:
    """Public car parks published by Brussels Open Data."""

    uid = "brussels_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in the Brussels Capital Region."""
        return 50.72 <= lat <= 50.98 and 4.20 <= lon <= 4.55

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch public parking facilities and static metadata."""
        try:
            async with session.get(
                ENDPOINT,
                params={"limit": "100"},
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.5.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        records = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")

        suggestions: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize(
                item,
                lat,
                lon,
                radius_m,
            )
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
        )

    @staticmethod
    def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
        point = item.get("geo_point_2d")
        if isinstance(point, dict):
            try:
                return float(point["lat"]), float(point["lon"])
            except (KeyError, TypeError, ValueError):
                pass
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                # Opendatasoft sometimes serializes geopoints as [lat, lon].
                return float(point[0]), float(point[1])
            except (TypeError, ValueError):
                pass
        return None

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

        name = str(
            item.get("name_en")
            or item.get("name_fr")
            or item.get("name_nl")
            or "Parking"
        )
        floors = item.get("floors")
        try:
            floor_count = int(floors) if floors is not None else 0
        except (TypeError, ValueError):
            floor_count = 0

        category = "multi_storey" if floor_count > 1 else "open"
        result: dict[str, Any] = {
            "provider": "brussels",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"brussels:{name.casefold()}:{lat:.6f}:{lon:.6f}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": "multi_storey" if floor_count > 1 else "public",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        address = item.get("adressee") or item.get("address")
        if address:
            result["address"] = str(address)
        operator = (
            item.get("operator_en")
            or item.get("operator_fr")
            or item.get("operator_nl")
        )
        if operator:
            result["operator"] = str(operator)
        try:
            if item.get("capacity") is not None:
                result["capacity"] = int(item["capacity"])
        except (TypeError, ValueError):
            pass
        try:
            if item.get("disabledcapacity") is not None:
                result["capacity_disabled"] = int(
                    item["disabledcapacity"]
                )
        except (TypeError, ValueError):
            pass
        if item.get("maxheight") not in (None, "", -999, "-999"):
            result["max_height"] = item["maxheight"]
        if item.get("maxwidth") not in (None, "", -999, "-999"):
            result["max_width"] = item["maxwidth"]

        return result
