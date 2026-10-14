"""Offline contracts for Fintraffic LIIPI and TfL direct providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

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
    spec = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


load("custom_components.osm_parking.coverage_geometry", ROOT / "coverage_geometry.py")
load("custom_components.osm_parking.providers.base", PACK / "base.py")
fin = load("custom_components.osm_parking.providers.fintraffic", PACK / "fintraffic.py")
tfl = load("custom_components.osm_parking.providers.tfl", PACK / "tfl.py")
quality = load("custom_components.osm_parking.parking_quality", ROOT / "parking_quality.py")


def now_iso(delta=timedelta()):
    return (datetime.now(UTC) - delta).isoformat()


def fin_feature():
    return {
        "id": 303,
        "geometry": {
            "type": "Polygon",
            "bbox": [24.99448, 60.24321, 24.99607, 60.24388],
            "coordinates": [[
                [24.99448, 60.24321],
                [24.99607, 60.24321],
                [24.99607, 60.24388],
                [24.99448, 60.24321],
            ]],
        },
        "properties": {
            "name": {
                "fi": "Eskolantie P1",
                "sv": "Eskosvägen P1",
                "en": "Eskolantie P1",
            },
            "status": "IN_OPERATION",
            "operatorId": 44,
            "builtCapacity": {"CAR": 89, "ELECTRIC_CAR": 2},
            "usages": ["PARK_AND_RIDE"],
            "ports": [{
                "entry": True,
                "exit": True,
                "location": {
                    "type": "Point",
                    "coordinates": [24.994629, 60.243603],
                },
            }],
        },
    }


def fin_live(**changes):
    item = {
        "facilityId": 303,
        "capacityType": "CAR",
        "usage": "PARK_AND_RIDE",
        "timestamp": now_iso(),
        "spacesAvailable": 63,
        "capacity": 89,
        "openNow": True,
    }
    item.update(changes)
    return item


def tfl_place():
    return {
        "id": "CarParks_800491",
        "commonName": "Barkingside Station Car Park",
        "lat": 51.58629,
        "lon": 0.08832,
        "url": "https://api.tfl.gov.uk/Place/CarParks_800491",
        "additionalProperties": [
            {"key": "NumberOfSpaces", "value": "46"},
            {"key": "NumberOfDisabledBays", "value": "2"},
            {"key": "OpeningHours", "value": "24 hours"},
            {"key": "Open", "value": "True"},
            {"key": "StationAtcoCode", "value": "940GZZLUBKE"},
            {"key": "StandardTariffsCashlessDaily", "value": "5"},
            {"key": "Address", "value": "Station Road, Barkingside"},
        ],
    }


def tfl_occupancy():
    return {
        "id": "CarParks_800491",
        "name": "Barkingside Station Car Park",
        "bays": [
            {
                "bayType": "Regular",
                "bayCount": 44,
                "free": 11,
                "occupied": 33,
            },
            {
                "bayType": "Disabled",
                "bayCount": 2,
                "free": 1,
                "occupied": 1,
            },
        ],
    }


class FintrafficContracts(unittest.TestCase):
    def parse(self, feature=None, current=None):
        feature = feature or fin_feature()
        current = current if current is not None else {303: fin_live()}
        return fin.FintrafficLiipiProvider._normalize(
            feature,
            current,
            60.243603,
            24.994629,
            1500,
        )

    def test_published_schema_becomes_verified_live(self):
        item = self.parse()
        self.assertEqual(item["provider_id"], "fintraffic-liipi:303")
        self.assertEqual(item["category"], "park_and_ride")
        self.assertEqual(item["capacity"], 89)
        self.assertEqual(item["ev_capacity"], 2)
        self.assertEqual(item["free_capacity"], 63)
        self.assertEqual(item["occupied_capacity"], 26)
        self.assertEqual(item["availability_kind"], "live")
        self.assertTrue(item["has_realtime_data"])
        self.assertEqual(item["availability_freshness"], "verified")
        self.assertEqual(item["opening_status"], "open")
        self.assertEqual(item["distance_m"], 0)

    def test_entry_port_wins_over_polygon_centre(self):
        point = fin._site_point(fin_feature())
        self.assertEqual(point, (60.243603, 24.994629))

    def test_bbox_centre_fallback_is_valid(self):
        feature = fin_feature()
        feature["properties"]["ports"] = []
        point = fin._site_point(feature)
        self.assertAlmostEqual(point[0], (60.24321 + 60.24388) / 2)
        self.assertAlmostEqual(point[1], (24.99448 + 24.99607) / 2)

    def test_stale_measurement_never_becomes_live(self):
        item = self.parse(current={
            303: fin_live(timestamp=now_iso(timedelta(minutes=11)))
        })
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_closed_utilization_hides_free_spaces(self):
        item = self.parse(current={303: fin_live(openNow=False)})
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_closed_facility_status_hides_utilization(self):
        feature = fin_feature()
        feature["properties"]["status"] = "TEMPORARILY_CLOSED"
        item = self.parse(feature=feature)
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_impossible_counts_are_static(self):
        for changes in (
            {"spacesAvailable": -1},
            {"spacesAvailable": 90},
            {"spacesAvailable": 2.5},
            {"capacity": float("nan")},
        ):
            with self.subTest(changes=changes):
                item = self.parse(current={303: fin_live(**changes)})
                self.assertNotEqual(item["availability_kind"], "live")
                self.assertNotIn("free_capacity", item)

    def test_no_utilization_keeps_static_facility(self):
        item = self.parse(current={})
        self.assertEqual(item["availability_kind"], "static")
        self.assertEqual(item["capacity"], 89)

    def test_coverage_is_facility_derived_not_country_rectangle(self):
        provider = fin.FintrafficLiipiProvider()
        self.assertTrue(provider.applies(60.1699, 24.9384))
        self.assertTrue(provider.applies(60.2736, 25.0365))
        self.assertFalse(provider.applies(50.9375, 6.9603))
        coverage = fin.load_coverage(fin.COVERAGE_FILE)
        self.assertEqual(coverage.properties["source_authority"], "Fintraffic / LIIPI")
        self.assertGreaterEqual(coverage.properties["source_facility_count"], 250)
        self.assertEqual(coverage.properties["buffer_m"], 10_000)


class FintrafficAsyncContracts(unittest.IsolatedAsyncioTestCase):
    async def test_live_subfeed_failure_keeps_static_and_retries(self):
        provider = fin.FintrafficLiipiProvider()
        provider._static_facilities = AsyncMock(return_value=[fin_feature()])
        provider._utilizations = AsyncMock(side_effect=RuntimeError("down"))
        result = await provider.async_fetch(
            None,
            60.243603,
            24.994629,
            1500,
        )
        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(
            result.suggestions[0]["availability_kind"],
            "static",
        )
        self.assertEqual(result.live_refresh_seconds, 120)


class TflContracts(unittest.TestCase):
    def parse(self, occupancy=None, place=None):
        return tfl.TflCarParkProvider._normalize(
            place or tfl_place(),
            occupancy,
            51.58629,
            0.08832,
            1500,
            now_iso(),
        )

    def test_static_place_schema(self):
        item = self.parse()
        self.assertEqual(item["provider_id"], "tfl:CarParks_800491")
        self.assertEqual(item["category"], "park_and_ride")
        self.assertEqual(item["capacity"], 46)
        self.assertEqual(item["accessible_capacity"], 2)
        self.assertEqual(item["opening_hours"], "24 hours")
        self.assertEqual(item["address"], "Station Road, Barkingside")
        self.assertEqual(item["price"], "£5.00 / day")
        self.assertEqual(item["fee"], "yes")
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_occupancy_is_reported_not_verified_live(self):
        item = self.parse(tfl_occupancy())
        self.assertEqual(item["capacity"], 46)
        self.assertEqual(item["free_capacity"], 12)
        self.assertEqual(item["occupied_capacity"], 34)
        self.assertEqual(item["availability_kind"], "reported")
        self.assertEqual(item["availability_freshness"], "unverified")
        self.assertFalse(item["has_realtime_data"])
        self.assertIn("availability_checked_at", item)

    def test_impossible_bay_counts_are_ignored(self):
        occupancy = tfl_occupancy()
        occupancy["bays"][0]["free"] = 100
        item = self.parse(occupancy)
        # The valid disabled bay can still contribute; impossible regular row
        # is rejected record-by-record.
        self.assertEqual(item["free_capacity"], 1)
        self.assertEqual(item["availability_kind"], "reported")

    def test_no_valid_bays_is_static(self):
        occupancy = tfl_occupancy()
        for bay in occupancy["bays"]:
            bay["free"] = -1
        item = self.parse(occupancy)
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_closed_place_does_not_expose_reported_free(self):
        place = tfl_place()
        for prop in place["additionalProperties"]:
            if prop["key"] == "Open":
                prop["value"] = "False"
        item = self.parse(tfl_occupancy(), place=place)
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_coverage_comes_from_actual_tfl_carpark_places(self):
        provider = tfl.TflCarParkProvider()
        self.assertTrue(provider.applies(51.58629, 0.08832))
        self.assertFalse(provider.applies(50.9375, 6.9603))
        coverage = tfl.load_coverage(tfl.COVERAGE_FILE)
        self.assertEqual(coverage.properties["source_authority"], "Transport for London")
        self.assertEqual(coverage.properties["source_facility_count"], 58)
        self.assertEqual(coverage.properties["buffer_m"], 10_000)

    def test_direct_tfl_static_outscores_aggregator_duplicate(self):
        direct = self.parse()
        parkendd = {
            **direct,
            "provider": "parkendd",
            "provider_id": "parkendd:duplicate",
            "provider_name": "ParkenDD",
            "price": None,
        }
        merged = quality.merge_facilities([], [parkendd, direct])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provider"], "tfl_carpark")


class TflAsyncContracts(unittest.IsolatedAsyncioTestCase):
    async def test_occupancy_outage_keeps_static_places_and_retries(self):
        provider = tfl.TflCarParkProvider()
        provider._static_places = AsyncMock(return_value=[tfl_place()])
        provider._occupancy = AsyncMock(return_value={})
        result = await provider.async_fetch(
            None,
            51.58629,
            0.08832,
            1500,
        )
        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(
            result.suggestions[0]["availability_kind"],
            "static",
        )
        self.assertEqual(result.live_refresh_seconds, 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
