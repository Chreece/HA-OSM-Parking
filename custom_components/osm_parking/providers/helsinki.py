from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

AREAS_ENDPOINT = "https://pubapi.parkkiopas.fi/public/v1/parking_area/"
STATS_ENDPOINT = "https://pubapi.parkkiopas.fi/public/v1/parking_area_statistics/"
PROVIDER_NAME = "Helsinki Parkkihubi"
PROVIDER_URL = "https://github.com/City-of-Helsinki/parkkihubi"
_MAX_PAGES = 20


class HelsinkiParkingProvider:
    """Helsinki public parking-area statistics provider."""

    uid = "helsinki_parkkihubi"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in the Helsinki area."""
        return 59.95 <= lat <= 60.40 and 24.55 <= lon <= 25.35

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> ProviderFetchResult:
        """Fetch parking polygons and current parking-area statistics."""
        areas_payload = await self._fetch_pages(
            session, AREAS_ENDPOINT, "features"
        )
        stats_payload = await self._fetch_pages(
            session, STATS_ENDPOINT, "results"
        )

        stats_by_id = {
            str(row.get("id")): row
            for row in stats_payload
            if isinstance(row, dict) and row.get("id") is not None
        }

        suggestions: list[dict[str, Any]] = []
        has_stats = False

        for feature in areas_payload:
            if not isinstance(feature, dict):
                continue
            area_id = str(feature.get("id") or "")
            normalized = self._normalize(
                feature,
                stats_by_id.get(area_id),
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_stats = has_stats or bool(
                normalized.get("has_realtime_data")
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if has_stats else None,
        )

    async def _fetch_pages(
        self,
        session: ClientSession,
        endpoint: str,
        result_key: str,
    ) -> list[dict[str, Any]]:
        url: str | None = endpoint
        params: dict[str, str] | None = {"page_size": "500"}
        rows: list[dict[str, Any]] = []

        for _ in range(_MAX_PAGES):
            if url is None:
                break
            try:
                async with session.get(
                    url,
                    params=params,
                    timeout=20,
                    headers={
                        "User-Agent": "HomeAssistant-OSM-Parking/0.5.0"
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

            params = None
            if not isinstance(payload, dict):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid response")
            page_rows = payload.get(result_key)
            if not isinstance(page_rows, list):
                raise RuntimeError(
                    f"{PROVIDER_NAME}: missing {result_key}"
                )
            rows.extend(
                row for row in page_rows if isinstance(row, dict)
            )
            next_url = payload.get("next")
            url = str(next_url) if next_url else None

        return rows

    @staticmethod
    def _geometry_center(
        geometry: dict[str, Any] | None,
    ) -> tuple[float, float] | None:
        if not isinstance(geometry, dict):
            return None

        points: list[tuple[float, float]] = []

        def collect(value: Any) -> None:
            if not isinstance(value, list):
                return
            if (
                len(value) >= 2
                and isinstance(value[0], (int, float))
                and isinstance(value[1], (int, float))
            ):
                points.append((float(value[0]), float(value[1])))
                return
            for child in value:
                collect(child)

        collect(geometry.get("coordinates"))
        if not points:
            return None

        lons = [point[0] for point in points]
        lats = [point[1] for point in points]
        return (
            (min(lats) + max(lats)) / 2,
            (min(lons) + max(lons)) / 2,
        )

    @classmethod
    def _normalize(
        cls,
        feature: dict[str, Any],
        statistics: dict[str, Any] | None,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        center = cls._geometry_center(feature.get("geometry"))
        if center is None:
            return None
        lat, lon = center

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        properties = feature.get("properties")
        props = properties if isinstance(properties, dict) else {}
        area_id = str(feature.get("id") or "unknown")

        capacity: int | None = None
        try:
            capacity = int(props["capacity_estimate"])
        except (KeyError, TypeError, ValueError):
            pass

        current_count: int | None = None
        if statistics is not None:
            try:
                current_count = int(statistics["current_parking_count"])
            except (KeyError, TypeError, ValueError):
                pass

        result: dict[str, Any] = {
            "provider": "helsinki_parkkihubi",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"helsinki:{area_id}",
            "provider_url": PROVIDER_URL,
            "name": str(
                props.get("name")
                or props.get("description")
                or f"Parking area {area_id[:8]}"
            ),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "street",
            "parking_type": "parking_area",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": statistics is not None,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if capacity is not None:
            result["capacity"] = capacity

        if current_count is not None:
            # The public API deliberately returns 0 whenever the true count is
            # 3 or less. Never translate that privacy-protected zero into an
            # exact vacancy count.
            if current_count > 3:
                result["occupied_capacity"] = current_count
                if capacity is not None:
                    result["free_capacity"] = max(
                        0, capacity - current_count
                    )
            else:
                result["occupancy_privacy_suppressed"] = True
                if capacity is not None:
                    result["free_capacity_min"] = max(0, capacity - 3)
                    result["free_capacity_max"] = capacity

        return result
