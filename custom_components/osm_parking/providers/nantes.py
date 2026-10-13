"""Official Nantes Naolib live public garage and Park & Ride feeds."""
from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

BASE = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets"
PUBLIC = "244400404_parkings-publics-nantes-disponibilites"
PARK_RIDE = "244400404_parcs-relais-nantes-metropole-disponibilites"
FRESHNESS_SECONDS = 900


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
        return int(value) if math.isfinite(value) and value >= 0 and value.is_integer() else None
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


def _location(raw: Any) -> tuple[float, float] | None:
    """Opendatasoft geo_point_2d: v1 [lat,lon], v2 {lat,lon}."""
    try:
        if isinstance(raw, dict):
            if "lat" in raw and "lon" in raw:
                lat, lon = float(raw["lat"]), float(raw["lon"])
            elif isinstance(raw.get("coordinates"), (list, tuple)):
                lon, lat = map(float, raw["coordinates"][:2])
            else:
                return None
        elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
            lat, lon = float(raw[0]), float(raw[1])
        else:
            return None
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (ValueError, TypeError, IndexError):
        pass
    return None


class _NantesBase:
    uid = ""
    name = ""
    dataset = ""
    category = ""

    def applies(self, lat: float, lon: float) -> bool:
        return 46.95 <= lat <= 47.50 and -2.05 <= lon <= -1.25

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        try:
            async with session.get(
                f"{BASE}/{self.dataset}/records",
                params={"limit": "100"},
                timeout=15,
                headers={"Accept": "application/json",
                         "User-Agent": "HomeAssistant-OSM-Parking/0.8.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{self.name}: {err}") from err
        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"{self.name}: invalid Opendatasoft records")
        items = [
            item for row in rows
            if (item := self._normalize(row, lat, lon, radius_m)) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid, suggestions=items,
            live_refresh_seconds=120 if items else None,
        )

    @classmethod
    def _normalize(
        cls, row: Any, destination_lat: float,
        destination_lon: float, radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        coords = _location(row.get("location") or row.get("geo_point_2d"))
        if coords is None:
            return None
        lat, lon = coords
        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None
        parking_id = row.get("grp_identifiant") or row.get("idobj")
        if parking_id in (None, ""):
            return None
        item: dict[str, Any] = {
            "provider": cls.uid, "provider_name": cls.name,
            "provider_id": f"{cls.uid}:{parking_id}",
            "provider_url": f"https://data.nantesmetropole.fr/explore/dataset/{cls.dataset}/",
            "name": str(row.get("nom_complet") or row.get("grp_nom") or "Parking"),
            "distance_m": distance, "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": cls.category,
            "parking_type": "park_and_ride" if cls.category == "park_and_ride" else "public_car_park",
            "fee": "unknown", "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Nantes Métropole / Naolib Open Data",
        }
        if row.get("adresse"):
            item["address"] = str(row["adresse"])

        # This counts public SHORT-STAY bays, not all subscriber bays.
        capacity = _count(row.get("grp_exploitation"))
        if capacity is not None:
            item["capacity"] = capacity
            item["capacity_scope"] = "short_stay"

        status = _count(row.get("grp_statut"))
        updated = row.get("grp_horodatage")
        if not _fresh(updated):
            return item
        if status == 1:
            item["opening_status"] = "closed"
        elif status == 2:
            item["opening_status"] = "closed"
            item["access"] = "permit"
            item["status_description"] = "Subscribers only"
        elif status == 5:
            free = _count(row.get("grp_disponible"))
            if free is not None and (capacity is None or free <= capacity):
                item["has_realtime_data"] = True
                item["free_capacity"] = free
                item["realtime_updated_at"] = str(updated)
                if capacity is not None:
                    item["occupied_capacity"] = capacity - free
                threshold = _count(row.get("grp_complet"))
                item["opening_status"] = "full" if (
                    free == 0 or (threshold is not None and free <= threshold)
                ) else "open"
        # Official code 0 means invalid, not zero available bays.
        return item


class NantesPublicParkingProvider(_NantesBase):
    uid = "nantes_public_parking"
    name = "Nantes Naolib Public Parking"
    dataset = PUBLIC
    category = "multi_storey"


class NantesParkAndRideProvider(_NantesBase):
    uid = "nantes_park_and_ride"
    name = "Nantes Naolib Park & Ride"
    dataset = PARK_RIDE
    category = "park_and_ride"
