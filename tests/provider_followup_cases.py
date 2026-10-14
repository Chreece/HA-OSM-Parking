"""Extra regressions from inspecting real official endpoint responses."""
import copy
import unittest
from unittest.mock import patch
import provider_safety_cases as support
from custom_components.osm_parking.providers import resilient_http as http
from custom_components.osm_parking.providers.toulouse import ToulouseParkingProvider
from custom_components.osm_parking.providers.netherlands_rdw import NetherlandsRdwProvider


class Followup(unittest.IsolatedAsyncioTestCase):
    async def test_expired_cooldown_is_renewed_after_another_failure(self):
        first = http.Endpoint('https://city.example/v2', {})
        second = http.Endpoint('https://city.example/v1', {})
        pool = http.EndpointPool((first, second))
        pool._retry_at[first.url] = 500
        with patch.object(http, 'monotonic', return_value=1000):
            session = support.Session(support.Response(status=503), support.Response({'rows': [2]}))
            self.assertEqual(await pool.fetch(session, lambda p: p['rows']), [2])
            self.assertEqual(pool._retry_at[first.url], 1300)
        with patch.object(http, 'monotonic', return_value=1001):
            session = support.Session(support.Response({'rows': [3]}))
            self.assertEqual(await pool.fetch(session, lambda p: p['rows']), [3])
            self.assertEqual([call[0] for call in session.calls], [second.url])

    async def test_long_server_rate_limit_is_not_shortened(self):
        pool = http.EndpointPool((http.Endpoint('https://city.example/v2', {}), http.Endpoint('https://city.example/v1', {})))
        with patch.object(http, 'monotonic', return_value=1000):
            with self.assertRaises(http.SourceUnavailable) as raised:
                await pool.fetch(support.Session(support.Response(status=429, headers={'Retry-After': '600'})), lambda p: p)
        self.assertEqual(raised.exception.retry_after_seconds, 600)
        self.assertEqual(set(pool._retry_at.values()), {1600})

    def record(self):
        # Observed municipality field names; no live vacancy is present.
        return {'id': '31555-P-0001', 'nom': 'ARNAUD BERNARD',
                'ylat': 43.6106, 'xlong': 1.43922, 'nb_places': 305,
                'type_ouvrage': 'Enterré', 'type_usager': 'tous, riverains',
                'gratuit': 'F', 'public': 'T', 'gestionnaire': 'INDIGO'}

    def parse(self, row):
        return ToulouseParkingProvider._normalize(row, 43.61, 1.44, 1000)

    def test_toulouse_false_flag_means_paid_not_unknown(self):
        result = self.parse(self.record())
        self.assertEqual(result['fee'], 'yes')
        self.assertEqual(result['operator'], 'INDIGO')
        self.assertEqual(result['availability_kind'], 'static')
        self.assertNotIn('free_capacity', result)

    def test_toulouse_true_flag_means_free(self):
        row = self.record(); row['gratuit'] = 'T'
        self.assertEqual(self.parse(row)['fee'], 'no')

    def test_toulouse_private_and_resident_only_access(self):
        row = self.record(); row['public'] = 'F'
        self.assertEqual(self.parse(row)['access'], 'private')
        row = self.record(); row['type_usager'] = 'résidents'
        self.assertEqual(self.parse(row)['access'], 'permit')
        row['type_usager'] = 'tous, residents'
        self.assertEqual(self.parse(row)['access'], 'unknown')

    def test_toulouse_record_adaptation_does_not_mutate_cache(self):
        row = self.record(); original = copy.deepcopy(row)
        self.parse(row)
        self.assertEqual(row, original)

    def test_toulouse_malformed_row_does_not_discard_good_sites(self):
        rows = [None, {'id': 'bad', 'ylat': [], 'xlong': {}}, self.record()]
        valid = ToulouseParkingProvider._catalog({'results': rows, 'total_count': 3})
        self.assertEqual(valid, [self.record()])

    def test_rdw_authoritative_geometry_keeps_dutch_coverage_without_querying_german_cities(self):
        provider = NetherlandsRdwProvider()
        for lat, lon, name in (
            (52.3676, 4.9041, "Amsterdam"),
            (51.9244, 4.4777, "Rotterdam"),
            (50.8514, 5.6910, "Maastricht"),
            (53.2194, 6.5665, "Groningen"),
            (52.2215, 6.8937, "Enschede"),
            # Border buffer: a search near Aachen can legitimately include
            # Dutch parking within the integration's maximum 10 km radius.
            (50.7753, 6.0839, "Aachen-border"),
        ):
            with self.subTest(place=name):
                self.assertTrue(provider.applies(lat, lon))

        for lat, lon, name in (
            (50.9375, 6.9603, "Cologne"),
            (51.2277, 6.7735, "Dusseldorf"),
            (51.5136, 7.4653, "Dortmund"),
            (50.1109, 8.6821, "Frankfurt"),
        ):
            with self.subTest(place=name):
                self.assertFalse(provider.applies(lat, lon))


if __name__ == '__main__':
    unittest.main(verbosity=2)
