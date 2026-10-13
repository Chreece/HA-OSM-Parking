from __future__ import annotations

from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from ..const import (
    CONF_TDX_CLIENT_ID,
    CONF_TDX_CLIENT_SECRET,
    CONF_TDX_ENABLED,
)
from .base import ProviderFetchResult, haversine_m, navigation_url, geo_uri

TOKEN_URL = (
    "https://tdx.transportdata.tw/auth/realms/TDXConnect/"
    "protocol/openid-connect/token"
)
API_BASE = "https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet"
PROVIDER_NAME = "Taiwan TDX Parking"
PROVIDER_URL = "https://tdx.transportdata.tw/api-service/swagger"
_STATIC_CACHE_SECONDS = 6 * 60 * 60

# Approximate county/city centers are only used to choose the few TDX city
# feeds worth checking. Results are always filtered by the exact destination
# radius using each parking facility's own WGS84 coordinates.
CITY_CENTERS: dict[str, tuple[float, float]] = {
    "Taipei": (25.0375, 121.5637),
    "NewTaipei": (25.0120, 121.4650),
    "Keelung": (25.1283, 121.7419),
    "Taoyuan": (24.9937, 121.3010),
    "Hsinchu": (24.8138, 120.9675),
    "HsinchuCounty": (24.8387, 121.0177),
    "MiaoliCounty": (24.5602, 120.8214),
    "Taichung": (24.1477, 120.6736),
    "ChanghuaCounty": (24.0756, 120.5440),
    "NantouCounty": (23.9609, 120.9719),
    "YunlinCounty": (23.7092, 120.4313),
    "Chiayi": (23.4801, 120.4491),
    "ChiayiCounty": (23.4518, 120.2555),
    "Tainan": (22.9999, 120.2270),
    "Kaohsiung": (22.6273, 120.3014),
    "PingtungCounty": (22.5519, 120.5488),
    "YilanCounty": (24.7021, 121.7378),
    "HualienCounty": (23.9911, 121.6112),
    "TaitungCounty": (22.7554, 121.1500),
    "PenghuCounty": (23.5712, 119.5793),
    "KinmenCounty": (24.4494, 118.3767),
    "LienchiangCounty": (26.1602, 119.9517),
}


