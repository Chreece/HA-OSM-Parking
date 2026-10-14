#!/usr/bin/env python3
"""Generate bundled Netherlands coverage from Kadaster/PDOK BRK.

Development/maintenance tool only. Runtime never calls PDOK for coverage
selection. Requires shapely + pyproj when regenerating the files.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.request import Request, urlopen

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "custom_components" / "osm_parking" / "data" / "coverage"
SOURCE_URL = (
    "https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/ogc/v1/"
    "collections/landgebied/items?limit=10"
)
SOURCE_LANDING = (
    "https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/ogc/v1"
)
LICENSE = "CC BY 4.0"


def fetch_country():
    request = Request(
        SOURCE_URL,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": "HA-OSM-Parking coverage generator",
        },
    )
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"PDOK returned HTTP {response.status}")
        payload = json.load(response)
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError("PDOK did not return a FeatureCollection")
    features = [
        feature
        for feature in payload.get("features", [])
        if isinstance(feature, dict)
        and str(feature.get("properties", {}).get("naam", "")).casefold()
        == "nederland"
    ]
    if len(features) != 1:
        raise RuntimeError(f"Expected one Nederland feature, got {len(features)}")
    return features[0]


def write_feature(path: Path, geometry, *, buffer_m: int):
    properties = {
        "source_authority": "Kadaster / PDOK",
        "source_dataset": "BRK Bestuurlijke Gebieden - Landgebied",
        "source_url": SOURCE_LANDING,
        "source_feature_url": SOURCE_URL,
        "source_license": LICENSE,
        "source_feature_name": "Nederland",
        "buffer_m": buffer_m,
        "generated_at": datetime.now(UTC).isoformat(),
        "generation_note": (
            "Derived directly from the official BRK Landgebied geometry. "
            "Runtime selection is fully offline; only the separate RDW search "
            "variant adds a 10 km buffer."
        ),
    }
    payload = {
        "type": "Feature",
        "properties": properties,
        "geometry": mapping(geometry),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main():
    feature = fetch_country()
    official = shape(feature["geometry"])
    if official.is_empty or not official.is_valid:
        raise RuntimeError("Official Netherlands geometry is empty/invalid")

    west, south, east, north = official.bounds
    if not (
        3.0 <= west <= 3.6
        and 50.5 <= south <= 51.0
        and 7.0 <= east <= 7.5
        and 53.3 <= north <= 53.8
    ):
        raise RuntimeError(
            f"Unexpected official Netherlands bounds: {official.bounds}"
        )

    to_rd = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
    from_rd = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)
    official_rd = transform(to_rd.transform, official)

    # Keep the source-derived exact shape compact but accurate enough for
    # provider selection. The buffered variant permits the configured maximum
    # 10 km radius to cross the border and still discover Dutch parking.
    exact_rd = official_rd.simplify(50, preserve_topology=True)
    buffered_rd = official_rd.buffer(10_000).simplify(100, preserve_topology=True)

    exact = transform(from_rd.transform, exact_rd)
    buffered = transform(from_rd.transform, buffered_rd)

    OUT.mkdir(parents=True, exist_ok=True)
    write_feature(OUT / "netherlands_brk.geojson", exact, buffer_m=0)
    write_feature(OUT / "netherlands_rdw_10km.geojson", buffered, buffer_m=10_000)

    # Sanity checks in the exact authoritative geometry.
    dutch = {
        "Amsterdam": (4.9041, 52.3676),
        "Rotterdam": (4.4777, 51.9244),
        "Maastricht": (5.6910, 50.8514),
        "Groningen": (6.5665, 53.2194),
        "Enschede": (6.8937, 52.2215),
    }
    german = {
        "Cologne": (6.9603, 50.9375),
        "Dusseldorf": (6.7735, 51.2277),
        "Dortmund": (7.4653, 51.5136),
        "Frankfurt": (8.6821, 50.1109),
    }
    for name, point in dutch.items():
        if not exact.covers(__import__("shapely").geometry.Point(*point)):
            raise RuntimeError(f"Official geometry excludes {name}")
    for name, point in german.items():
        if exact.covers(__import__("shapely").geometry.Point(*point)):
            raise RuntimeError(f"Official geometry unexpectedly includes {name}")

    print(
        json.dumps(
            {
                "source": SOURCE_URL,
                "exact_bytes": (OUT / "netherlands_brk.geojson").stat().st_size,
                "buffered_bytes": (
                    OUT / "netherlands_rdw_10km.geojson"
                ).stat().st_size,
                "exact_bounds": list(exact.bounds),
                "buffered_bounds": list(buffered.bounds),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
