"""Live public parking from Métropole de Lyon OGC API Features (2026)."""
from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, bounding_box, geo_uri, haversine_m, navigation_url

ENDPOINT = (
    "https://data.grandlyon.com/geoserver/ogc/features/v1/collections/"
    "metropole-de-lyon:parkings-de-la-metropole-de-lyon-disponibilites-temps-reel-v2/items"
)
PROVIDER_NAME = "Métropole de Lyon Open Data"
PROVIDER_URL = "https://www.data.gouv.fr/datasets/parkings-de-la-metropole-de-lyon-disponibilites-temps-reel"
FRESHNESS_SECONDS = 900


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
    except (TypeError, ValueError):
        return None


def _fresh(value: Any) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return False
        age = (datetime.now(UTC) - dt.astimezone(UTC)).total_seconds()
        return -300 <= age <= FRESHNESS_SECONDS
    except (ValueError, TypeError, OverflowError):
        return False


class LyonParkingProvider:
    uid = "lyon_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        return 45.40 <= lat <= 46.05 and 4.55 <= lon <= 5.25

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        south, west, north, east = bounding_box(lat, lon, radius_m)
        try:
            async with session.get(
                ENDPOINT,
                params={
                    "f": "json",
                    "bbox": f"{west:.7f},{south:.7f},{east:.7f},{north:.7f}",
                    "limit": "500",
                },
                timeout=20,
                headers={"Accept": "application/geo+json, application/json",
                         "User-Agent": "HomeAssistant-OSM-Parking/0.8.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid GeoJSON features")
        items = [
            item for feature in features
            if (item := self._normalize(feature, lat, lon, radius_m)) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid, suggestions=items,
            live_refresh_seconds=120 if items else None,
        )

    @staticmethod
    def _normalize(
        feature: Any, destination_lat: float,
        destination_lon: float, radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(feature, dict):
            return None
        geometry, props = feature.get("geometry"), feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(props, dict):
            return None
        coords = geometry.get("coordinates")
        if geometry.get("type") != "Point" or not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return None
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            return None
        if not (math.isfinite(lat) and math.isfinite(lon)
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None
        parking_id = props.get("id") or feature.get("id")
        if parking_id in (None, ""):
            return None

        name = str(props.get("nom") or "Parking")
        layout = str(props.get("type_ouvrage") or "").casefold()
        if "relais" in name.casefold() or "p+r" in name.casefold():
            category = "park_and_ride"
        elif "souterrain" in layout:
            category = "underground"
        elif "surface" in layout or "plein air" in layout:
            category = "open"
        else:
            category = "multi_storey"
        free_parking = props.get("gratuit")
        fee = "no" if free_parking is True else "yes" if free_parking is False else "unknown"
        if fee == "yes" and category != "park_and_ride":
            category = "paid"

        item: dict[str, Any] = {
            "provider": "lyon", "provider_name": PROVIDER_NAME,
            "provider_id": f"lyon:{parking_id}", "provider_url": PROVIDER_URL,
            "name": name, "distance_m": distance,
            "latitude": round(lat, 7), "longitude": round(lon, 7),
            "category": category, "parking_type": layout or "off_street",
            "fee": fee, "access": "unknown", "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon), "geo_uri": geo_uri(lat, lon),
            "source_attribution": PROVIDER_NAME,
        }
        for key, out in (("gestionnaire", "operator"), ("adresse", "address")):
            if props.get(key) not in (None, ""):
                item[out] = str(props[key])
        capacity = _count(props.get("nb_places"))
        if capacity is not None:
            item["capacity"] = capacity
        for key, out in (("nb_pmr", "accessible_capacity"), ("nb_voitures_electriques", "ev_capacity")):
            count = _count(props.get(key))
            if count is not None:
                item[out] = count
        link = str(props.get("url") or "")
        if link.startswith(("https://", "http://")):
            item["provider_url"] = link

        tariff = props.get("tarif_1h")
        try:
            amount = float(tariff) if tariff is not None else -1
            if math.isfinite(amount) and amount >= 0:
                item["price"] = f"{amount:.2f} € / 1 h"
        except (TypeError, ValueError):
            pass

        updated_at = props.get("last_update")
        if _fresh(updated_at):
            free = _count(props.get("places_disponibles"))
            if free is not None and (capacity is None or free <= capacity):
                item["has_realtime_data"] = True
                item["free_capacity"] = free
                item["realtime_updated_at"] = str(updated_at)
                if capacity is not None:
                    item["occupied_capacity"] = capacity - free
            status = str(props.get("etat") or "").strip().casefold()
            if status in {"ouvert", "ouverte", "open", "available"}:
                item["opening_status"] = "open"
            elif status in {"ferme", "fermée", "fermé", "closed"}:
                item["opening_status"] = "closed"
            elif status in {"complet", "complete", "full"}:
                item["opening_status"] = "full"
        return item
