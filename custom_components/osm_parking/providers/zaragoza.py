"""Official Zaragoza municipality public-car-park inventory (static API).

The Zaragoza map's VINCI occupancy and estimated street-zone occupancy are
separate services. No unverified 'live' counts are inferred from this API.
"""

from __future__ import annotations

import asyncio
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://www.zaragoza.es/sede/servicio/"
    "urbanismo-infraestructuras/equipamiento/aparcamiento-publico.json"
)
PROVIDER_NAME = "Ayuntamiento de Zaragoza Open Data"
PROVIDER_URL = "https://www.zaragoza.es/sede/servicio/catalogo/55"
CACHE_SECONDS = 24 * 60 * 60
PAGE_SIZE = 500
MAX_RECORDS = 3000


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


class ZaragozaParkingProvider:
    """Zaragoza municipality parking sites, not estimated occupancy zones."""

    uid = "zaragoza_public"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return 41.42 <= lat <= 41.85 and -1.24 <= lon <= -0.54

    async def _records(self, session: ClientSession) -> list[dict[str, Any]]:
        if self._cache is not None and monotonic() - self._loaded_at < CACHE_SECONDS:
            return self._cache
        async with self._lock:
            if self._cache is not None and monotonic() - self._loaded_at < CACHE_SECONDS:
                return self._cache

            records: list[dict[str, Any]] = []
            start = 0
            while start < MAX_RECORDS:
                try:
                    async with session.get(
                        ENDPOINT,
                        params={"srsname": "wgs84", "rows": str(PAGE_SIZE), "start": str(start)},
                        timeout=20,
                        headers={
                            "Accept": "application/json",
                            "User-Agent": "HomeAssistant-OSM-Parking/1.1.0",
                        },
                    ) as response:
                        response.raise_for_status()
                        payload = await response.json(content_type=None)
                except (ClientError, TimeoutError, ValueError) as err:
                    raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

                rows = payload.get("result") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise RuntimeError(f"{PROVIDER_NAME}: invalid municipal response")
                records.extend(item for item in rows if isinstance(item, dict))
                start += len(rows)
                total = payload.get("totalCount")
                if not rows or len(rows) < PAGE_SIZE:
                    break
                if isinstance(total, int) and start >= total:
                    break
            else:
                raise RuntimeError(f"{PROVIDER_NAME}: result exceeds safe paging limit")
            if not records:
                raise RuntimeError(f"{PROVIDER_NAME}: empty municipal parking catalog")
            self._cache = records
            self._loaded_at = monotonic()
            return records

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        records = await self._records(session)
        suggestions = [
            normalized
            for record in records
            if (normalized := self._normalize(record, lat, lon, radius_m)) is not None
        ]
        return ProviderFetchResult(provider=self.uid, suggestions=suggestions)

    @staticmethod
    def _normalize(
        record: Any,
        dest_lat: float,
        dest_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        props = record.get("properties") if isinstance(record.get("properties"), dict) else record
        geometry = record.get("geometry") or props.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            return None
        coords = geometry.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return None
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, OverflowError):
            return None
        # Zaragoza defaults to UTM30: never mistake those metres for degrees.
        if not (math.isfinite(lat) and math.isfinite(lon) and 41 <= lat <= 42 and -2 <= lon <= 0):
            return None
        distance = round(haversine_m(dest_lat, dest_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = props.get("id") or record.get("id") or props.get("@id")
        if parking_id in (None, ""):
            return None
        name = str(props.get("title") or props.get("name") or "Aparcamiento público")
        kind = str(props.get("tipo") or props.get("type") or "").casefold()
        if "subterráneo" in kind or "subterraneo" in kind:
            category = "underground"
        elif "superficie" in kind:
            category = "open"
        elif "disuasorio" in kind or "intermodal" in kind:
            category = "park_and_ride"
        else:
            category = "other"
        result: dict[str, Any] = {
            "provider": "zaragoza",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"zaragoza:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": kind or "off_street",
            "fee": "unknown",
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Ayuntamiento de Zaragoza Open Data",
        }
        for source, target in (
            ("address", "address"),
            ("address_string", "address"),
            ("openingHours", "opening_hours"),
        ):
            if props.get(source) not in (None, "") and target not in result:
                result[target] = str(props[source])
        for source in ("plazas", "capacidad", "capacity"):
            count = _count(props.get(source))
            if count is not None:
                result["capacity"] = count
                break
        return result
