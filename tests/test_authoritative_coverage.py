"""Contracts for bundled authoritative provider coverage geometry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "osm_parking"
COVERAGE_DIR = ROOT / "data" / "coverage"


def load_direct(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load_direct(
    "coverage_geometry_authoritative_test",
    ROOT / "coverage_geometry.py",
)


class AuthoritativeCoverageTests(unittest.TestCase):
    def setUp(self):
        coverage.load_coverage.cache_clear()
        self.exact = coverage.load_coverage("netherlands_brk.geojson")
        self.buffered = coverage.load_coverage("netherlands_rdw_10km.geojson")

    def test_source_provenance_is_bundled(self):
        for item, buffer_m in ((self.exact, 0), (self.buffered, 10000)):
            with self.subTest(buffer=buffer_m):
                self.assertEqual(
                    item.properties["source_authority"],
                    "Kadaster / PDOK",
                )
                self.assertEqual(
                    item.properties["source_dataset"],
                    "BRK Bestuurlijke Gebieden - Landgebied",
                )
                self.assertEqual(item.properties["source_license"], "CC BY 4.0")
                self.assertEqual(item.properties["buffer_m"], buffer_m)
                self.assertTrue(
                    item.properties["source_url"].startswith("https://api.pdok.nl/")
                )

    def test_dutch_city_points_are_inside_official_country(self):
        for name, lat, lon in (
            ("Amsterdam", 52.3676, 4.9041),
            ("Rotterdam", 51.9244, 4.4777),
            ("Maastricht", 50.8514, 5.6910),
            ("Groningen", 53.2194, 6.5665),
            ("Enschede", 52.2215, 6.8937),
        ):
            with self.subTest(city=name):
                self.assertTrue(self.exact.contains(lat, lon))
                self.assertTrue(self.buffered.contains(lat, lon))

    def test_german_cities_do_not_enter_ten_kilometre_buffer(self):
        for name, lat, lon in (
            ("Cologne", 50.9375, 6.9603),
            ("Dusseldorf", 51.2277, 6.7735),
            ("Dortmund", 51.5136, 7.4653),
            ("Frankfurt", 50.1109, 8.6821),
        ):
            with self.subTest(city=name):
                self.assertFalse(self.exact.contains(lat, lon))
                self.assertFalse(self.buffered.contains(lat, lon))

    def test_border_search_buffer_is_derived_not_hand_written(self):
        # Aachen itself is German, but a maximum 10 km search can overlap NL.
        self.assertFalse(self.exact.contains(50.7753, 6.0839))
        self.assertTrue(self.buffered.contains(50.7753, 6.0839))

    def test_invalid_points_are_rejected(self):
        for lat, lon in (
            (float("nan"), 5),
            (52, float("inf")),
            (91, 5),
            (52, 181),
            ("bad", 5),
        ):
            with self.subTest(lat=lat, lon=lon):
                self.assertFalse(self.buffered.contains(lat, lon))

    def test_geometry_files_are_small_and_valid_geojson(self):
        for filename, maximum in (
            ("netherlands_brk.geojson", 120_000),
            ("netherlands_rdw_10km.geojson", 40_000),
        ):
            path = COVERAGE_DIR / filename
            with self.subTest(filename=filename):
                self.assertLess(path.stat().st_size, maximum)
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["type"], "Feature")
                self.assertIn(
                    payload["geometry"]["type"],
                    ("Polygon", "MultiPolygon"),
                )

    def test_loader_is_cached_and_rejects_path_traversal(self):
        again = coverage.load_coverage("netherlands_rdw_10km.geojson")
        self.assertIs(self.buffered, again)
        for filename in ("../secret.geojson", "/tmp/x.geojson", "x.json"):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    coverage.load_coverage(filename)


if __name__ == "__main__":
    unittest.main()
