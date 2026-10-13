from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Protocol

from aiohttp import ClientSession


@dataclass(slots=True)
class ProviderFetchResult:
    """Normalized provider response."""

    provider: str
    suggestions: list[dict[str, Any]]
    live_refresh_seconds: int | None = None


class ParkingProvider(Protocol):
    """Interface implemented by supplemental parking providers."""

    uid: str
    name: str

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether this provider is relevant for these coordinates."""

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch and normalize nearby parking."""


def haversine_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return great-circle distance in metres."""
    radius = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bounding_box(
    lat: float,
    lon: float,
    radius_m: int,
) -> tuple[float, float, float, float]:
    """Return south, west, north, east for a radius around a point."""
    lat_delta = radius_m / 111_320.0
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.01)
    lon_delta = radius_m / (111_320.0 * cos_lat)
    return (
        max(-90.0, lat - lat_delta),
        max(-180.0, lon - lon_delta),
        min(90.0, lat + lat_delta),
        min(180.0, lon + lon_delta),
    )


def navigation_url(lat: float, lon: float) -> str:
    """Return a generic navigation URL."""
    return (
        "https://www.google.com/maps/dir/?api=1&destination="
        f"{lat:.7f},{lon:.7f}&travelmode=driving"
    )


def geo_uri(lat: float, lon: float) -> str:
    """Return geo URI."""
    return f"geo:{lat:.7f},{lon:.7f}?q={lat:.7f},{lon:.7f}"
