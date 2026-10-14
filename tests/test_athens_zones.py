"""Offline Athens controlled-parking zone parser tests."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[1] / "custom_components/osm_parking"
aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)
for name, directory in (
    ("custom_components", None),
    ("custom_components.osm_parking", root),
    ("custom_components.osm_parking.providers", root / "providers"),
):
    pkg = types.ModuleType(name)
    pkg.__path__ = [] if directory is None else [str(directory)]
    sys.modules.setdefault(name, pkg)


def load(qualified, file):
    spec = importlib.util.spec_from_file_location(qualified, file)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = obj
    spec.loader.exec_module(obj)
    return obj


load("custom_components.osm_parking.const", root / "const.py")
load("custom_components.osm_parking.providers.base", root / "providers/base.py")
athens = load("custom_components.osm_parking.providers.athens_zones", root / "providers/athens_zones.py")


class Zones(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [23.728, 37.978], [23.740, 37.978], [23.740, 37.985],
                [23.728, 37.985], [23.728, 37.978],
            ]]},
            "properties": {"name": "Ζώνη Α"},
        }
        self.bbox = (37.97, 23.72, 37.99, 23.75)

    def test_zone_not_parking(self):
        result = athens._normalize(self.feature, self.bbox)
        self.assertEqual(result["properties"]["record_type"], "zone")
        self.assertEqual(result["properties"]["availability_kind"], "zone")
        self.assertNotIn("free_capacity", result["properties"])
        self.assertEqual(result["properties"]["parking_rules"], "consult_official_signage")

    def test_outside_bbox_not_included(self):
        self.assertIsNone(athens._normalize(self.feature, (37.9, 23.5, 37.92, 23.55)))

    def test_invalid_crs_coordinates_not_included(self):
        self.feature["geometry"]["coordinates"][0][0] = [478000, 4200000]
        self.assertIsNone(athens._normalize(self.feature, self.bbox))

    def test_non_polygon_not_included(self):
        self.feature["geometry"]["type"] = "Point"
        self.assertIsNone(athens._normalize(self.feature, self.bbox))

    def test_multipolygon(self):
        self.feature["geometry"]["type"] = "MultiPolygon"
        self.feature["geometry"]["coordinates"] = [self.feature["geometry"]["coordinates"]]
        self.assertIsNotNone(athens._normalize(self.feature, self.bbox))

    def test_opt_in_and_geofence(self):
        self.assertFalse(hasattr(athens.AthensParkingZonesProvider(), "enabled_option"))
        self.assertTrue(athens.AthensParkingZonesProvider().applies(37.98, 23.73))


if __name__ == "__main__":
    unittest.main()
