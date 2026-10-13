"""Optional City of Athens WFS controlled-parking polygons.

No occupancy, fee, permit eligibility, or time restriction is inferred from
these static geometries. The GIS server is intermittently unavailable;
this provider is disabled by default until the user opts into it.
"""
from __future__ import annotations

from time import monotonic
import math
from typing import Any
from aiohttp import ClientError, ClientSession

from ..const import CONF_ATHENS_ZONES_ENABLED
from .base import ProviderFetchResult, bounding_box

ENDPOINT = "https://gis.cityofathens.gr/geoserver/ows"
PROVIDER_NAME = "City of Athens Controlled Parking Zones"
PROVIDER_URL = "https://opendata.cityofathens.gr/en/dataset/gis-athens-86d8dc0c-25a9-11ec-9787-0242ac130009"
CACHE_SECONDS = 24 * 3600


def _points(value: Any):
    if not isinstance(value, (list, tuple)):
        return
    if len(value) >= 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value[:2]):
        yield value[:2]
    else:
        for child in value:
            yield from _points(child)


def _normalize(feature: Any, bbox: tuple[float, float, float, float]) -> dict[str, Any] | None:
    if not isinstance(feature, dict):
        return None
    geom = feature.get("geometry")
    if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
        return None
    vertices = []
    for point in _points(geom.get("coordinates")):
        try:
            lon, lat = map(float, point[:2])
        except (TypeError, ValueError, OverflowError):
            return None
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        vertices.append((lat, lon))
        if len(vertices) > 10000:
            return None
    if len(vertices) < 4:
        return None

    south, west, north, east = bbox
    if (
        max(x[0] for x in vertices) < south
        or min(x[0] for x in vertices) > north
        or max(x[1] for x in vertices) < west
        or min(x[1] for x in vertices) > east
    ):
        return None
    props = feature.get("properties")
    values = props if isinstance(props, dict) else {}
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "id": str(values.get("id") or values.get("objectid") or feature.get("id") or ""),
            "name": str(values.get("name") or values.get("Name") or values.get("zone") or values.get("zonh") or "Ζώνη ελεγχόμενης στάθμευσης"),
            "record_type": "zone",
            "zone_type": "controlled_parking",
            "availability_kind": "zone",
            "provider": "athens_city_zones",
            "provider_name": PROVIDER_NAME,
            "provider_url": PROVIDER_URL,
            "source_attribution": "City of Athens Open Data",
            "parking_rules": "consult_official_signage",
        },
    }


class AthensParkingZonesProvider:
    uid = "athens_city_zones"
    name = PROVIDER_NAME
    enabled_option = CONF_ATHENS_ZONES_ENABLED
    enabled_default = False

    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] | None = None
        self._loaded_at = 0.0

    def applies(self, lat: float, lon: float) -> bool:
        return 37.90 <= lat <= 38.08 and 23.62 <= lon <= 23.87

    async def async_fetch(
        self, session: ClientSession, lat: float, lon: float,
        radius_m: int, options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        if self._cache is None or monotonic() - self._loaded_at >= CACHE_SECONDS:
            try:
                async with session.get(
                    ENDPOINT,
                    params={
                        "service": "WFS", "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": "geonode:zones_stathmeusis",
                        "outputFormat": "application/json",
                        "srsName": "EPSG:4326", "count": "500",
                    },
                    timeout=25,
                    headers={"Accept": "application/json",
                             "User-Agent": "HomeAssistant-OSM-Parking/1.0.0"},
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err
            raw = payload.get("features") if isinstance(payload, dict) else None
            if not isinstance(raw, list):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid GeoJSON response")
            self._cache = [r for r in raw if isinstance(r, dict)]
            self._loaded_at = monotonic()

        bbox = bounding_box(lat, lon, radius_m)
        zones = [v for raw in self._cache if (v := _normalize(raw, bbox)) is not None]
        return ProviderFetchResult(provider=self.uid, suggestions=[], zones=zones)
