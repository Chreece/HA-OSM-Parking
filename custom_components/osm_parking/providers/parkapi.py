from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://api.mobidata-bw.de/park-api/api/public/v3/parking-sites"
PROVIDER_NAME = "ParkAPI / MobiData BW"


class ParkApiProvider:
    """MobiData BW ParkAPI v3 provider."""

    uid = "parkapi_mobidata_bw"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Use a broad Central-European envelope around known ParkAPI coverage."""
        return 45.0 <= lat <= 56.5 and 4.0 <= lon <= 16.5

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> ProviderFetchResult:
        """Fetch nearby car parking from ParkAPI v3."""
        params = {
            "lat": f"{lat:.7f}",
            "lon": f"{lon:.7f}",
            "radius": str(radius_m),
            "purpose": "CAR",
            "limit": "100",
            "calculate_has_realtime_data": "true",
        }

        try:
            async with session.get(
                ENDPOINT,
                params=params,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.4.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")

        suggestions: list[dict[str, Any]] = []
        live = False

        for item in items:
            normalized = self._normalize(item, lat, lon, radius_m)
            if normalized is None:
                continue
            suggestions.append(normalized)
            live = live or bool(normalized.get("has_realtime_data"))

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if live else None,
        )

    @staticmethod
    def _normalize(
        item: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        site_type = str(item.get("type") or "").upper()
        has_fee = item.get("has_fee")
        park_ride = item.get("park_and_ride_type") or []

        if has_fee is True:
            category = "paid"
        elif park_ride:
            category = "park_and_ride"
        elif site_type == "ON_STREET":
            category = "street"
        elif site_type == "UNDERGROUND":
            category = "underground"
        elif site_type == "CAR_PARK":
            category = "multi_storey"
        elif site_type == "OFF_STREET_PARKING_GROUND":
            category = "open"
        else:
            category = "other"

        name = str(item.get("name") or "Parking")
        realtime = bool(item.get("has_realtime_data"))

        result: dict[str, Any] = {
            "provider": "parkapi",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"parkapi:{item.get('id', item.get('original_uid', 'unknown'))}",
            "provider_source_id": item.get("source_id"),
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": site_type.lower() or "unknown",
            "fee": "yes" if has_fee is True else "no" if has_fee is False else "unknown",
            "access": "unknown",
            "has_realtime_data": realtime,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if item.get("public_url"):
            result["provider_url"] = str(item["public_url"])

        if item.get("operator_name"):
            result["operator"] = str(item["operator_name"])

        if item.get("address"):
            result["address"] = str(item["address"])

        if item.get("opening_hours"):
            result["opening_hours"] = str(item["opening_hours"])

        if item.get("fee_description"):
            result["price"] = str(item["fee_description"])

        capacity = item.get("realtime_capacity") if realtime else item.get("capacity")
        free_capacity = item.get("realtime_free_capacity") if realtime else None

        if capacity is not None:
            try:
                result["capacity"] = int(capacity)
            except (TypeError, ValueError):
                pass

        if free_capacity is not None:
            try:
                result["free_capacity"] = int(free_capacity)
            except (TypeError, ValueError):
                pass

        if realtime and item.get("realtime_data_updated_at"):
            result["realtime_updated_at"] = str(item["realtime_data_updated_at"])

        if realtime and item.get("realtime_opening_status"):
            result["opening_status"] = str(item["realtime_opening_status"])

        return result
