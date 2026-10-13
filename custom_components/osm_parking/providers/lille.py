"""Official Métropole Européenne de Lille parking availability, WFS/GeoJSON."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://data.lillemetropole.fr/geoserver/wfs"
PROVIDER_NAME = "Métropole Européenne de Lille Open Data"
PROVIDER_URL = "https://data.lillemetropole.fr/catalogue/dataset/disponibilite-parkings"
LIVE_MAX_AGE_SECONDS = 15 * 60
LOCAL_TZ = ZoneInfo("Europe/Paris")
OPEN_STATUSES = {"ouvert", "ouverte", "open", "disponible", "en service", "en_service"}
CLOSED_STATUSES = {
    "ferme", "fermé", "fermée", "fermee", "closed", "hors service",
    "hors_service", "hs", "indisponible", "fermeture",
}
FULL_STATUSES = {"complet", "complete", "full", "saturé", "sature"}


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


def _fresh_datetime(raw: Any) -> str | None:
    """MEL's naive municipal timestamps refer to Europe/Paris, not UTC."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        utc = dt.astimezone(UTC)
        age = (datetime.now(UTC) - utc).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return utc.isoformat()
    except (ValueError, OverflowError, TypeError):
        return None
    return None


class LilleParkingProvider:
    uid = "lille_mel"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        return 50.25 <= lat <= 51.05 and 2.65 <= lon <= 3.45

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        try:
            async with session.get(
                ENDPOINT,
                params={
                    "service": "WFS",
                    "request": "GetFeature",
                    "version": "2.0.0",
                    "typeNames": "mel_mobilite_et_transport:parking",
                    "outputFormat": "application/json",
                    "count": "500",
                },
                timeout=20,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.9.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid WFS GeoJSON")

        suggestions = [
            item for feature in features
            if (item := self._normalize(feature, lat, lon, radius_m)) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        feature: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            return None
        props = feature["properties"]
        coords = None
        geometry = feature.get("geometry")
        if isinstance(geometry, dict) and geometry.get("type") == "Point":
            location = geometry.get("coordinates")
            if isinstance(location, (list, tuple)) and len(location) >= 2:
                coords = (location[1], location[0])
        if coords is None:
            coords = (props.get("latitude"), props.get("longitude"))
        try:
            lat, lon = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, OverflowError):
            return None
        if not (
            math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180
        ):
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
        elif "surface" in layout:
            category = "open"
        elif "ouvrage" in layout or "etage" in layout or "étage" in layout:
            category = "multi_storey"
        else:
            category = "other"

        item: dict[str, Any] = {
            "provider": "lille",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"lille:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": layout or "off_street",
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Métropole Européenne de Lille (Licence Ouverte 2.0)",
        }

        address = props.get("adresse")
        city = props.get("ville")
        if address or city:
            item["address"] = ", ".join(str(v) for v in (address, city) if v)

        capacity = _count(props.get("nbr_total"))
        if capacity is not None:
            item["capacity"] = capacity

        updated_at = _fresh_datetime(props.get("dtdate"))
        if updated_at is None:
            return item

        raw_status = str(props.get("etat") or "").strip().casefold()
        if raw_status in CLOSED_STATUSES:
            item["opening_status"] = "closed"
            return item
        if raw_status in FULL_STATUSES:
            item["opening_status"] = "full"
            return item

        # Status codes and undocumented values are deliberately NOT guessed.
        if raw_status not in OPEN_STATUSES:
            return item

        free = _count(props.get("nbr_libre"))
        if free is None or (capacity is not None and free > capacity):
            return item
        item["has_realtime_data"] = True
        item["free_capacity"] = free
        item["realtime_updated_at"] = updated_at
        item["opening_status"] = "full" if free == 0 else "open"
        if capacity is not None:
            item["occupied_capacity"] = capacity - free
        return item
