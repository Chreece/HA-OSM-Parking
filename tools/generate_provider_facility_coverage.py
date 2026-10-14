#!/usr/bin/env python3
"""Generate offline applicability coverage from official provider inventories.

Development-only tool. Runtime uses only the bundled GeoJSON polygons and does
not contact these services just to decide whether a provider should run.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.request import Request, urlopen

from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "custom_components" / "osm_parking" / "data" / "coverage"

FINTRAFFIC_URL = "https://parking.fintraffic.fi/api/v1/facilities.geojson?limit=-1"
TFL_URL = "https://api.tfl.gov.uk/Place/Type/CarPark"


def _json(url: str, accept: str = "application/json"):
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "HomeAssistant-OSM-Parking coverage generator",
            "Digitraffic-User": "ha-osm-parking",
        },
    )
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned {response.status}")
        raw = response.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            raise RuntimeError("Coverage source response too large")
    return json.loads(raw)


def _write(filename: str, geom, props: dict):
    if geom.is_empty or not geom.is_valid:
        raise RuntimeError(f"{filename}: generated geometry invalid")
    payload = {
        "type": "Feature",
        "properties": {
            **props,
            "buffer_m": 10_000,
            "generated_at": datetime.now(UTC).isoformat(),
            "generation_note": (
                "Coverage is derived from the provider's own official parking "
                "facility inventory and buffered by the integration's maximum "
                "10 km search radius. Runtime applicability is fully offline."
            ),
        },
        "geometry": mapping(geom),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / filename
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def fintraffic():
    payload = _json(FINTRAFFIC_URL, "application/geo+json")
    if (
        not isinstance(payload, dict)
        or payload.get("type") != "FeatureCollection"
        or payload.get("hasMore") not in (False, None)
        or not isinstance(payload.get("features"), list)
    ):
        raise RuntimeError("Unexpected Fintraffic facility GeoJSON")

    geometries = []
    ids = []
    for feature in payload["features"]:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        capacity = props.get("builtCapacity") if isinstance(props, dict) else None
        if not isinstance(capacity, dict):
            continue
        try:
            car_capacity = int(capacity.get("CAR", 0))
        except (TypeError, ValueError):
            continue
        if car_capacity <= 0:
            continue
        geom = shape(feature.get("geometry"))
        if geom.is_empty or not geom.is_valid:
            continue
        geometries.append(geom)
        ids.append(str(feature.get("id")))

    if len(geometries) < 100:
        raise RuntimeError(f"Too few usable Fintraffic car facilities: {len(geometries)}")

    to_local = Transformer.from_crs("EPSG:4326", "EPSG:3067", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:3067", "EPSG:4326", always_xy=True)
    local = [transform(to_local.transform, geom) for geom in geometries]
    coverage = unary_union(local).buffer(10_000).simplify(250, preserve_topology=True)
    coverage = transform(to_wgs.transform, coverage)
    path = _write(
        "fintraffic_liipi_10km.geojson",
        coverage,
        {
            "source_authority": "Fintraffic / LIIPI",
            "source_dataset": "Park-and-ride facilities",
            "source_url": FINTRAFFIC_URL,
            "source_license": "CC BY 4.0",
            "source_facility_count": len(geometries),
            "source_facility_ids_sha256": __import__("hashlib").sha256(
                "\n".join(sorted(ids)).encode()
            ).hexdigest(),
        },
    )
    return path, len(geometries)


def tfl():
    payload = _json(TFL_URL)
    if not isinstance(payload, list) or len(payload) < 20 or len(payload) > 500:
        raise RuntimeError("Unexpected TfL car-park inventory")

    points = []
    ids = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (49 <= lat <= 53 and -2 <= lon <= 2):
            continue
        ident = str(row.get("id") or "")
        if not ident:
            continue
        points.append(Point(lon, lat))
        ids.append(ident)

    if len(points) < 20:
        raise RuntimeError(f"Too few usable TfL car parks: {len(points)}")

    to_local = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    local = [transform(to_local.transform, point) for point in points]
    coverage = unary_union(local).buffer(10_000).simplify(250, preserve_topology=True)
    coverage = transform(to_wgs.transform, coverage)
    path = _write(
        "tfl_carpark_10km.geojson",
        coverage,
        {
            "source_authority": "Transport for London",
            "source_dataset": "Unified API Place/Type/CarPark",
            "source_url": TFL_URL,
            "source_license": "TfL Open Data terms",
            "source_facility_count": len(points),
            "source_facility_ids_sha256": __import__("hashlib").sha256(
                "\n".join(sorted(ids)).encode()
            ).hexdigest(),
        },
    )
    return path, len(points)


def main():
    results = []
    for name, fn in (("fintraffic", fintraffic), ("tfl", tfl)):
        path, count = fn()
        results.append(
            {
                "provider": name,
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "source_facilities": count,
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
