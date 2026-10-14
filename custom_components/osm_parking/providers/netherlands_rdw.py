from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

PROVIDER_NAME = "Netherlands RDW Open Data"
# Conservative Netherlands coverage bands with a small border buffer.
# RDW's APIs still apply an exact radius query afterwards. Splitting the old
# 50.70–53.75 / 3.15–7.35 rectangle avoids querying RDW from large parts of
# western Germany (for example Cologne/Düsseldorf) while preserving Dutch
# border areas where a <=10 km search can legitimately cross the border.
_NETHERLANDS_COVERAGE_REGIONS = (
    (50.65, 3.15, 51.30, 6.30),  # Zeeland, Brabant, Limburg + border buffer
    (51.30, 3.15, 51.85, 6.75),  # South/central Netherlands
    (51.85, 3.50, 52.50, 7.10),  # Randstad, Gelderland, Overijssel
    (52.50, 4.25, 53.75, 7.35),  # North Netherlands + Wadden area
)

DATASETS = (
    (
        "garage",
        "https://opendata.rdw.nl/resource/t5pc-eb34.json",
        "https://opendata.rdw.nl/d/t5pc-eb34",
        "multi_storey",
    ),
    (
        "park_and_ride",
        "https://opendata.rdw.nl/resource/6wzd-evwu.json",
        "https://opendata.rdw.nl/d/6wzd-evwu",
        "park_and_ride",
    ),
)


class NetherlandsRdwProvider:
    """Dutch national RDW parking garages and Park & Ride locations."""

    uid = "netherlands_rdw"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates plausibly overlap Dutch RDW coverage."""
        return any(
            south <= lat <= north and west <= lon <= east
            for south, west, north, east in _NETHERLANDS_COVERAGE_REGIONS
        )

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby RDW garages and P+R locations."""
        results = await asyncio.gather(
            *[
                self._fetch_dataset(
                    session,
                    endpoint,
                    dataset_url,
                    category,
                    lat,
                    lon,
                    radius_m,
                )
                for _, endpoint, dataset_url, category in DATASETS
            ],
            return_exceptions=True,
        )

        suggestions: list[dict[str, Any]] = []
        errors: list[str] = []
        for result in results:
            if isinstance(result, BaseException):
                errors.append(str(result))
            else:
                suggestions.extend(result)

        if not suggestions and errors:
            raise RuntimeError("; ".join(errors))

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
        )

    async def _fetch_dataset(
        self,
        session: ClientSession,
        endpoint: str,
        dataset_url: str,
        category: str,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> list[dict[str, Any]]:
        params = {
            "$where": f"within_circle(location,{lat:.7f},{lon:.7f},{radius_m})",
            "$limit": "100",
        }

        try:
            async with session.get(
                endpoint,
                params=params,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.5.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if not isinstance(payload, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")

        suggestions: list[dict[str, Any]] = []
        for item in payload:
            normalized = self._normalize(
                item,
                category,
                dataset_url,
                lat,
                lon,
                radius_m,
            )
            if normalized is not None:
                suggestions.append(normalized)
        return suggestions

    @staticmethod
    def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
        location = item.get("location")
        if isinstance(location, dict):
            coordinates = location.get("coordinates")
            if (
                isinstance(coordinates, list)
                and len(coordinates) >= 2
            ):
                try:
                    return float(coordinates[1]), float(coordinates[0])
                except (TypeError, ValueError):
                    pass

            for lat_key, lon_key in (
                ("latitude", "longitude"),
                ("lat", "lon"),
            ):
                if lat_key in location and lon_key in location:
                    try:
                        return float(location[lat_key]), float(location[lon_key])
                    except (TypeError, ValueError):
                        pass
        return None

    @classmethod
    def _normalize(
        cls,
        item: dict[str, Any],
        category: str,
        dataset_url: str,
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

        area_id = str(item.get("areaid") or "")
        name = str(item.get("areadesc") or area_id or "Parking")

        address_parts = [
            str(item.get("location_address") or "").strip(),
            " ".join(
                part
                for part in (
                    str(item.get("location_zip") or "").strip(),
                    str(item.get("location_city") or "").strip(),
                )
                if part
            ).strip(),
        ]
        address = ", ".join(part for part in address_parts if part)

        result: dict[str, Any] = {
            "provider": "netherlands_rdw",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"rdw:{category}:{area_id or lat}:{lon}",
            "provider_url": dataset_url,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": (
                "park_and_ride" if category == "park_and_ride" else "garage"
            ),
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if address:
            result["address"] = address
        if item.get("usageid"):
            result["usage_id"] = str(item["usageid"])

        return result
