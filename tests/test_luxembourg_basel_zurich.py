"""Offline contracts for Luxembourg City/CFL, Basel and Zürich official feeds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "osm_parking"
PROVIDERS = ROOT / "providers"

aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
sys.modules.setdefault("aiohttp", aiohttp)

for name, folder in (
    ("custom_components", ROOT.parent),
    ("custom_components.osm_parking", ROOT),
    ("custom_components.osm_parking.providers", PROVIDERS),
):
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    module.__path__ = [str(folder)]


def load(qualified: str, path: Path):
    spec = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


load("custom_components.osm_parking.providers.base", PROVIDERS / "base.py")
lux = load(
    "custom_components.osm_parking.providers.luxembourg_city",
    PROVIDERS / "luxembourg_city.py",
)
cfl = load(
    "custom_components.osm_parking.providers.luxembourg_cfl",
    PROVIDERS / "luxembourg_cfl.py",
)
basel = load(
    "custom_components.osm_parking.providers.basel_stadt",
    PROVIDERS / "basel_stadt.py",
)
zurich = load(
    "custom_components.osm_parking.providers.zurich_pls",
    PROVIDERS / "zurich_pls.py",
)
quality = load(
    "custom_components.osm_parking.parking_quality",
    ROOT / "parking_quality.py",
)


def fresh_iso(minutes: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def fresh_rfc(minutes: int = 0) -> str:
    return (
        datetime.now(UTC) - timedelta(minutes=minutes)
    ).strftime("%a, %d %b %Y %H:%M:%S +0000")


class LuxembourgCityContracts(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": 27,
            "titre": "Bouillon",
            "total": 2422,
            "actuel": 2005,
            "tendance": 0,
            "ouvert": True,
            "complet": False,
            "panne": False,
            "localisation": {
                "latitude": 49.599744,
                "longitude": 6.107143,
                "mobilite": {"en": "P+R Bouillon: buses"},
                "entree": [{"adresse": "Rue de Bouillon"}],
            },
            "nominal": {"handicapes": 8, "e-cars": 70},
            "paiement": {"politique_tarifaire": "gratuit24h"},
            "restrictions": {"max_hauteur": "2,00 m"},
            "ouverture": {"en": "7/7d and 24/24h."},
            "divers": {"park_and_ride": True},
        }

    def parse(self, recorded_at=None):
        return lux.LuxembourgCityParkingProvider._normalize(
            self.row,
            49.599744,
            6.107143,
            1000,
            recorded_at if recorded_at is not None else fresh_iso(),
        )

    def test_live_vdl_record(self):
        item = self.parse()
        self.assertEqual(item["category"], "park_and_ride")
        self.assertEqual(item["capacity"], 2422)
        self.assertEqual(item["free_capacity"], 2005)
        self.assertEqual(item["occupied_capacity"], 417)
        self.assertEqual(item["accessible_capacity"], 8)
        self.assertEqual(item["ev_capacity"], 70)
        self.assertEqual(item["availability_kind"], "live")
        self.assertTrue(item["has_realtime_data"])
        self.assertEqual(item["address"], "Rue de Bouillon")
        self.assertEqual(item["max_height"], "2,00 m")
        # 24 h free then paid is not globally "free".
        self.assertEqual(item["fee"], "unknown")

    def test_vdl_fault_does_not_publish_free_spaces(self):
        self.row["panne"] = True
        item = self.parse()
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)
        self.assertEqual(item["source_status"], "fault")

    def test_vdl_closed_does_not_publish_free_spaces(self):
        self.row["ouvert"] = False
        item = self.parse()
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_vdl_stale_feed_demotes_to_static(self):
        item = self.parse(None)
        # Explicit None means helper fallback above, so call directly.
        item = lux.LuxembourgCityParkingProvider._normalize(
            self.row, 49.599744, 6.107143, 1000, None
        )
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_vdl_build_time_freshness(self):
        self.assertIsNotNone(lux._fresh_build_time(fresh_rfc(2)))
        self.assertIsNone(lux._fresh_build_time(fresh_rfc(30)))
        self.assertIsNone(lux._fresh_build_time("not a timestamp"))

    def test_vdl_paid_policy_and_geofence(self):
        self.row["divers"]["park_and_ride"] = False
        self.row["paiement"]["politique_tarifaire"] = "payant"
        item = self.parse()
        self.assertEqual(item["category"], "paid")
        self.assertEqual(item["fee"], "yes")
        provider = lux.LuxembourgCityParkingProvider()
        self.assertTrue(provider.applies(49.61, 6.13))
        self.assertFalse(provider.applies(50.85, 4.35))


class CflContracts(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "FQMPE",
            "name": "Mersch",
            "address": {
                "streetAndNumber": "30, Rue de la gare",
                "city": "Mersch",
                "zipCode": "L-7535",
            },
            "totalCapacity": 405,
            "wgS84Coordinate": {
                "longitude": 6.111,
                "latitude": 49.751,
            },
            "currentTotalFreeSpaces": 160,
            "currentPMRFreeSpaces": 10,
            "currentECarFreeSpaces": 9,
            "totalPMRCapacity": 11,
            "totalECarCapacity": 10,
        }

    def parse(self, checked="FETCHED"):
        return cfl.CflParkAndRideProvider._normalize(
            self.row,
            49.751,
            6.111,
            1000,
            checked,
        )

    def test_cfl_exact_counts_are_reported_not_live(self):
        item = self.parse()
        self.assertEqual(item["category"], "park_and_ride")
        self.assertEqual(item["capacity"], 405)
        self.assertEqual(item["free_capacity"], 160)
        self.assertEqual(item["occupied_capacity"], 245)
        self.assertEqual(item["accessible_capacity"], 11)
        self.assertEqual(item["accessible_free_capacity"], 10)
        self.assertEqual(item["ev_capacity"], 10)
        self.assertEqual(item["ev_free_capacity"], 9)
        self.assertEqual(item["availability_kind"], "reported")
        self.assertFalse(item["has_realtime_data"])
        self.assertEqual(item["availability_checked_at"], "FETCHED")

    def test_cfl_list_only_record_remains_static(self):
        item = self.parse(None)
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_cfl_impossible_free_count_is_rejected(self):
        self.row["currentTotalFreeSpaces"] = 406
        self.assertNotIn("free_capacity", self.parse())

    def test_cfl_geofence(self):
        provider = cfl.CflParkAndRideProvider()
        self.assertTrue(provider.applies(49.75, 6.11))
        self.assertFalse(provider.applies(47.56, 7.59))


class BaselContracts(unittest.TestCase):
    def setUp(self):
        self.row = {
            "title": "Parkhaus City",
            "published": fresh_iso(),
            "free": 860,
            "total": 1114,
            "link": "https://www.parkleitsystem-basel.ch/parkhaus/city",
            "geo_point_2d": {"lon": 7.5824076, "lat": 47.561101},
            "name": "City",
            "id2": "city",
            "id": "baselparkhauscity",
            "status": "offen",
            "last_downloaded": fresh_iso(),
            "address": "Schanzenstrasse 48",
            "lot_type": "Parkhaus",
        }

    def parse(self):
        return basel.BaselStadtParkingProvider._normalize(
            self.row, 47.561101, 7.5824076, 1000
        )

    def test_basel_fresh_open_record_is_live(self):
        item = self.parse()
        self.assertEqual(item["availability_kind"], "live")
        self.assertEqual(item["free_capacity"], 860)
        self.assertEqual(item["occupied_capacity"], 254)
        self.assertEqual(item["capacity"], 1114)
        self.assertEqual(item["opening_status"], "open")
        self.assertEqual(item["provider"], "basel_stadt")

    def test_basel_stale_record_is_static(self):
        self.row["published"] = fresh_iso(20)
        item = self.parse()
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_basel_closed_record_never_exposes_free(self):
        self.row["status"] = "geschlossen"
        item = self.parse()
        self.assertEqual(item["opening_status"], "closed")
        self.assertNotIn("free_capacity", item)

    def test_direct_basel_wins_equal_duplicate_over_parkendd(self):
        direct = self.parse()
        fallback = {
            **direct,
            "provider": "parkendd",
            "provider_id": "parkendd:city",
            "free_capacity": 3,
            "occupied_capacity": direct["capacity"] - 3,
        }
        merged = quality.merge_facilities([], [fallback, direct])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provider"], "basel_stadt")
        self.assertEqual(merged[0]["free_capacity"], 860)
        self.assertIn("parkendd", merged[0]["data_sources"])

    def test_basel_geofence(self):
        provider = basel.BaselStadtParkingProvider()
        self.assertTrue(provider.applies(47.56, 7.58))
        self.assertFalse(provider.applies(47.37, 8.54))


class ZurichContracts(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.feature = {
            "type": "Feature",
            "id": "poi_parkhaus_view.2",
            "geometry": {
                "type": "Point",
                "coordinates": [8.540591, 47.414853],
            },
            "properties": {
                "adresse": "Fritz-Heeb-Weg 5",
                "anzahl_oeffentliche_pp": 213.0,
                "davon_behinderten_pp": 2.0,
                "davon_elektro_pp": 2.0,
                "link_pls": (
                    "https://www.pls-zh.ch/parkhaus/"
                    "accu.jsp?pid=accu"
                ),
                "name": "Accu",
                "poi_id": "ph060",
            },
        }

    def live(self, minutes=0, free=159, status="open"):
        return {
            "accu": {
                "free": free,
                "status": status,
                "updated_at": fresh_iso(minutes),
                "link": (
                    "https://www.pls-zh.ch/parkhaus/"
                    "accu.jsp?pid=accu"
                ),
            }
        }

    def parse(self, live=None):
        return zurich.ZurichPlsProvider._normalize(
            self.feature,
            self.live() if live is None else live,
            47.414853,
            8.540591,
            1000,
        )

    def test_rss_parser_extracts_pid_free_status_and_timestamp(self):
        stamp = fresh_iso().replace("+00:00", "Z")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
          <channel><item>
            <title>Parkhaus Accu / Otto-Schütz-Weg</title>
            <link>https://www.pls-zh.ch/parkhaus/accu.jsp?pid=accu</link>
            <description>open / 159</description>
            <dc:date>{stamp}</dc:date>
          </item></channel>
        </rss>""".encode()
        parsed = zurich._live_items(xml)
        self.assertEqual(parsed["accu"]["free"], 159)
        self.assertEqual(parsed["accu"]["status"], "open")
        self.assertIsNotNone(parsed["accu"]["updated_at"])

    def test_zurich_wfs_rss_join_is_live(self):
        item = self.parse()
        self.assertEqual(item["provider"], "zurich_pls")
        self.assertEqual(item["capacity"], 213)
        self.assertEqual(item["free_capacity"], 159)
        self.assertEqual(item["occupied_capacity"], 54)
        self.assertEqual(item["accessible_capacity"], 2)
        self.assertEqual(item["ev_capacity"], 2)
        self.assertEqual(item["availability_kind"], "live")
        self.assertEqual(item["opening_status"], "open")

    def test_zurich_closed_or_missing_rss_stays_safe(self):
        closed = self.parse(self.live(status="closed"))
        self.assertEqual(closed["opening_status"], "closed")
        self.assertNotIn("free_capacity", closed)
        static = self.parse({})
        self.assertEqual(static["availability_kind"], "static")
        self.assertNotIn("free_capacity", static)

    def test_zurich_stale_rss_parser_drops_timestamp(self):
        stamp = fresh_iso(20).replace("+00:00", "Z")
        xml = f"""<rss xmlns:dc="http://purl.org/dc/elements/1.1/">
        <channel><item><title>X</title>
        <link>https://www.pls-zh.ch/parkhaus/accu.jsp?pid=accu</link>
        <description>open / 159</description><dc:date>{stamp}</dc:date>
        </item></channel></rss>""".encode()
        parsed = zurich._live_items(xml)
        self.assertIsNone(parsed["accu"]["updated_at"])
        item = self.parse(parsed)
        self.assertEqual(item["availability_kind"], "static")
        self.assertNotIn("free_capacity", item)

    def test_direct_zurich_wins_equal_duplicate_over_parkendd(self):
        direct = self.parse()
        fallback = {
            **direct,
            "provider": "parkendd",
            "provider_id": "parkendd:accu",
            "free_capacity": 2,
            "occupied_capacity": direct["capacity"] - 2,
        }
        merged = quality.merge_facilities([], [fallback, direct])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provider"], "zurich_pls")
        self.assertEqual(merged[0]["free_capacity"], 159)

    async def test_rss_failure_does_not_hide_static_wfs_sites(self):
        provider = zurich.ZurichPlsProvider()
        provider._static_sites = AsyncMock(return_value=[self.feature])
        provider._live = AsyncMock(side_effect=RuntimeError("offline"))
        result = await provider.async_fetch(
            object(), 47.414853, 8.540591, 1000, {}
        )
        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(
            result.suggestions[0]["availability_kind"], "static"
        )
        self.assertNotIn("free_capacity", result.suggestions[0])

    def test_zurich_geofence(self):
        provider = zurich.ZurichPlsProvider()
        self.assertTrue(provider.applies(47.38, 8.54))
        self.assertFalse(provider.applies(47.56, 7.58))


if __name__ == "__main__":
    unittest.main()
