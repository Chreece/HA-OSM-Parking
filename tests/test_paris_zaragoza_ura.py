"""Official Paris, Zaragoza and Singapore URA provider contracts.

Offline tests use publisher-documented response shapes and fake HTTP sessions.
No Home Assistant installation, credentials or public internet is required.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "osm_parking"
PACK = ROOT / "providers"

aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)

for name, folder in (
    ("custom_components", ROOT.parent),
    ("custom_components.osm_parking", ROOT),
    ("custom_components.osm_parking.providers", PACK),
):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        sys.modules[name] = package
    package.__path__ = [str(folder)]


def load(qualified: str, path: Path):
    specification = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[qualified] = module
    specification.loader.exec_module(module)
    return module


load("custom_components.osm_parking.const", ROOT / "const.py")
load("custom_components.osm_parking.providers.base", PACK / "base.py")
load("custom_components.osm_parking.providers.singapore", PACK / "singapore.py")
paris = load("custom_components.osm_parking.providers.paris", PACK / "paris.py")
zaragoza = load("custom_components.osm_parking.providers.zaragoza", PACK / "zaragoza.py")
ura = load("custom_components.osm_parking.providers.singapore_ura", PACK / "singapore_ura.py")
quality = load("custom_components.osm_parking.parking_quality", ROOT / "parking_quality.py")


class ParisProviderTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "75115-P-157",
            "nom": "FREMICOURT",
            "adresse": "13 ter rue fremicourt, 75015, Paris",
            "xlong": 2.29739674,
            "ylat": 48.84734233,
            "gratuit": 0,
            "nb_places": 195,
            "nb_pmr": 5,
            "nb_voitures_electriques": 12,
            "type_ouvrage": "ouvrage",
            "tarif_1h": 4.5,
            "url": "https://example.com/parking",
        }

    def parse(self):
        return paris.ParisBnlsProvider._normalize(
            self.row, 48.84734233, 2.29739674, 1000
        )

    def test_paris_published_bnls_schema(self):
        result = self.parse()
        self.assertEqual(result["provider_id"], "paris-bnls:75115-P-157")
        self.assertEqual(result["capacity"], 195)
        self.assertEqual(result["accessible_capacity"], 5)
        self.assertEqual(result["ev_capacity"], 12)
        self.assertEqual(result["price"], "4.50 € / 1 h")
        self.assertEqual(result["fee"], "yes")
        self.assertEqual(result["availability_kind"], "static")
        self.assertNotIn("free_capacity", result)
        self.assertFalse(result["has_realtime_data"])

    def test_paris_relay_category(self):
        self.row["nb_pr"] = 25
        self.assertEqual(self.parse()["category"], "park_and_ride")

    def test_paris_subscriber_only_restricted(self):
        self.row["type_usagers"] = "abonnés"
        self.assertEqual(self.parse()["access"], "permit")
        self.row["type_usagers"] = "abonnés, visiteurs"
        self.assertEqual(self.parse()["access"], "unknown")

    def test_paris_coordinates_fallback(self):
        self.row.pop("xlong")
        self.row.pop("ylat")
        self.row["geo_point_2d"] = [48.84734233, 2.29739674]
        self.assertAlmostEqual(self.parse()["latitude"], 48.84734233, places=6)
        self.row["geo_point_2d"] = {"lat": 48.84734233, "lon": 2.29739674}
        self.assertAlmostEqual(self.parse()["longitude"], 2.29739674, places=6)

    def test_paris_invalid_coordinates_or_missing_id(self):
        self.row["xlong"] = float("nan")
        self.assertIsNone(self.parse())
        self.row["xlong"] = 2.29739674
        self.row.pop("id")
        self.assertIsNone(self.parse())

    def test_paris_no_fabricated_tariffs(self):
        self.row.pop("tarif_1h")
        self.assertNotIn("price", self.parse())
        self.row["gratuit"] = 1
        self.assertEqual(self.parse()["fee"], "no")

    def test_paris_geographic_selection_and_radius(self):
        self.assertTrue(paris.ParisBnlsProvider().applies(48.86, 2.34))
        self.assertFalse(paris.ParisBnlsProvider().applies(41.65, -0.88))
        self.row["xlong"] += 0.2
        self.assertIsNone(self.parse())

    def test_paris_static_merge_cannot_erase_valid_live(self):
        static = self.parse()
        live = {
            "provider": "source_live",
            "name": static["name"],
            "provider_id": "live:test",
            "latitude": static["latitude"],
            "longitude": static["longitude"],
            "category": "multi_storey",
            "availability_kind": "reported",
            "free_capacity": 30,
            "capacity": 195,
            "fee": "unknown",
        }
        merged = quality.merge_facilities([], [static, live])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provider"], "source_live")
        self.assertEqual(merged[0]["free_capacity"], 30)
        self.assertEqual(merged[0]["address"], static["address"])


class ZaragozaProviderTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": 123,
            "title": "Parking Plaza del Pilar",
            "geometry": {"type": "Point", "coordinates": [-0.8774, 41.656]},
            "address": "Plaza del Pilar",
            "openingHours": "24 horas",
            "plazas": 350,
        }

    def parse(self):
        return zaragoza.ZaragozaParkingProvider._normalize(
            self.row, 41.656, -0.8774, 1000
        )

    def test_zaragoza_documented_api_result(self):
        item = self.parse()
        self.assertEqual(item["provider_id"], "zaragoza:123")
        self.assertEqual(item["capacity"], 350)
        self.assertEqual(item["name"], "Parking Plaza del Pilar")
        self.assertEqual(item["opening_hours"], "24 horas")
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_zaragoza_geojson_property_wrapper(self):
        raw = {"type": "Feature", "id": 123, "geometry": self.row["geometry"],
               "properties": {"title": "Pilar", "plazas": 10}}
        normalized = zaragoza.ZaragozaParkingProvider._normalize(raw, 41.656, -0.8774, 1000)
        self.assertEqual(normalized["capacity"], 10)

    def test_zaragoza_utm30_rejected(self):
        self.row["geometry"]["coordinates"] = [676934.75, 4613880.67]
        self.assertIsNone(self.parse())

    def test_zaragoza_invalid_geometry_and_radius(self):
        self.row["geometry"]["type"] = "MultiPoint"
        self.assertIsNone(self.parse())
        self.row["geometry"]["type"] = "Point"
        self.row["geometry"]["coordinates"] = [-0.7, 41.656]
        self.assertIsNone(self.parse())

    def test_zaragoza_no_guessing_vinci_or_zone_occupancy(self):
        self.row["ocupacion"] = 85
        self.row["libres"] = 8
        self.assertFalse(self.parse()["has_realtime_data"])
        self.assertNotIn("free_capacity", self.parse())
        self.assertNotIn("estimated_occupancy_ratio", self.parse())

    def test_zaragoza_geofence(self):
        self.assertTrue(zaragoza.ZaragozaParkingProvider().applies(41.65, -0.88))
        self.assertFalse(zaragoza.ZaragozaParkingProvider().applies(48.86, 2.34))


class SingaporeUraProviderTests(unittest.TestCase):
    def setUp(self):
        self.detail = {
            "ppCode": "A0004",
            "ppName": "ALIWAL STREET",
            "vehCat": "Car",
            "parkCapacity": 69,
            "weekdayRate": "$0.50",
            "weekdayMin": "30mins",
            "parkingSystem": "C",
            "geometries": [{"coordinates": "31045.6165, 31694.0055"}],
        }
        self.position = ura._coords(self.detail)[0]
        self.availability = {
            "carparkNo": "A0004",
            "lotType": "C",
            "lotsAvailable": "23",
        }

    def parse(self):
        return ura.SingaporeUraProvider._normalize(
            self.detail, self.availability,
            self.position[0], self.position[1], 1000, "FETCHED_AT",
        )

    def test_svy21_coordinates_not_used_as_wgs84(self):
        lat, lon = self.position
        self.assertTrue(1.1 < lat < 1.52)
        self.assertTrue(103.5 < lon < 104.2)
        self.assertEqual(len(ura._coords(self.detail)), 1)

    def test_ura_documented_details_and_reported_availability(self):
        item = self.parse()
        self.assertEqual(item["provider_id"], "sg-ura:A0004")
        self.assertEqual(item["capacity"], 69)
        self.assertEqual(item["free_capacity"], 23)
        self.assertEqual(item["occupied_capacity"], 46)
        self.assertEqual(item["availability_kind"], "reported")
        self.assertFalse(item["has_realtime_data"])
        self.assertEqual(item["availability_checked_at"], "FETCHED_AT")
        self.assertEqual(item["price"], "$0.50 / 30mins (weekday)")
        self.assertEqual(item["fee"], "yes")

    def test_ura_zero_remaining_is_valid_not_timestamp_verified(self):
        self.availability["lotsAvailable"] = "0"
        item = self.parse()
        self.assertEqual(item["free_capacity"], 0)
        self.assertEqual(item["availability_kind"], "reported")
        self.assertNotIn("opening_status", item)

    def test_ura_missing_availability_is_static(self):
        self.availability = None
        item = self.parse()
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_ura_capacity_bounds_protected(self):
        for raw in ("70", "-1", "nan", "2.5"):
            self.availability["lotsAvailable"] = raw
            with self.subTest(raw=raw):
                self.assertNotIn("free_capacity", self.parse())

    def test_ura_invalid_utm_coordinates_rejected(self):
        self.detail["geometries"] = [{"coordinates": "nan, 30000"}]
        self.assertIsNone(ura.SingaporeUraProvider._normalize(
            self.detail, self.availability,
            self.position[0], self.position[1], 1000,
        ))

    def test_ura_nearest_of_many_geometries(self):
        first = self.detail["geometries"][0]
        self.detail["geometries"] = [
            {"coordinates": "29000, 29000"}, first
        ]
        self.assertEqual(self.parse()["distance_m"], 0)

    def test_ura_outside_radius(self):
        self.assertIsNone(ura.SingaporeUraProvider._normalize(
            self.detail, self.availability,
            1.20, 103.70, 100,
        ))

    def test_ura_enabled_only_when_key_configured(self):
        p = ura.SingaporeUraProvider()
        self.assertEqual(p.required_options, ("ura_access_key",))
        self.assertTrue(p.applies(1.30, 103.85))
        self.assertFalse(p.applies(48.86, 2.34))

    def test_ura_token_fingerprint_not_plain_secret(self):
        hashed = ura.SingaporeUraProvider._fingerprint("TEST_SECRET")
        self.assertNotIn("TEST_SECRET", hashed)
        self.assertEqual(len(hashed), 64)


class ConfigurationContracts(unittest.TestCase):
    def test_all_option_translations_have_ura_keys(self):
        import json
        for file in [ROOT / "strings.json", *(ROOT / "translations").glob("*.json")]:
            with self.subTest(file=file.name):
                obj = json.loads(file.read_text(encoding="utf-8"))
                options = obj["options"]["step"]["init"]
                self.assertTrue(options["data"]["ura_enabled"])
                self.assertTrue(options["data"]["ura_access_key"])
                self.assertTrue(options["data_description"]["ura_access_key"])


if __name__ == "__main__":
    unittest.main()
