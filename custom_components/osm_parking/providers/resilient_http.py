"""Bounded, schema-validated fallback reads of the SAME official dataset.

Alternate formats on one host are not independent mirrors. Endpoints are
code-owned, never obtained from untrusted API responses.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
import json
import math
from time import monotonic
from typing import Any, Callable

MAX_BYTES = 8 * 1024 * 1024


class SourceUnavailable(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class Endpoint:
    url: str
    params: dict[str, str]


class EndpointPool:
    """Try equivalents only after transport or response validation fails."""
    def __init__(self, endpoints: tuple[Endpoint, ...]) -> None:
        self.endpoints = endpoints
        self._retry_at: dict[str, float] = {}
        self.last_source: str | None = None

    async def fetch(self, session: Any, validate: Callable[[Any], Any]) -> Any:
        errors: list[str] = []
        self.last_source = None
        eligible = [e for e in self.endpoints if monotonic() >= self._retry_at.get(e.url, 0)]
        if not eligible:
            raise SourceUnavailable('Equivalent endpoints are cooling down', max(1, math.ceil(min(self._retry_at.values()) - monotonic())))
        for endpoint in eligible:
            try:
                async with asyncio.timeout(8):
                    async with session.get(
                        endpoint.url, params=endpoint.params, timeout=7,
                        headers={'Accept': 'application/json, application/geo+json',
                                 'User-Agent': 'HomeAssistant-OSM-Parking'},
                    ) as response:
                        if response.status == 429:
                            # Do not circumvent one host's rate limit via another route.
                            try:
                                retry = min(86400, max(60, int(response.headers.get('Retry-After', '300'))))
                            except (TypeError, ValueError, OverflowError):
                                retry = 300
                            for other in self.endpoints:
                                self._retry_at[other.url] = monotonic() + retry
                            raise RuntimeError('Rate limited')
                        response.raise_for_status()
                        chunks = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            chunks.extend(chunk)
                            if len(chunks) > MAX_BYTES:
                                raise ValueError('Response exceeds safe size')
                        payload = json.loads(chunks)
                        result = validate(payload)
                        self.last_source = endpoint.url
                        self._retry_at.pop(endpoint.url, None)
                        return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Renew an expired cooldown without shortening Retry-After.
                # No exception bodies, credentials or raw server error pages.
                errors.append(type(exc).__name__)
                self._retry_at[endpoint.url] = max(
                    self._retry_at.get(endpoint.url, 0), monotonic() + 300,
                )
                if all(monotonic() < self._retry_at.get(e.url, 0) for e in self.endpoints):
                    break
        raise SourceUnavailable('No usable equivalent endpoint: ' + ', '.join(errors), max(1, math.ceil(min(self._retry_at.values()) - monotonic())))
