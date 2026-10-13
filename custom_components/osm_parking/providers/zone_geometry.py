"""Validate bounded WGS84 polygons before map rendering or deduplication."""
from __future__ import annotations
import math
from typing import Any


def validated_geometry(geometry: Any, bounds=(-90.0, -180.0, 90.0, 180.0)) -> dict | None:
    if not isinstance(geometry, dict):
        return None
    kind, coordinates = geometry.get('type'), geometry.get('coordinates')
    if kind not in ('Polygon', 'MultiPolygon') or not isinstance(coordinates, list):
        return None
    polygons = [coordinates] if kind == 'Polygon' else coordinates
    if not polygons or len(polygons) > 100:
        return None
    count = 0
    south, west, north, east = bounds
    result = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon or len(polygon) > 100:
            return None
        rings = []
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                return None
            clean = []
            for point in ring:
                count += 1
                if count > 10000 or not isinstance(point, (list, tuple)) or len(point) < 2:
                    return None
                if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in point[:2]):
                    return None
                lon, lat = point[:2]
                if not (math.isfinite(lat) and math.isfinite(lon) and south <= lat <= north and west <= lon <= east):
                    return None
                clean.append([lon, lat])
            if clean[0] != clean[-1] or len(set(tuple(p) for p in clean)) < 3:
                return None
            area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(clean, clean[1:]))
            if abs(area) < 1e-12:
                return None
            rings.append(clean)
        result.append(rings)
    return {'type': kind, 'coordinates': result[0] if kind == 'Polygon' else result}


def intersects_bbox(geometry: dict, bbox: tuple) -> bool:
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    points = [p for poly in polygons for ring in poly for p in ring]
    south, west, north, east = bbox
    return not (max(p[1] for p in points) < south or min(p[1] for p in points) > north
                or max(p[0] for p in points) < west or min(p[0] for p in points) > east)
