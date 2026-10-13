"""Toulouse Metropole BNLS static inventory; ODS v2/v1 are equivalent routes."""
from __future__ import annotations
import asyncio
from time import monotonic
from typing import Any
from aiohttp import ClientSession
from .base import ProviderFetchResult
from .paris import ParisBnlsProvider, PROVIDER_URL as PARIS_URL
from .resilient_http import Endpoint, EndpointPool

PROVIDER_URL = 'https://data.toulouse-metropole.fr/explore/dataset/parcs-de-stationnement/'


class ToulouseParkingProvider:
    uid = 'toulouse_bnls'
    name = 'Toulouse Métropole Open Data / BNLS'
    fetch_timeout = 18

    def __init__(self):
        self._cache = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()
        self._endpoints = EndpointPool((
            Endpoint('https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/parcs-de-stationnement/records', {'limit': '100'}),
            Endpoint('https://data.toulouse-metropole.fr/api/records/1.0/search/', {'dataset': 'parcs-de-stationnement', 'rows': '1000'}),
        ))

    def applies(self, lat, lon):
        return 43.40 <= lat <= 43.80 and 1.15 <= lon <= 1.70

    @staticmethod
    def _normalize(row, lat, lon, radius):
        item = ParisBnlsProvider._normalize(row, lat, lon, radius)
        if item is None or not (43.40 <= item['latitude'] <= 43.80 and 1.15 <= item['longitude'] <= 1.70):
            return None
        item.update(provider='toulouse_bnls', provider_name=ToulouseParkingProvider.name,
                    provider_id='toulouse-bnls:' + str(row['id']),
                    source_attribution='Toulouse Métropole Open Data')
        if item.get('provider_url') == PARIS_URL:
            item['provider_url'] = PROVIDER_URL
        return item

    @staticmethod
    def _catalog(payload):
        if not isinstance(payload, dict):
            raise ValueError('Invalid ODS payload')
        if isinstance(payload.get('results'), list):
            rows, total = payload['results'], payload.get('total_count')
        elif isinstance(payload.get('records'), list):
            rows = [r.get('fields') for r in payload['records'] if isinstance(r, dict)]
            total = payload.get('nhits')
        else:
            raise ValueError('Invalid ODS record list')
        if not rows or len(rows) > 1000 or (isinstance(total, int) and total > len(rows)):
            raise ValueError('Empty or truncated inventory')
        valid = [r for r in rows if ToulouseParkingProvider._normalize(r, 43.60, 1.44, 40000) is not None]
        if not valid:
            raise ValueError('No usable Toulouse facility records')
        return valid

    async def async_fetch(self, session: ClientSession, lat: float, lon: float,
                          radius_m: int, options: dict[str, Any] | None = None):
        async with self._lock:
            if self._cache is None or monotonic() - self._loaded_at >= 86400:
                self._cache = await self._endpoints.fetch(session, self._catalog)
                self._loaded_at = monotonic()
        rows = [item for row in self._cache if (item := self._normalize(row, lat, lon, radius_m)) is not None]
        return ProviderFetchResult(self.uid, rows)
