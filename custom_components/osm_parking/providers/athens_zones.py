"""Automatic Athens GIS: emit only validated, geographically relevant zones.

The legacy setup switch is ignored. Unreachable or unusable GIS is isolated
and rechecked by the provider supervisor. Never infer permission, fees or
available bays from a zone. Same-host WFS routes are route/format fallback,
not independent publishers.
"""
from __future__ import annotations
import asyncio
from time import monotonic
from typing import Any
from aiohttp import ClientSession
from .base import ProviderFetchResult, bounding_box
from .resilient_http import Endpoint, EndpointPool
from .zone_geometry import validated_geometry, intersects_bbox

ENDPOINT = 'https://gis.cityofathens.gr/geoserver/ows'
PROVIDER_NAME = 'City of Athens Controlled Parking Zones'
PROVIDER_URL = 'https://opendata.cityofathens.gr/en/dataset/gis-athens-86d8dc0c-25a9-11ec-9787-0242ac130009'
CACHE_SECONDS = 24 * 3600
ATHENS_BOUNDS = (37.80, 23.55, 38.20, 23.95)
PARAMS = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
          'typeNames': 'geonode:zones_stathmeusis', 'outputFormat': 'application/json',
          'srsName': 'EPSG:4326', 'count': '500'}


def _normalize(feature: Any, bbox: tuple) -> dict | None:
    if not isinstance(feature, dict):
        return None
    geometry = validated_geometry(feature.get('geometry'), ATHENS_BOUNDS)
    if geometry is None or not intersects_bbox(geometry, bbox):
        return None
    props = feature.get('properties')
    props = props if isinstance(props, dict) else {}
    return {'type': 'Feature', 'geometry': geometry, 'properties': {
        'id': str(props.get('id') or props.get('objectid') or feature.get('id') or ''),
        'name': str(props.get('name') or props.get('Name') or props.get('zone') or props.get('zonh') or 'Ζώνη ελεγχόμενης στάθμευσης')[:300],
        'record_type': 'zone', 'zone_type': 'controlled_parking', 'availability_kind': 'zone',
        'provider': 'athens_city_zones', 'provider_name': PROVIDER_NAME,
        'provider_url': PROVIDER_URL, 'source_attribution': 'City of Athens Open Data',
        'parking_rules': 'consult_official_signage',
    }}


def _catalog(payload: Any) -> list[dict]:
    if not isinstance(payload, dict) or payload.get('type') != 'FeatureCollection':
        raise ValueError('Expected WFS FeatureCollection')
    crs = payload.get('crs')
    if crs:
        name = str(crs.get('properties', {}).get('name', '')) if isinstance(crs, dict) else ''
        if not (name.endswith('4326') or name.upper().endswith('CRS84') or name.upper().endswith('CRS:84')):
            raise ValueError('Unsupported CRS')
    features = payload.get('features')
    if not isinstance(features, list) or not features or len(features) > 500:
        raise ValueError('Empty or invalid zone inventory')
    matched = payload.get('numberMatched')
    if str(matched).isdigit() and int(matched) > len(features):
        raise ValueError('Truncated zone inventory')
    zones = [z for feature in features if (z := _normalize(feature, ATHENS_BOUNDS)) is not None]
    if not zones:
        raise ValueError('No usable Athens polygons')
    return zones


class AthensParkingZonesProvider:
    uid = 'athens_city_zones'
    name = PROVIDER_NAME
    fetch_timeout = 18

    def __init__(self) -> None:
        self._cache: list[dict] | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()
        self._endpoints = EndpointPool((
            Endpoint(ENDPOINT, PARAMS),
            Endpoint('https://gis.cityofathens.gr/geoserver/wfs', PARAMS),
        ))

    def applies(self, lat: float, lon: float) -> bool:
        return 37.90 <= lat <= 38.08 and 23.62 <= lon <= 23.87

    async def async_fetch(self, session: ClientSession, lat: float, lon: float,
                          radius_m: int, options: dict[str, Any] | None = None) -> ProviderFetchResult:
        async with self._lock:
            if self._cache is None or monotonic() - self._loaded_at >= CACHE_SECONDS:
                zones = await self._endpoints.fetch(session, _catalog)
                self._cache, self._loaded_at = zones, monotonic()
        bbox = bounding_box(lat, lon, radius_m)
        zones = [z for z in self._cache if intersects_bbox(z['geometry'], bbox)]
        return ProviderFetchResult(provider=self.uid, suggestions=[], zones=zones)
