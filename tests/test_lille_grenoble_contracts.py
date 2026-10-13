"""Lille and Grenoble normalized provider contracts (no HA or live network)."""

import importlib.util
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

root = Path(__file__).resolve().parents[1] / "custom_components/osm_parking/providers"
aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)
for package in (
    "custom_components",
    "custom_components.osm_parking",
    "custom_components.osm_parking.providers",
):
    module = types.ModuleType(package)
    module.__path__ = []
    sys.modules.setdefault(package, module)


def load(name):
    qualified = f"custom_components.osm_parking.providers.{name}"
    spec = importlib.util.spec_from_file_location(qualified, root / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


load("base")
lille = load("lille")
grenoble = load("grenoble")


def iso(delta=timedelta()):
    return (datetime.now(UTC) - delta).isoformat()


def unix(delta=timedelta()):
    return int((datetime.now(UTC) - delta).timestamp())


class LilleContract(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [3.058, 50.632]},
            "properties": {
                "id": "MEL_1",
                "nom": "Parking Test Lille",
                "adresse": "Rue Test",
                "ville": "Lille",
                "etat": "OUVERT",
                "nbr_total": 300,
                "nbr_libre": 42,
                "dtdate": iso(),
            },
        }

    def parse(self):
        return lille.LilleParkingProvider._normalize(
            self.feature, 50.632, 3.058, 800,
        )

    def test_lille_fresh_known_open(self):
        result = self.parse()
        self.assertEqual(result["free_capacity"], 42)
        self.assertEqual(result["capacity"], 300)
        self.assertEqual(result["occupied_capacity"], 258)
        self.assertTrue(result["has_realtime_data"])

    def test_lille_stale_never_live(self):
        self.feature["properties"]["dtdate"] = iso(timedelta(minutes=16))
        result = self.parse()
        self.assertFalse(result["has_realtime_data"])
        self.assertNotIn("free_capacity", result)

    def test_lille_unknown_status_conservative(self):
        self.feature["properties"]["etat"] = "1"
        result = self.parse()
        self.assertNotIn("free_capacity", result)
        self.assertFalse(result["has_realtime_data"])

    def test_lille_closed_not_zero_availability(self):
        self.feature["properties"]["etat"] = "FERME"
        result = self.parse()
        self.assertEqual(result["opening_status"], "closed")
        self.assertNotIn("free_capacity", result)

    def test_lille_invalid_counts_rejected(self):
        for value in (-1, 301, "nan", 1.5):
            self.feature["properties"]["nbr_libre"] = value
            with self.subTest(value=value):
                self.assertNotIn("free_capacity", self.parse())

    def test_lille_point_fallback_and_radius(self):
        self.feature["geometry"] = None
        self.feature["properties"]["latitude"] = 50.632
        self.feature["properties"]["longitude"] = 3.058
        self.assertEqual(self.parse()["distance_m"], 0)
        self.feature["properties"]["longitude"] = 3.10
        self.assertIsNone(self.parse())

    def test_lille_naive_time_not_interpreted_as_utc(self):
        from zoneinfo import ZoneInfo
        naive = datetime.now(ZoneInfo("Europe/Paris")).replace(tzinfo=None)
        self.feature["properties"]["dtdate"] = naive.isoformat()
        self.assertTrue(self.parse()["has_realtime_data"])

    def test_lille_geofence(self):
        self.assertTrue(lille.LilleParkingProvider().applies(50.63, 3.06))
        self.assertFalse(lille.LilleParkingProvider().applies(45.19, 5.72))


class GrenobleContract(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.724, 45.189]},
            "properties": {
                "id": "GREN_1",
                "nom": "Parking Grenoble",
                "nb_places": 250,
                "nb_pr": 0,
                "nb_pmr": 9,
                "nb_voitures_electriques": 6,
                "type_ouvrage": "ouvrage",
                "gratuit": False,
                "tarif_1h": 2.0,
            },
        }
        self.live = {"GREN_1": {"nb_places_libres": 55, "time": unix(), "nsv_id": 123}}

    def parse(self):
        return grenoble.GrenobleParkingProvider._normalize(
            self.feature, self.live, 45.189, 5.724, 1200,
        )

    def test_grenoble_fresh_join_by_id(self):
        result = self.parse()
        self.assertEqual(result["capacity"], 250)
        self.assertEqual(result["free_capacity"], 55)
        self.assertEqual(result["occupied_capacity"], 195)
        self.assertEqual(result["accessible_capacity"], 9)
        self.assertEqual(result["price"], "2.00 € / 1 h")
        self.assertTrue(result["has_realtime_data"])

    def test_grenoble_no_join_does_not_claim_zero(self):
        self.live = {"DIFFERENT_ID": {"nb_places_libres": 0, "time": unix()}}
        self.assertNotIn("free_capacity", self.parse())

    def test_grenoble_null_and_missing_producer_time(self):
        self.live["GREN_1"]["nb_places_libres"] = None
        self.assertNotIn("free_capacity", self.parse())
        self.live["GREN_1"]["nb_places_libres"] = 20
        self.live["GREN_1"].pop("time")
        self.assertFalse(self.parse()["has_realtime_data"])

    def test_grenoble_stale_and_future(self):
        self.live["GREN_1"]["time"] = unix(timedelta(minutes=11))
        self.assertNotIn("free_capacity", self.parse())
        self.live["GREN_1"]["time"] = unix(-timedelta(days=1))
        self.assertNotIn("free_capacity", self.parse())

    def test_grenoble_ms_timestamp(self):
        self.live["GREN_1"]["time"] = unix() * 1000
        self.assertEqual(self.parse()["free_capacity"], 55)

    def test_grenoble_impossible_counts(self):
        for value in (-2, 251, float("nan"), 1.5):
            self.live["GREN_1"]["nb_places_libres"] = value
            with self.subTest(value=value):
                self.assertNotIn("free_capacity", self.parse())

    def test_grenoble_park_ride_separate_category(self):
        self.feature["properties"]["nb_pr"] = 200
        self.assertEqual(self.parse()["category"], "park_and_ride")

    def test_grenoble_bad_coords_and_radius(self):
        self.feature["geometry"]["coordinates"] = [float("inf"), 45.189]
        self.assertIsNone(self.parse())
        self.feature["geometry"]["coordinates"] = [5.9, 45.189]
        self.assertIsNone(self.parse())

    def test_grenoble_geofence(self):
        self.assertTrue(grenoble.GrenobleParkingProvider().applies(45.189, 5.724))
        self.assertFalse(grenoble.GrenobleParkingProvider().applies(50.632, 3.058))


if __name__ == "__main__":
    unittest.main()
