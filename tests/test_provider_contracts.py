"""Provider data contracts tested without Home Assistant or live network."""
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[1] / "custom_components/osm_parking/providers"
aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)
for pkg in ("custom_components", "custom_components.osm_parking", "custom_components.osm_parking.providers"):
    obj = types.ModuleType(pkg)
    obj.__path__ = []
    sys.modules.setdefault(pkg, obj)


def load(name):
    module_name = f"custom_components.osm_parking.providers.{name}"
    spec = importlib.util.spec_from_file_location(module_name, root / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


load("base")
nantes = load("nantes")
lyon = load("lyon")


def iso(delta=timedelta()):
    return (datetime.now(UTC) - delta).isoformat()


class ParkingContract(unittest.TestCase):
    def setUp(self):
        self.na = {
            "grp_identifiant": "009", "grp_nom": "Nantes Test",
            "grp_statut": 5, "grp_disponible": 40,
            "grp_exploitation": 200, "grp_complet": 8,
            "grp_horodatage": iso(), "location": [47.215, -1.553],
        }
        self.ly = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [4.83, 45.76]},
            "properties": {
                "id": "ABC", "nom": "Lyon Test", "gratuit": False,
                "nb_places": 150, "places_disponibles": 70,
                "last_update": iso(), "etat": "OUVERT", "tarif_1h": 2.5,
            },
        }

    def parse_na(self, cls=nantes.NantesPublicParkingProvider):
        return cls._normalize(self.na, 47.215, -1.553, 1000)

    def parse_ly(self):
        return lyon.LyonParkingProvider._normalize(self.ly, 45.76, 4.83, 1000)

    def test_nantes_live_with_short_stay_capacity(self):
        item = self.parse_na()
        self.assertEqual((item["free_capacity"], item["capacity"]), (40, 200))
        self.assertEqual(item["capacity_scope"], "short_stay")
        self.assertTrue(item["has_realtime_data"])

    def test_nantes_park_and_ride_separate(self):
        a = self.parse_na()
        b = self.parse_na(nantes.NantesParkAndRideProvider)
        self.assertEqual(b["category"], "park_and_ride")
        self.assertNotEqual(a["provider_id"], b["provider_id"])

    def test_nantes_legacy_and_new_coordinates(self):
        self.na["location"] = {"lat": 47.215, "lon": -1.553}
        self.assertEqual(self.parse_na()["latitude"], 47.215)
        self.na["location"] = [95, -1.553]
        self.assertIsNone(self.parse_na())

    def test_nantes_invalid_status_not_available(self):
        self.na["grp_statut"] = 0
        self.assertNotIn("free_capacity", self.parse_na())
        self.na["grp_statut"] = 2
        self.assertEqual(self.parse_na()["access"], "permit")
        self.assertNotIn("free_capacity", self.parse_na())

    def test_nantes_stale_never_live(self):
        self.na["grp_horodatage"] = iso(timedelta(minutes=20))
        self.assertFalse(self.parse_na()["has_realtime_data"])

    def test_nantes_threshold_and_bad_count(self):
        self.na["grp_disponible"] = 6
        self.assertEqual(self.parse_na()["opening_status"], "full")
        self.na["grp_disponible"] = 201
        self.assertFalse(self.parse_na()["has_realtime_data"])

    def test_lyon_geojson_and_tariff(self):
        item = self.parse_ly()
        self.assertEqual(item["free_capacity"], 70)
        self.assertEqual(item["occupied_capacity"], 80)
        self.assertEqual(item["price"], "2.50 € / 1 h")

    def test_lyon_stale_never_live(self):
        self.ly["properties"]["last_update"] = iso(timedelta(hours=1))
        item = self.parse_ly()
        self.assertNotIn("free_capacity", item)
        self.assertNotIn("opening_status", item)

    def test_lyon_impossible_count_and_coordinates(self):
        self.ly["properties"]["places_disponibles"] = 151
        self.assertNotIn("free_capacity", self.parse_ly())
        self.ly["geometry"]["coordinates"] = [float("nan"), 45.76]
        self.assertIsNone(self.parse_ly())

    def test_geographic_filters(self):
        self.assertTrue(lyon.LyonParkingProvider().applies(45.76, 4.83))
        self.assertFalse(lyon.LyonParkingProvider().applies(47.21, -1.55))
        self.assertTrue(nantes.NantesPublicParkingProvider().applies(47.21, -1.55))


if __name__ == "__main__":
    unittest.main()