class TaiwanTdxParkingProvider:
    """Taiwan TDX off-street parking + realtime availability provider."""

    uid = "taiwan_tdx"
    name = PROVIDER_NAME
    enabled_option = CONF_TDX_ENABLED
    required_options = (CONF_TDX_CLIENT_ID, CONF_TDX_CLIENT_SECRET)

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._static_cache: dict[str, list[dict[str, Any]]] = {}
        self._static_loaded_at: dict[str, float] = {}

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in Taiwan or its island counties."""
        return 21.7 <= lat <= 26.6 and 118.0 <= lon <= 122.3

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby Taiwan parking and current availability."""
        config = options or {}
        client_id = str(config.get(CONF_TDX_CLIENT_ID, "")).strip()
        client_secret = str(config.get(CONF_TDX_CLIENT_SECRET, "")).strip()
        if not client_id or not client_secret:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        token = await self._async_token(
            session, client_id, client_secret
        )

        nearby_static: list[tuple[str, dict[str, Any]]] = []
        for city in self._candidate_cities(lat, lon):
            static = await self._async_static_city(session, token, city)
            for item in static:
                coords = self._coordinates(item)
                if coords is None:
                    continue
                item_lat, item_lon = coords
                if (
                    haversine_m(lat, lon, item_lat, item_lon)
                    <= radius_m
                ):
                    nearby_static.append((city, item))

        if not nearby_static:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        by_city: dict[str, list[dict[str, Any]]] = {}
        for city, item in nearby_static:
            by_city.setdefault(city, []).append(item)

        suggestions: list[dict[str, Any]] = []
        has_live = False
        refresh_candidates: list[int] = []

        for city, static_items in by_city.items():
            ids = [
                str(item.get("CarParkID") or "")
                for item in static_items
                if item.get("CarParkID")
            ]
            live_items = await self._async_availability(
                session, token, city, ids
            )
            live_by_id = {
                str(item.get("CarParkID")): item
                for item in live_items
                if isinstance(item, dict) and item.get("CarParkID")
            }

            for item in static_items:
                parking_id = str(item.get("CarParkID") or "")
                normalized = self._normalize(
                    item,
                    live_by_id.get(parking_id),
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

            for live in live_items:
                try:
                    interval = int(live.get("SrcUpdateInterval") or 0)
                except (TypeError, ValueError):
                    interval = 0
                if interval > 0:
                    refresh_candidates.append(interval)

        refresh_seconds = None
        if has_live:
            refresh_seconds = max(
                60,
                min(refresh_candidates or [60]),
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=refresh_seconds,
        )

    async def _async_token(
        self,
        session: ClientSession,
        client_id: str,
        client_secret: str,
    ) -> str:
        now = monotonic()
        if self._token and now < self._token_expires_at:
            return self._token

        try:
            async with session.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=15,
                headers={
                    "User-Agent": "HomeAssistant-OSM-Parking/0.5.0"
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} auth: {err}") from err

        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise RuntimeError(f"{PROVIDER_NAME}: token response was invalid")

        token = str(payload["access_token"])
        try:
            expires_in = int(payload.get("expires_in") or 900)
        except (TypeError, ValueError):
            expires_in = 900

        self._token = token
        self._token_expires_at = now + max(60, expires_in - 60)
        return token

    def _candidate_cities(
        self, lat: float, lon: float
    ) -> list[str]:
        ordered = sorted(
            CITY_CENTERS.items(),
            key=lambda item: haversine_m(
                lat,
                lon,
                item[1][0],
                item[1][1],
            ),
        )
        # Query up to three neighboring authorities. This avoids brittle county
        # polygon logic near administrative borders while keeping request count
        # small; exact facility coordinates are filtered locally afterward.
        return [name for name, _ in ordered[:3]]

    async def _async_static_city(
        self,
        session: ClientSession,
        token: str,
        city: str,
    ) -> list[dict[str, Any]]:
        now = monotonic()
        if (
            city in self._static_cache
            and now - self._static_loaded_at.get(city, 0)
            < _STATIC_CACHE_SECONDS
        ):
            return self._static_cache[city]

        url = f"{API_BASE}/CarPark/City/{city}"
        payload = await self._get_json(
            session,
            token,
            url,
            {"$format": "JSON", "$top": "5000"},
        )
        items = self._unwrap_items(payload)
        self._static_cache[city] = items
        self._static_loaded_at[city] = now
        return items

    async def _async_availability(
        self,
        session: ClientSession,
        token: str,
        city: str,
        parking_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not parking_ids:
            return []

        escaped = [
            parking_id.replace("'", "''")
            for parking_id in parking_ids
        ]
        filter_value = " or ".join(
            f"CarParkID eq '{parking_id}'"
            for parking_id in escaped
        )

        url = f"{API_BASE}/ParkingAvailability/City/{city}"
        payload = await self._get_json(
            session,
            token,
            url,
            {
                "$format": "JSON",
                "$top": str(max(100, len(parking_ids) * 2)),
                "$filter": filter_value,
            },
        )
        return self._unwrap_items(payload)

    async def _get_json(
        self,
        session: ClientSession,
        token: str,
        url: str,
        params: dict[str, str],
    ) -> Any:
        try:
            async with session.get(
                url,
                params=params,
                timeout=20,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.5.0",
                },
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

    @staticmethod
    def _unwrap_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            items = payload.get("Items")
            if isinstance(items, list):
                return [
                    item for item in items if isinstance(item, dict)
                ]
        return []

    @staticmethod
    def _coordinates(
        item: dict[str, Any],
    ) -> tuple[float, float] | None:
        position = item.get("CarParkPosition")
        if not isinstance(position, dict):
            return None
        try:
            return (
                float(position["PositionLat"]),
                float(position["PositionLon"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    @classmethod
    def _normalize(
        cls,
        static: dict[str, Any],
        live: dict[str, Any] | None,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        coordinates = cls._coordinates(static)
        if coordinates is None:
            return None
        lat, lon = coordinates

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = str(static.get("CarParkID") or "")
        if not parking_id:
            return None

        name = str(
            static.get("CarParkName")
            or (live or {}).get("CarParkName")
            or "Parking"
        )
        type_text = str(static.get("CarParkType") or "").casefold()

        if "underground" in type_text or "地下" in type_text:
            category = "underground"
        elif (
            "multi" in type_text
            or "structure" in type_text
            or "立體" in type_text
        ):
            category = "multi_storey"
        elif "park" in name.casefold() and "ride" in name.casefold():
            category = "park_and_ride"
        else:
            category = "open"

        result: dict[str, Any] = {
            "provider": "tdx",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"tdx:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": type_text or "off_street",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if static.get("Address"):
            result["address"] = str(static["Address"])

        if live:
            available_raw = live.get("AvailableSpaces")
            total_raw = live.get("TotalSpaces")
            try:
                available = int(available_raw)
            except (TypeError, ValueError):
                available = -1
            try:
                total = int(total_raw)
            except (TypeError, ValueError):
                total = -1

            if total >= 0:
                result["capacity"] = total
            if available >= 0:
                result["free_capacity"] = available
                result["has_realtime_data"] = True

            service_status = live.get("ServiceStatus")
            if service_status is not None:
                try:
                    status = int(service_status)
                except (TypeError, ValueError):
                    status = -1
                if status == 1:
                    result["opening_status"] = "open"
                    result["has_realtime_data"] = True
                elif status in {0, 2, 3}:
                    result["opening_status"] = "closed"
                    result["has_realtime_data"] = True

            updated = (
                live.get("DataCollectTime")
                or live.get("UpdateTime")
                or live.get("SrcUpdateTime")
            )
            if updated:
                result["realtime_updated_at"] = str(updated)

        return result
