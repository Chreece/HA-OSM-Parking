"""Official Turkish municipality parking data contracts (offline)."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "custom_components/osm_parking/providers"
aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)
for name in (
    "custom_components",
    "custom_components.osm_parking",
    "custom_components.osm_parking.providers",
):
    obj = types.ModuleType(name)
    obj.__path__ = []
    sys.modules.setdefault(name, obj)


def load(name):
    qualified = f"custom_components.osm_parking.providers.{name}"
    spec = importlib.util.spec_from_file_location(qualified, root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = mod
    spec.loader.exec_module(mod)
    return mod


load("base")
ispark = load("ispark")
izmir = load("izmir")


class TurkishContracts(unittest.TestCase):
    def setUp(self):
        self.istanbul = {
            "parkID": 3068,
            "parkName": "15 Temmuz Şehitler Meydanı",
            "lat": "41.0246",
            "lng": "29.0915",
            "capacity": 1029,
            "emptyCapacity": 560,
            "workHours": "24 Saat",
            "parkType": "KAPALI OTOPARK",
            "isOpen": 1,
        }
        self.izmir = {
            "ufid": "CPS-TR-IZM-M1-01",
            "name": "Konak Katlı Otopark",
            "provider": "İZELMAN A.Ş",
            "type": "OffStreet", "status": "Opened",
            "lat": 38.415959, "lng": 27.129392, "isPaid": True,
            "nonstop": True,
            "occupancy": {
                "total": {"free": 661, "occupied": 227},
                "disabled": {"free": 15, "occupied": 4},
            },
        }

    def parse_ispark(self):
        return ispark.IstanbulIsparkProvider._normalize(
            self.istanbul, 41.0246, 29.0915, 1000, "FETCHED",
        )

    def parse_izmir(self):
        return izmir.IzmirIzumProvider._normalize(
            self.izmir, 38.415959, 27.129392, 1000, "FETCHED",
        )

    def test_ispark_schema(self):
        item = self.parse_ispark()
        self.assertEqual(item["capacity"], 1029)
        self.assertEqual(item["free_capacity"], 560)
        self.assertEqual(item["occupied_capacity"], 469)
        self.assertEqual(item["category"], "multi_storey")
        self.assertEqual(item["availability_kind"], "reported")
        self.assertFalse(item["has_realtime_data"])
        self.assertEqual(item["availability_checked_at"], "FETCHED")
        self.assertEqual(item["fee"], "unknown")

    def test_ispark_closed_not_showing_public_free(self):
        self.istanbul["isOpen"] = 0
        self.assertNotIn("free_capacity", self.parse_ispark())
        self.assertEqual(self.parse_ispark()["opening_status"], "closed")

    def test_ispark_bad_counts(self):
        for free in (1030, -2, "nan", 12.5):
            self.istanbul["emptyCapacity"] = free
            with self.subTest(free=free):
                self.assertNotIn("free_capacity", self.parse_ispark())

    def test_ispark_street_no_cross_provider_merging(self):
        self.istanbul["parkType"] = "YOL ÜSTÜ"
        item = self.parse_ispark()
        self.assertEqual(item["category"], "street")
        self.assertFalse(item["merge_with_other_sources"])

    def test_ispark_no_fake_free_pricing(self):
        self.istanbul["freeTime"] = 15
        self.assertEqual(self.parse_ispark()["fee"], "unknown")
        self.assertNotIn("price", self.parse_ispark())

    def test_ispark_bad_coordinates_rejected(self):
        self.istanbul["lat"] = 3.1
        self.assertIsNone(self.parse_ispark())

    def test_izmir_schema_and_accessibility(self):
        item = self.parse_izmir()
        self.assertEqual(item["capacity"], 888)
        self.assertEqual(item["free_capacity"], 661)
        self.assertEqual(item["accessible_capacity"], 19)
        self.assertEqual(item["accessible_free_capacity"], 15)
        self.assertEqual(item["fee"], "yes")
        self.assertEqual(item["opening_hours"], "24/7")
        self.assertEqual(item["availability_kind"], "reported")
        self.assertFalse(item["has_realtime_data"])

    def test_izmir_closed_not_free(self):
        self.izmir["status"] = "Closed"
        item = self.parse_izmir()
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_izmir_bad_or_partial_counts_not_reported(self):
        for free in (-1, "nan", None, 12.4):
            self.izmir["occupancy"]["total"]["free"] = free
            with self.subTest(free=free):
                self.assertNotIn("free_capacity", self.parse_izmir())
                self.assertEqual(self.parse_izmir()["availability_kind"], "static")

    def test_izmir_street_not_same_as_garage(self):
        self.izmir["type"] = "OnStreet"
        item = self.parse_izmir()
        self.assertEqual(item["category"], "street")
        self.assertFalse(item["merge_with_other_sources"])

    def test_izmir_no_unknown_tariff_invention(self):
        self.izmir["isPaid"] = False
        item = self.parse_izmir()
        self.assertEqual(item["fee"], "no")
        self.assertNotIn("price", item)

    def test_izmir_bad_coordinates_rejected(self):
        self.izmir["lng"] = float("nan")
        self.assertIsNone(self.parse_izmir())

    def test_geofences(self):
        self.assertTrue(ispark.IstanbulIsparkProvider().applies(41.0246, 29.0915))
        self.assertFalse(ispark.IstanbulIsparkProvider().applies(38.4159, 27.1293))
        self.assertTrue(izmir.IzmirIzumProvider().applies(38.4159, 27.1293))
        self.assertFalse(izmir.IzmirIzumProvider().applies(41.0246, 29.0915))


if __name__ == "__main__":
    unittest.main()
