"""Global source quality and deduplication contracts (no HA dependency)."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
import unittest

path = (
    Path(__file__).resolve().parents[1]
    / "custom_components/osm_parking/parking_quality.py"
)
spec = importlib.util.spec_from_file_location("parking_quality_under_test", path)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def stamp(minutes=0):
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def facility(provider, *, name="City Parking Alpha", latitude=50.938, longitude=6.982,
             fee="unknown", category="multi_storey", capacity=None,
             free=None, updated=None, kind=None, mergeable=True):
    result = {
        "provider": provider,
        "provider_name": provider,
        "provider_id": f"{provider}:1",
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "fee": fee,
        "merge_with_other_sources": mergeable,
    }
    if capacity is not None:
        result["capacity"] = capacity
    if free is not None:
        result["free_capacity"] = free
        result["has_realtime_data"] = kind == "live"
    if updated is not None:
        result["realtime_updated_at"] = updated
    if kind is not None:
        result["availability_kind"] = kind
    return result


class SourceQualityContracts(unittest.TestCase):
    def test_recent_measured_wins_over_estimate_and_static(self):
        osm = facility("osm", name="City Parking Alpha", fee="yes", capacity=300)
        estimate = facility("swiss", kind="estimated")
        estimate["estimated_occupancy_ratio"] = .51
        live = facility("city", kind="live", free=28, capacity=300, updated=stamp())
        for inputs in ([osm, estimate, live], [live, osm, estimate]):
            with self.subTest(order=[v["provider"] for v in inputs]):
                merged = quality.merge_facilities([], inputs)
                self.assertEqual(len(merged), 1)
                self.assertEqual(merged[0]["provider"], "city")
                self.assertEqual(merged[0]["availability_kind"], "live")
                self.assertEqual(merged[0]["free_capacity"], 28)
                self.assertEqual(len(merged[0]["data_sources"]), 3)

    def test_newest_valid_live_wins_even_when_arriving_first(self):
        old = facility("feed_a", kind="live", free=8, capacity=100, updated=stamp(8))
        new = facility("feed_b", kind="live", free=47, capacity=100, updated=stamp())
        for inputs in ([new, old], [old, new]):
            result = quality.merge_facilities([], inputs)[0]
            self.assertEqual(result["free_capacity"], 47)
            self.assertEqual(result["availability_source"], "feed_b")

    def test_stale_live_is_demoted_and_removed(self):
        stale = facility("official", kind="live", capacity=100, free=4, updated=stamp(90))
        normalized = quality.normalize_facility(stale)
        self.assertEqual(normalized["availability_kind"], "static")
        self.assertFalse(normalized["has_realtime_data"])
        self.assertNotIn("free_capacity", normalized)
        self.assertTrue(normalized["availability_stale"])

    def test_naive_bad_timestamp_is_not_claimed_live(self):
        record = facility("official", kind="live", free=4, updated="2026-10-13 10:00:00")
        self.assertEqual(quality.normalize_facility(record)["availability_kind"], "static")

    def test_reported_count_is_not_live(self):
        record = facility("turkish", kind="reported", free=12, capacity=60)
        item = quality.normalize_facility(record)
        self.assertEqual(item["availability_kind"], "reported")
        self.assertFalse(item["has_realtime_data"])
        self.assertEqual(item["free_capacity"], 12)

    def test_live_wins_over_unverified_reported(self):
        reported = facility("municipality", kind="reported", free=43, capacity=100)
        live = facility("sensor", kind="live", free=3, capacity=100, updated=stamp())
        result = quality.merge_facilities([], [reported, live])[0]
        self.assertEqual(result["free_capacity"], 3)
        self.assertEqual(result["availability_kind"], "live")

    def test_no_negative_fractional_nan_or_beyond_capacity(self):
        for raw in (-2, float("nan"), "nan", float("inf"), 1.5, 101):
            with self.subTest(value=raw):
                record = facility("bad", kind="live", capacity=100, free=raw)
                item = quality.normalize_facility(record)
                self.assertFalse(item["has_realtime_data"])
                self.assertNotIn("free_capacity", item)

    def test_missing_timestamp_legacy_claim_is_disclosed(self):
        item = quality.normalize_facility(facility("older", kind="live", free=2))
        self.assertEqual(item["availability_freshness"], "unverified")

    def test_nearby_distinct_garages_not_merged(self):
        a = facility("source_a", name="Central Garage")
        b = facility("source_b", name="Riverside Garage", latitude=50.93805)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_same_name_official_and_osm_merged(self):
        a = facility("osm", name="Parking Stadtmitte")
        b = facility("city", name="Stadtmitte Parking", latitude=50.93809)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 1)

    def test_distant_same_name_not_merged(self):
        a = facility("osm")
        b = facility("city", latitude=50.941)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_single_bays_not_merged(self):
        a = facility("melbourne", name="Bay", mergeable=False)
        b = facility("city", name="Bay", mergeable=False)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_street_and_garage_never_merged(self):
        a = facility("osm", name="Street Lot", category="street")
        b = facility("official", name="Street Lot", category="multi_storey")
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_official_fee_wins_instead_of_any_paid_true(self):
        osm = facility("osm", fee="yes")
        official = facility("city", kind="live", fee="no", free=12, updated=stamp())
        item = quality.merge_facilities([], [osm, official])[0]
        self.assertEqual(item["fee"], "no")

    def test_price_navigation_and_osm_url_enriched(self):
        osm = facility("osm", fee="yes")
        osm["price"] = "2 EUR/hour"
        osm["osm_url"] = "https://www.openstreetmap.org/way/123"
        official = facility("city", kind="live", free=50, updated=stamp())
        item = quality.merge_facilities([], [osm, official])[0]
        self.assertEqual(item["osm_url"], osm["osm_url"])
        self.assertEqual(item["price"], osm["price"])

    def test_capacity_lower_than_winning_free_is_not_merged(self):
        reported = facility("provider", kind="reported", free=90)
        bad_metadata = facility("osm", capacity=10)
        merged = quality.merge_facilities([], [bad_metadata, reported])[0]
        self.assertNotEqual(merged.get("capacity"), 10)

    def test_provider_does_not_mutate_inputs(self):
        one = facility("osm")
        two = facility("official", kind="live", free=1, updated=stamp())
        quality.merge_facilities([one], [two])
        self.assertNotIn("data_sources", two)
        self.assertNotIn("availability_kind", one)

    def test_generic_adjacent_names_are_not_collapsed(self):
        a = facility("osm", name="Parking", longitude=6.982)
        b = facility("city", name="Garage", longitude=6.98210)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_exact_provider_id_is_not_duplicate_far_away(self):
        a = facility("city", latitude=50.938)
        b = facility("city", latitude=50.942)
        self.assertEqual(len(quality.merge_facilities([], [a, b])), 2)

    def test_bad_coordinates_excluded(self):
        bad = facility("city", latitude=float("nan"))
        self.assertEqual(quality.merge_facilities([], [bad]), [])

    def test_estimate_zero_is_valid_not_missing(self):
        a = facility("sbb", kind="estimated")
        a["estimated_occupancy_ratio"] = 0
        result = quality.normalize_facility(a)
        self.assertEqual(result["availability_kind"], "estimated")

    def test_unknown_estimate_rejected(self):
        a = facility("sbb", kind="estimated")
        a["estimated_occupancy_ratio"] = 2
        result = quality.normalize_facility(a)
        self.assertEqual(result["availability_kind"], "static")


if __name__ == "__main__":
    unittest.main()
