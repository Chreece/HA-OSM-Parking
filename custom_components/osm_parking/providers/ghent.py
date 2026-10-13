from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://data.stad.gent/api/explore/v2.1/catalog/datasets/"
    "bezetting-parkeergarages-real-time/records"
)
PROVIDER_NAME = "Stad Gent Open Data"
PROVIDER_URL = (
    "https://data.stad.gent/explore/assets/"
    "bezetting-parkeergarages-real-time/view/"
)


class GhentParkingProvider:
    """Realtime public parking garages from Stad Gent Open Data."""

    uid = "ghent_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in the Ghent metropolitan area."""
        return 50.85 <= lat <= 51.25 and 3.40 <= lon <= 4.10

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch realtime Gent parking occupancy."""
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
            normalized = self._normalize(item, lat, lon, radius_m)
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=180 if suggestions else None,
        )

    @staticmethod
    def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
        location = item.get("location")
        if isinstance(location, dict):
            try:
                return float(location["lat"]), float(location["lon"])
            except (KeyError, TypeError, ValueError):
                pass

        dimension = item.get("locationanddimension")
        if isinstance(dimension, dict):
            display = dimension.get("coordinatesForDisplay")
            if isinstance(display, dict):
                try:
                    return float(display["latitude"]), float(display["longitude"])
                except (KeyError, TypeError, ValueError):
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

        parking_type = str(item.get("type") or "").lower()
        if parking_type == "offstreetparkingground":
            category = "open"
        elif parking_type == "carpark":
            category = "multi_storey"
        else:
            category = "other"

        free_parking = item.get("freeparking")
        fee = "no" if free_parking in (1, True, "1", "true") else "unknown"

        provider_id = str(
            item.get("id")
            or item.get("urllinkaddress")
            or item.get("name")
            or "unknown"
        )

        result: dict[str, Any] = {
            "provider": "ghent",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"gent:{provider_id}",
            "provider_url": str(item.get("urllinkaddress") or PROVIDER_URL),
            "name": str(item.get("name") or "Parking"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": parking_type or "unknown",
            "fee": fee,
            "access": "unknown",
            "has_realtime_data": True,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        for source, target in (
            ("totalcapacity", "capacity"),
            ("availablecapacity", "free_capacity"),
        ):
            value = item.get(source)
            if value is not None:
                try:
                    result[target] = int(value)
                except (TypeError, ValueError):
                    pass

        if item.get("lastupdate"):
            result["realtime_updated_at"] = str(item["lastupdate"])

        if item.get("openingtimesdescription"):
            result["opening_hours"] = str(item["openingtimesdescription"])

        if item.get("operatorinformation"):
            result["operator"] = str(item["operatorinformation"])

        if item.get("isopennow") is not None:
            result["opening_status"] = (
                "open" if item.get("isopennow") in (1, True, "1", "true") else "closed"
            )

        if item.get("temporaryclosed") in (1, True, "1", "true"):
            result["opening_status"] = "closed"

        dimension = item.get("locationanddimension")
        if isinstance(dimension, dict):
            road_name = str(dimension.get("roadName") or "").strip()
            if road_name and road_name != "?":
                result["address"] = road_name

        return result
