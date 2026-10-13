from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

LIVE_URL = "https://opendata.dublincity.ie/TrafficOpenData/CP_TR/CPDATA.xml"
STATIC_URL = "https://data.smartdublin.ie/api/3/action/datastore_search"
STATIC_RESOURCE_ID = "900faaec-755f-4e50-8811-c8121b2b8921"
PROVIDER_NAME = "Dublin City Council Open Data"
PROVIDER_URL = "https://data.smartdublin.ie/dataset/multi-story-car-parking-space-availability"


class DublinParkingProvider:
    """Dublin City Council live multistorey car-park availability."""

    uid = "dublin_dcc"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in the Dublin urban area."""
        return 53.20 <= lat <= 53.50 and -6.55 <= lon <= -6.00

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Combine DCC live free spaces with the official coordinate dataset."""
        live_result, static_result = await asyncio.gather(
            self._async_live(session),
            self._async_static(session),
            return_exceptions=True,
        )

        if isinstance(static_result, BaseException):
            raise RuntimeError(str(static_result))

        live: dict[str, int] = {}
        if not isinstance(live_result, BaseException):
            live = live_result

        suggestions: list[dict[str, Any]] = []
        for item in static_result:
            normalized = self._normalize(
                item,
                live,
                lat,
                lon,
                radius_m,
            )
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if live else None,
        )

    async def _async_live(
        self,
        session: ClientSession,
    ) -> dict[str, int]:
        try:
            async with session.get(
                LIVE_URL,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.5.0"},
            ) as response:
                response.raise_for_status()
                body = await response.read()
        except (ClientError, TimeoutError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} live data: {err}") from err

        try:
            root = ET.fromstring(body)
        except ET.ParseError as err:
            raise RuntimeError(
                f"{PROVIDER_NAME}: invalid live XML: {err}"
            ) from err

        result: dict[str, int] = {}
        for element in root.iter():
            if element.tag.casefold().split("}")[-1] != "carpark":
                continue
            name = str(element.attrib.get("name") or "").strip()
            spaces = element.attrib.get("spaces")
            if not name or spaces is None:
                continue
            try:
                result[self._key(name)] = int(spaces)
            except (TypeError, ValueError):
                continue
        return result

    async def _async_static(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        try:
            async with session.get(
                STATIC_URL,
                params={
                    "resource_id": STATIC_RESOURCE_ID,
                    "limit": "100",
                },
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.5.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(
                f"{PROVIDER_NAME} locations: {err}"
            ) from err

        records = (
            payload.get("result", {}).get("records")
            if isinstance(payload, dict)
            else None
        )
        if not isinstance(records, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid location response")
        return [row for row in records if isinstance(row, dict)]

    @staticmethod
    def _key(value: str) -> str:
        """Normalize DCC live/static site names for joining."""
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    @classmethod
    def _normalize(
        cls,
        item: dict[str, Any],
        live: dict[str, int],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        name = str(item.get("Site") or item.get("site") or "").strip()
        try:
            lat = float(item.get("Latitude", item.get("latitude")))
            lon = float(item.get("Longitude", item.get("longitude")))
        except (TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        result: dict[str, Any] = {
            "provider": "dublin_dcc",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"dublin:{cls._key(name) or lat}:{lon}",
            "provider_url": PROVIDER_URL,
            "name": name or "Parking",
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "multi_storey",
            "parking_type": "multi_storey",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        key = cls._key(name)
        if key in live:
            result["free_capacity"] = live[key]
            result["has_realtime_data"] = True

        return result
