from __future__ import annotations

import csv
import io
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

CATALOG_URL = (
    "https://datosabiertos.malaga.eu/recursos/aparcamientos/"
    "ocupappublicosmun/catalogo.csv"
)
OCCUPANCY_URL = (
    "https://datosabiertos.malaga.eu/recursos/aparcamientos/"
    "ocupappublicosmun/ocupappublicosmun.csv"
)
PROVIDER_NAME = "Ayuntamiento de Málaga Open Data"
PROVIDER_URL = (
    "https://datosabiertos.malaga.eu/dataset/"
    "ocupacion-aparcamientos-publicos-municipales"
)
CATALOG_CACHE_SECONDS = 24 * 60 * 60


class MalagaParkingProvider:
    """Minute-updated municipal parking availability from Málaga."""

    uid = "malaga_open_data"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._catalog: dict[str, dict[str, Any]] = {}
        self._catalog_loaded_at = 0.0

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside Málaga city."""
        return 36.55 <= lat <= 36.90 and -4.75 <= lon <= -4.15

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Join the official live occupancy feed to its official catalog."""
        catalog = await self._async_catalog(session)
        occupancy = await self._async_csv(session, OCCUPANCY_URL)

        suggestions: list[dict[str, Any]] = []
        for row in occupancy:
            parking_id = str(row.get("id") or "").strip()
            if not parking_id:
                continue
            static = catalog.get(parking_id)
            if static is None:
                # Never invent coordinates for a live row that is absent from
                # the municipality's published catalog.
                continue

            normalized = self._normalize(
                parking_id,
                static,
                row,
                lat,
                lon,
                radius_m,
            )
            if normalized is not None:
                suggestions.append(normalized)

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if suggestions else None,
        )

    async def _async_catalog(
        self,
        session: ClientSession,
    ) -> dict[str, dict[str, Any]]:
        now = monotonic()
        if (
            self._catalog
            and now - self._catalog_loaded_at < CATALOG_CACHE_SECONDS
        ):
            return self._catalog

        rows = await self._async_csv(session, CATALOG_URL)
        catalog = {
            str(row.get("id") or "").strip(): row
            for row in rows
            if str(row.get("id") or "").strip()
        }
        if not catalog:
            raise RuntimeError(f"{PROVIDER_NAME}: parking catalog was empty")

        self._catalog = catalog
        self._catalog_loaded_at = now
        return catalog

    async def _async_csv(
        self,
        session: ClientSession,
        url: str,
    ) -> list[dict[str, str]]:
        try:
            async with session.get(
                url,
                timeout=15,
                headers={
                    "Accept": "text/csv,*/*",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.7.0",
                },
            ) as response:
                response.raise_for_status()
                raw = await response.read()
        except (ClientError, TimeoutError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        text: str | None = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise RuntimeError(f"{PROVIDER_NAME}: could not decode CSV")

        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict[str, str]] = []
        for original in reader:
            normalized = {
                str(key or "").strip().casefold(): str(value or "").strip()
                for key, value in original.items()
            }
            rows.append(normalized)
        return rows

    @staticmethod
    def _normalize(
        parking_id: str,
        static: dict[str, str],
        live: dict[str, str],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        try:
            lat = float(static["latitude"].replace(",", "."))
            lon = float(static["longitude"].replace(",", "."))
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        try:
            free = int(float(str(live.get("libres") or "").replace(",", ".")))
        except (TypeError, ValueError):
            return None
        if free < 0:
            return None

        result: dict[str, Any] = {
            "provider": "malaga",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"malaga:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(
                static.get("nombre")
                or static.get("name")
                or parking_id
            ),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "other",
            "parking_type": "municipal_car_park",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": True,
            "free_capacity": free,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Ayuntamiento de Málaga Open Data",
        }

        address = (
            static.get("direccion")
            or static.get("address")
            or ""
        ).strip()
        if address:
            result["address"] = address

        return result
