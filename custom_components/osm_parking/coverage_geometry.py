"""Offline point-in-polygon checks for bundled authoritative coverage geometry.

Coverage GeoJSON is generated during development from the original public
authority dataset and shipped with the integration. Runtime provider selection
therefore never needs a second network service merely to decide whether a
provider should be queried.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

_COVERAGE_DIR = Path(__file__).parent / "data" / "coverage"


@dataclass(frozen=True)
class _Polygon:
    exterior: tuple[tuple[float, float], ...]
    holes: tuple[tuple[tuple[float, float], ...], ...]
    bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class CoverageGeometry:
    """Prepared Polygon/MultiPolygon plus provenance metadata."""

    polygons: tuple[_Polygon, ...]
    bounds: tuple[float, float, float, float]
    properties: dict[str, Any]

    def contains(self, latitude: float, longitude: float) -> bool:
        """Return whether a WGS84 point falls inside the bundled coverage."""
        try:
            lat = float(latitude)
            lon = float(longitude)
        except (TypeError, ValueError, OverflowError):
            return False
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            return False

        west, south, east, north = self.bounds
        if not (west <= lon <= east and south <= lat <= north):
            return False

        point = (lon, lat)
        for polygon in self.polygons:
            pwest, psouth, peast, pnorth = polygon.bounds
            if not (pwest <= lon <= peast and psouth <= lat <= pnorth):
                continue
            if not _ring_contains(point, polygon.exterior):
                continue
            if any(_ring_contains(point, hole) for hole in polygon.holes):
                continue
            return True
        return False


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    """Treat geometry boundaries as inside coverage."""
    px, py = point
    ax, ay = start
    bx, by = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > 1e-10:
        return False
    return (
        min(ax, bx) - 1e-10 <= px <= max(ax, bx) + 1e-10
        and min(ay, by) - 1e-10 <= py <= max(ay, by) + 1e-10
    )


def _ring_contains(
    point: tuple[float, float],
    ring: tuple[tuple[float, float], ...],
) -> bool:
    """Ray-casting point-in-ring with explicit boundary inclusion."""
    x, y = point
    inside = False
    previous = ring[-1]
    for current in ring:
        if _point_on_segment(point, previous, current):
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _ring(raw: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, list) or len(raw) < 4 or len(raw) > 100_000:
        raise ValueError("Invalid coverage ring")
    points: list[tuple[float, float]] = []
    for value in raw:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            raise ValueError("Invalid coverage point")
        lon, lat = float(value[0]), float(value[1])
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            raise ValueError("Invalid coverage coordinate")
        points.append((lon, lat))
    if points[0] != points[-1]:
        raise ValueError("Coverage ring must be closed")
    return tuple(points)


def _polygon(raw: Any) -> _Polygon:
    if not isinstance(raw, list) or not raw or len(raw) > 1000:
        raise ValueError("Invalid coverage polygon")
    exterior = _ring(raw[0])
    holes = tuple(_ring(value) for value in raw[1:])
    xs = [point[0] for point in exterior]
    ys = [point[1] for point in exterior]
    return _Polygon(
        exterior=exterior,
        holes=holes,
        bounds=(min(xs), min(ys), max(xs), max(ys)),
    )


@lru_cache(maxsize=16)
def load_coverage(filename: str) -> CoverageGeometry:
    """Load and validate a bundled GeoJSON coverage file exactly once."""
    if "/" in filename or "\\" in filename or not filename.endswith(".geojson"):
        raise ValueError("Invalid coverage filename")
    path = _COVERAGE_DIR / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "Feature":
        raise ValueError("Coverage must be one GeoJSON Feature")
    geometry = payload.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("Coverage has no geometry")
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        polygons = (_polygon(coordinates),)
    elif kind == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("Invalid coverage multipolygon")
        polygons = tuple(_polygon(value) for value in coordinates)
    else:
        raise ValueError("Coverage must be Polygon or MultiPolygon")
    if not polygons:
        raise ValueError("Coverage is empty")
    west = min(value.bounds[0] for value in polygons)
    south = min(value.bounds[1] for value in polygons)
    east = max(value.bounds[2] for value in polygons)
    north = max(value.bounds[3] for value in polygons)
    props = payload.get("properties")
    if not isinstance(props, dict):
        props = {}
    return CoverageGeometry(
        polygons=polygons,
        bounds=(west, south, east, north),
        properties=dict(props),
    )
