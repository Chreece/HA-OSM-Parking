"""City of Paris BNLS public car parks, entrances, capacity and tariffs.

Official Opendatasoft v2.1 records. Static inventory (updated roughly twice
yearly), never parking vacancies. Pagination and time-limited cache ensure a
full municipal inventory without re-downloading it every destination change.
"""

from __future__ import annotations

import asyncio
import math
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

DATASET = "stationnement-en-ouvrage"
ENDPOINT = f"https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/{DATASET}/records"
PROVIDER_NAME = "Ville de Paris Open Data / BNLS"
PROVIDER_URL = "https://opendata.paris.fr/explore/dataset/stationnement-en-ouvrage/"
CACHE_SECONDS = 24 * 60 * 60
PAGE_SIZE = 100
MAX_RECORDS = 2000


def _positive_count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if math.isfinite(number) and number >= 0 and number.is_integer():
        return int(number)
    return None


def _coordinates(record: dict[str, Any]) -> tuple[float, float] | None:
    try:
        if record.get("xlong") is not None and record.get("ylat") is not None:
            lat, lon = float(record["ylat"]), float(record["xlong"])
        else:
            point = record.get("geo_point_2d")
            if isinstance(point, dict):
                lat, lon = float(point["lat"]), float(point["lon"])
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lat, lon = float(point[0]), float(point[1])
            else:
                shape = record.get("geo_shape")
                coords = shape.get("coordinates") if isinstance(shape, dict) else None
                if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    return None
                lon, lat = float(coords[0]), float(coords[1])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


class ParisBnlsProvider:
    """Paris city-operated/concession public garages; no realtime vacancies."""

    uid = "paris_bnls"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return 48.69 <= lat <= 49.04 and 2.16 <= lon <= 2.64

    async def _records(self, session: ClientSession) -> list[dict[str, Any]]:
        if self._cache is not None and monotonic() - self._cached_at < CACHE_SECONDS:
            return self._cache
        async with self._lock:
            if self._cache is not None and monotonic() - self._cached_at < CACHE_SECONDS:
                return self._cache

            records: list[dict[str, Any]] = []
            offset = 0
            while offset < MAX_RECORDS:
                try:
                    async with session.get(
                        ENDPOINT,
                        params={"limit": str(PAGE_SIZE), "offset": str(offset)},
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

                batch = payload.get("results") if isinstance(payload, dict) else None
                if not isinstance(batch, list):
                    raise RuntimeError(f"{PROVIDER_NAME}: invalid ODS records")
                records.extend(item for item in batch if isinstance(item, dict))
                offset += len(batch)
                if not batch or len(batch) < PAGE_SIZE:
                    break
                count = payload.get("total_count")
                if isinstance(count, int) and offset >= count:
                    break
            else:
                raise RuntimeError(f"{PROVIDER_NAME}: result exceeds safe paging limit")
            if not records:
                raise RuntimeError(f"{PROVIDER_NAME}: empty official inventory")
            self._cache = records
            self._cached_at = monotonic()
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
        uid = str(record.get("id") or "").strip()
        coords = _coordinates(record)
        if not uid or coords is None:
            return None
        lat, lon = coords
        distance = round(haversine_m(dest_lat, dest_lon, lat, lon))
        if distance > radius_m:
            return None

        layout = str(record.get("type_ouvrage") or "").casefold()
        user_type = str(record.get("type_usagers") or "").casefold()
        if (_positive_count(record.get("nb_pr")) or 0) > 0:
            category = "park_and_ride"
        elif "souterrain" in layout or "enterr" in layout:
            category = "underground"
        elif "surface" in layout or "plein air" in layout:
            category = "open"
        elif "ouvrage" in layout or "étage" in layout or "etage" in layout:
            category = "multi_storey"
        else:
            category = "other"

        gratuit = record.get("gratuit")
        if gratuit is True or str(gratuit).strip() == "1":
            fee = "no"
        elif gratuit is False or str(gratuit).strip() == "0":
            fee = "yes"
        else:
            fee = "unknown"
        if fee == "yes" and category not in {"park_and_ride", "underground"}:
            category = "paid"

        private_only = (
            any(term in user_type for term in ("abonn", "résident", "resident"))
            and not any(term in user_type for term in ("public", "visiteur", "rotatif", "horaire"))
        )
        result: dict[str, Any] = {
            "provider": "paris_bnls",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"paris-bnls:{uid}",
            "provider_url": PROVIDER_URL,
            "name": str(record.get("nom") or f"Parking {uid}"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": layout or "off_street",
            "fee": fee,
            "access": "permit" if private_only else "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Ville de Paris Open Data (ODbL / BNLS)",
        }
        if record.get("adresse"):
            result["address"] = str(record["adresse"])
        url = str(record.get("url") or "")
        if url.startswith("https://"):
            result["provider_url"] = url
        for source, target in (
            ("nb_places", "capacity"),
            ("nb_pmr", "accessible_capacity"),
            ("nb_voitures_electriques", "ev_capacity"),
        ):
            count = _positive_count(record.get(source))
            if count is not None:
                result[target] = count

        tariff = record.get("tarif_1h")
        try:
            amount = float(tariff) if tariff is not None else float("nan")
            if math.isfinite(amount) and amount >= 0:
                result["price"] = f"{amount:.2f} € / 1 h"
        except (TypeError, ValueError, OverflowError):
            pass
        return result
