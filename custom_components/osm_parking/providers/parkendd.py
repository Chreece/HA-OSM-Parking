from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

BASE_URL = "https://api.parkendd.de"
PROVIDER_NAME = "ParkenDD / ParkAPI"
PROVIDER_URL = "https://github.com/offenesdresden/ParkAPI"
_META_CACHE_SECONDS = 24 * 60 * 60
_LIVE_MAX_AGE_SECONDS = 45 * 60
_CITY_MATCH_RADIUS_M = 75_000


class ParkenDdProvider:
    """Key-free ParkenDD public API provider for supported European cities."""

    uid = "parkendd"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._cities: dict[str, dict[str, Any]] = {}
        self._cities_loaded_at = 0.0

    def applies(self, lat: float, lon: float) -> bool:
        """Limit metadata lookups to ParkenDD's European coverage region."""
        return 46.0 <= lat <= 58.5 and 4.0 <= lon <= 15.5

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> ProviderFetchResult:
        """Fetch parking for the nearest supported ParkenDD city."""
        cities = await self._async_cities(session)
        city_id = self._nearest_city(cities, lat, lon)
        if city_id is None:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        payload = await self._get_json(session, f"{BASE_URL}/{city_id}")
        lots = payload.get("lots") if isinstance(payload, dict) else None
        if not isinstance(lots, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid city response")

        live_is_fresh = self._is_fresh(
            payload.get("last_updated") or payload.get("last_downloaded")
        )
        updated = payload.get("last_updated") or payload.get("last_downloaded")
        data_source = payload.get("data_source")

        suggestions: list[dict[str, Any]] = []
        for lot in lots:
            if not isinstance(lot, dict):
                continue
            normalized = self._normalize(
                lot,
                city_id,
                lat,
                lon,
                radius_m,
                live_is_fresh,
                updated,
                data_source,
            )
            if normalized is not None:
                suggestions.append(normalized)

        has_live = any(item.get("has_realtime_data") for item in suggestions)
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if has_live else None,
        )

    async def _async_cities(
        self, session: ClientSession
    ) -> dict[str, dict[str, Any]]:
        now = monotonic()
        if self._cities and now - self._cities_loaded_at < _META_CACHE_SECONDS:
            return self._cities

        payload = await self._get_json(session, BASE_URL)
        cities = payload.get("cities") if isinstance(payload, dict) else None
        if not isinstance(cities, dict):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid metadata response")

        self._cities = {
            str(city_id): value
            for city_id, value in cities.items()
            if isinstance(value, dict)
        }
        self._cities_loaded_at = now
        return self._cities

    async def _get_json(
        self, session: ClientSession, url: str
    ) -> dict[str, Any]:
        try:
            async with session.get(
                url,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.5.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if not isinstance(payload, dict):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid JSON response")
        return payload

    @staticmethod
    def _nearest_city(
        cities: dict[str, dict[str, Any]],
        lat: float,
        lon: float,
    ) -> str | None:
        best_id: str | None = None
        best_distance = float("inf")

        for city_id, city in cities.items():
            coords = city.get("coords")
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                continue
            try:
                city_lat = float(coords[0])
                city_lon = float(coords[1])
            except (TypeError, ValueError):
                continue

            distance = haversine_m(lat, lon, city_lat, city_lon)
            if distance < best_distance:
                best_distance = distance
                best_id = city_id

        if best_distance > _CITY_MATCH_RADIUS_M:
            return None
        return best_id

    @staticmethod
    def _is_fresh(value: Any) -> bool:
        if not value:
            return False
        try:
            text = str(value).strip()
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()
            return -300 <= age <= _LIVE_MAX_AGE_SECONDS
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalize(
        lot: dict[str, Any],
        city_id: str,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
        live_is_fresh: bool,
        updated: Any,
        data_source: Any,
    ) -> dict[str, Any] | None:
        coords = lot.get("coords")
        if not isinstance(coords, dict):
            return None
        try:
            lat = float(coords["lat"])
            lon = float(coords.get("lng", coords.get("lon")))
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        lot_type = str(lot.get("lot_type") or "").casefold()
        if "tief" in lot_type or "underground" in lot_type:
            category = "underground"
        elif (
            "parkhaus" in lot_type
            or "garage" in lot_type
            or "multi" in lot_type
        ):
            category = "multi_storey"
        elif "p+r" in lot_type or "park & ride" in lot_type:
            category = "park_and_ride"
        else:
            category = "open"

        lot_id = str(lot.get("id") or lot.get("name") or "unknown")
        state = str(lot.get("state") or "unknown").casefold()

        result: dict[str, Any] = {
            "provider": "parkendd",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"parkendd:{city_id}:{lot_id}",
            "provider_url": str(lot.get("url") or PROVIDER_URL),
            "name": str(lot.get("name") or "Parking"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": lot_type or "unknown",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": bool(
                live_is_fresh
                and lot.get("free") is not None
                and state not in {"nodata", "unknown"}
            ),
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if lot.get("address"):
            result["address"] = str(lot["address"])
        if lot.get("opening_hours"):
            result["opening_hours"] = str(lot["opening_hours"])
        if lot.get("fee_hours"):
            result["fee_hours"] = str(lot["fee_hours"])
        if data_source:
            result["upstream_source"] = str(data_source)

        try:
            result["capacity"] = int(lot["total"])
        except (KeyError, TypeError, ValueError):
            pass

        if result["has_realtime_data"]:
            try:
                result["free_capacity"] = int(lot["free"])
            except (TypeError, ValueError):
                result["has_realtime_data"] = False
            if updated:
                result["realtime_updated_at"] = str(updated)

        if state in {"open", "closed"}:
            result["opening_status"] = state

        return result
