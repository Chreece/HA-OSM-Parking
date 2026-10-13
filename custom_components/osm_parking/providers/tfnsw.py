from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from ..const import CONF_TFNSW_API_KEY, CONF_TFNSW_ENABLED
from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://api.transport.nsw.gov.au/v1/carpark"
PROVIDER_NAME = "Transport for NSW Car Park API"
PROVIDER_URL = "https://opendata.transport.nsw.gov.au/dataset/car-park-api"
_INDEX_CACHE_SECONDS = 24 * 60 * 60
_DISCOVERY_CONCURRENCY = 4


class TfNswParkingProvider:
    """Transport for NSW realtime car-park occupancy provider."""

    uid = "tfnsw_carpark"
    name = PROVIDER_NAME
    enabled_option = CONF_TFNSW_ENABLED
    required_options = (CONF_TFNSW_API_KEY,)

    def __init__(self) -> None:
        self._locations: dict[str, tuple[float, float, str]] = {}
        self._index_loaded_at = 0.0
        self._discovery_payloads: dict[str, dict[str, Any]] = {}

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside the NSW coverage region."""
        return -38.0 <= lat <= -27.0 and 140.5 <= lon <= 154.5

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby TfNSW car parks and realtime occupancy."""
        api_key = str((options or {}).get(CONF_TFNSW_API_KEY, "")).strip()
        if not api_key:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        await self._async_ensure_locations(session, api_key)

        candidate_ids = [
            facility_id
            for facility_id, (facility_lat, facility_lon, _) in self._locations.items()
            if haversine_m(lat, lon, facility_lat, facility_lon)
            <= radius_m + 2_000
        ]
        if not candidate_ids:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        payloads: list[dict[str, Any]] = []
        for facility_id in candidate_ids:
            cached = self._discovery_payloads.pop(facility_id, None)
            if cached is not None:
                payloads.append(cached)
                continue
            payload = await self._get_facility(session, api_key, facility_id)
            if payload is not None:
                payloads.append(payload)

        suggestions: list[dict[str, Any]] = []
        for payload in payloads:
            normalized = self._normalize(payload, lat, lon, radius_m)
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    async def _async_ensure_locations(
        self,
        session: ClientSession,
        api_key: str,
    ) -> None:
        now = monotonic()
        if (
            self._locations
            and now - self._index_loaded_at < _INDEX_CACHE_SECONDS
        ):
            return

        facilities = await self._get_json(session, api_key, ENDPOINT)
        facility_ids: list[tuple[str, str]] = []

        if isinstance(facilities, dict):
            for key, value in facilities.items():
                if isinstance(value, str):
                    facility_ids.append((str(key), value))
                elif isinstance(value, dict):
                    facility_id = str(
                        value.get("facility_id") or key
                    )
                    facility_ids.append(
                        (
                            facility_id,
                            str(
                                value.get("facility_name")
                                or value.get("name")
                                or facility_id
                            ),
                        )
                    )
        elif isinstance(facilities, list):
            for value in facilities:
                if not isinstance(value, dict):
                    continue
                facility_id = str(value.get("facility_id") or "")
                if facility_id:
                    facility_ids.append(
                        (
                            facility_id,
                            str(
                                value.get("facility_name")
                                or value.get("name")
                                or facility_id
                            ),
                        )
                    )

        if not facility_ids:
            raise RuntimeError(f"{PROVIDER_NAME}: facility list was empty")

        semaphore = asyncio.Semaphore(_DISCOVERY_CONCURRENCY)

        async def discover(
            facility_id: str,
            facility_name: str,
        ) -> tuple[str, str, dict[str, Any] | None]:
            async with semaphore:
                payload = await self._get_facility(
                    session, api_key, facility_id
                )
                return facility_id, facility_name, payload

        discovered = await asyncio.gather(
            *[
                discover(facility_id, facility_name)
                for facility_id, facility_name in facility_ids
            ],
            return_exceptions=True,
        )

        locations: dict[str, tuple[float, float, str]] = {}
        payload_cache: dict[str, dict[str, Any]] = {}
        for result in discovered:
            if isinstance(result, BaseException):
                continue
            facility_id, facility_name, payload = result
            if payload is None:
                continue
            location = payload.get("location")
            if not isinstance(location, dict):
                continue
            try:
                facility_lat = float(location["latitude"])
                facility_lon = float(location["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            name = str(
                payload.get("facility_name")
                or facility_name
                or facility_id
            )
            locations[facility_id] = (
                facility_lat,
                facility_lon,
                name,
            )
            payload_cache[facility_id] = payload

        if not locations:
            raise RuntimeError(
                f"{PROVIDER_NAME}: no facility coordinates were returned"
            )

        self._locations = locations
        self._discovery_payloads = payload_cache
        self._index_loaded_at = now

    async def _get_facility(
        self,
        session: ClientSession,
        api_key: str,
        facility_id: str,
    ) -> dict[str, Any] | None:
        payload = await self._get_json(
            session,
            api_key,
            ENDPOINT,
            {"facility": facility_id},
        )
        return payload if isinstance(payload, dict) else None

    async def _get_json(
        self,
        session: ClientSession,
        api_key: str,
        url: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"apikey {api_key}",
            "User-Agent": "HomeAssistant-OSM-Parking/0.5.0",
        }
        try:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=15,
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

    @staticmethod
    def _normalize(
        payload: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        location = payload.get("location")
        if not isinstance(location, dict):
            return None
        try:
            lat = float(location["latitude"])
            lon = float(location["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        facility_id = str(
            payload.get("facility_id")
            or payload.get("tfnsw_facility_id")
            or payload.get("ParkID")
            or "unknown"
        )
        name = str(payload.get("facility_name") or "Parking")
        tfnsw_id = str(payload.get("tfnsw_facility_id") or "")

        is_park_ride = (
            "park&ride" in name.casefold()
            or "park & ride" in name.casefold()
            or "tpr" in tfnsw_id.casefold()
        )

        result: dict[str, Any] = {
            "provider": "tfnsw",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"tfnsw:{facility_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "park_and_ride" if is_park_ride else "other",
            "parking_type": "park_and_ride" if is_park_ride else "car_park",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": True,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        address_parts = [
            str(location.get("address") or "").strip(),
            str(location.get("suburb") or "").strip(),
        ]
        address = ", ".join(part for part in address_parts if part)
        if address:
            result["address"] = address

        occupancy = payload.get("occupancy")
        occupancy_data = occupancy if isinstance(occupancy, dict) else {}

        capacity: int | None = None
        occupied: int | None = None
        try:
            if payload.get("spots") is not None:
                capacity = int(payload["spots"])
                result["capacity"] = capacity
        except (TypeError, ValueError):
            pass
        try:
            if occupancy_data.get("total") is not None:
                occupied = int(occupancy_data["total"])
                result["occupied_capacity"] = occupied
        except (TypeError, ValueError):
            pass

        if capacity is not None and occupied is not None:
            result["free_capacity"] = max(0, capacity - occupied)

        if payload.get("MessageDate"):
            result["realtime_updated_at"] = str(payload["MessageDate"])

        return result
