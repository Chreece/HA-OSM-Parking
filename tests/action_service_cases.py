"""Isolated tests for the response-only coordinate parking action."""

from __future__ import annotations

import asyncio
from enum import Enum
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "osm_parking"


class Invalid(Exception):
    pass


class Marker:
    def __init__(self, key):
        self.key = key


class Schema:
    def __init__(self, value):
        self.schema = value


def _make_voluptuous():
    vol = types.ModuleType("voluptuous")
    vol.Invalid = Invalid
    vol.Optional = lambda key, *args, **kwargs: Marker(key)
    vol.Required = lambda key, *args, **kwargs: Marker(key)
    vol.Coerce = lambda typ: lambda value: typ(value)
    vol.Range = lambda **kwargs: lambda value: value
    vol.All = lambda *validators: lambda value: value
    vol.Schema = Schema
    sys.modules["voluptuous"] = vol


class ConfigEntryState(Enum):
    LOADED = "loaded"
    NOT_LOADED = "not_loaded"


class FakeError(Exception):
    def __init__(self, *args, translation_domain=None, translation_key=None, **kwargs):
        super().__init__(*args)
        self.translation_domain = translation_domain
        self.translation_key = translation_key


class ServiceCall:
    def __init__(self, data):
        self.data = data


class SupportsResponse(Enum):
    NONE = 0
    OPTIONAL = 1
    ONLY = 2


class FakeServices:
    def __init__(self):
        self.registered = {}

    def has_service(self, domain, service):
        return (domain, service) in self.registered

    def async_register(self, domain, service, handler, **kwargs):
        self.registered[(domain, service)] = (handler, kwargs)


class FakeConfigEntries:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def async_entries(self, domain):
        return [entry for entry in self.entries if entry.domain == domain]

    def async_get_entry(self, entry_id):
        return next((entry for entry in self.entries if entry.entry_id == entry_id), None)


class Hass:
    def __init__(self, entries=()):
        self.services = FakeServices()
        self.config_entries = FakeConfigEntries(entries)


class Entry:
    def __init__(self, entry_id, coordinator, state=ConfigEntryState.LOADED, domain="osm_parking"):
        self.entry_id = entry_id
        self.domain = domain
        self.state = state
        self.runtime_data = types.SimpleNamespace(coordinator=coordinator)


class Coordinator:
    def __init__(self):
        self.calls = []
        self.data = {"sentinel": "unchanged"}

    async def async_search_coordinates(self, latitude, longitude, **kwargs):
        self.calls.append((latitude, longitude, kwargs))
        return {
            "suggestions": [
                {
                    "provider": "osm",
                    "provider_id": "osm:1",
                    "name": "Central Garage",
                    "latitude": latitude,
                    "longitude": longitude,
                    "distance_m": 123,
                    "category": "underground",
                    "availability_kind": "static",
                    "fee": "yes",
                    "data_sources": ["openstreetmap"],
                }
            ],
            "destination_latitude": latitude,
            "destination_longitude": longitude,
            "radius_m": kwargs.get("radius_m") or 1500,
            "parking_types": list(kwargs.get("parking_types") or ("underground",)),
            "max_results_per_category": kwargs.get("max_results") or 5,
            "include_restricted": bool(kwargs.get("include_restricted")),
            "category_counts": {
                "paid": 0,
                "open": 0,
                "street": 0,
                "underground": 1,
                "multi_storey": 0,
                "park_and_ride": 0,
                "other": 0,
            },
            "providers_queried": ["openstreetmap", "broken_provider"],
            "providers_contributing": ["openstreetmap"],
            "winning_sources": ["openstreetmap"],
            "providers_used": ["openstreetmap"],
            "provider_errors": {"broken_provider": "TimeoutError"},
            "provider_load_errors": {},
            "partial_data": True,
            "realtime_result_count": 0,
            "reported_result_count": 0,
            "estimated_result_count": 0,
        }


class FailingCoordinator(Coordinator):
    async def async_search_coordinates(self, *args, **kwargs):
        raise UpdateFailed("network")


class BadOptionsCoordinator(Coordinator):
    async def async_search_coordinates(self, *args, **kwargs):
        raise ValueError("bad")


def _make_homeassistant():
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    sys.modules["homeassistant"] = ha

    ce = types.ModuleType("homeassistant.config_entries")
    ce.ConfigEntry = Entry
    ce.ConfigEntryState = ConfigEntryState
    sys.modules["homeassistant.config_entries"] = ce

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = Hass
    core.ServiceCall = ServiceCall
    core.ServiceResponse = dict
    core.SupportsResponse = SupportsResponse
    sys.modules["homeassistant.core"] = core

    exc = types.ModuleType("homeassistant.exceptions")
    exc.HomeAssistantError = type("HomeAssistantError", (FakeError,), {})
    exc.ServiceValidationError = type("ServiceValidationError", (FakeError,), {})
    sys.modules["homeassistant.exceptions"] = exc

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers

    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.ensure_list = lambda value: value if isinstance(value, list) else [value]
    cv.string = lambda value: str(value)
    cv.boolean = lambda value: bool(value)
    sys.modules["homeassistant.helpers.config_validation"] = cv
    helpers.config_validation = cv

    update = types.ModuleType("homeassistant.helpers.update_coordinator")
    update.UpdateFailed = type("UpdateFailed", (Exception,), {})
    sys.modules["homeassistant.helpers.update_coordinator"] = update
    return exc, update.UpdateFailed


def load(qualified, path):
    spec = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_make_voluptuous()
ServiceValidationErrorModule, UpdateFailed = _make_homeassistant()
for name, folder in (
    ("custom_components", ROOT.parent),
    ("custom_components.osm_parking", ROOT),
):
    package = types.ModuleType(name)
    package.__path__ = [str(folder)]
    sys.modules[name] = package

const = load("custom_components.osm_parking.const", ROOT / "const.py")
service = load("custom_components.osm_parking.services", ROOT / "services.py")


class ActionTests(unittest.IsolatedAsyncioTestCase):
    async def registered(self, entries):
        hass = Hass(entries)
        await service.async_register_services(hass)
        handler, kwargs = hass.services.registered[("osm_parking", "find_parking")]
        return hass, handler, kwargs

    async def test_registers_once_and_requires_response(self):
        hass = Hass()
        await service.async_register_services(hass)
        await service.async_register_services(hass)
        self.assertEqual(len(hass.services.registered), 1)
        _, kwargs = hass.services.registered[("osm_parking", "find_parking")]
        self.assertIs(kwargs["supports_response"], SupportsResponse.ONLY)
        self.assertIsInstance(kwargs["schema"], Schema)

    async def test_one_loaded_entry_is_selected_automatically(self):
        coordinator = Coordinator()
        _, handler, _ = await self.registered([Entry("one", coordinator)])
        response = await handler(ServiceCall({
            "latitude": 50.11,
            "longitude": 8.68,
        }))
        self.assertEqual(response["count"], 1)
        self.assertEqual(response["parkings"][0]["name"], "Central Garage")
        self.assertEqual(response["radius_m"], 1500)
        self.assertEqual(response["unavailable_sources"], ["broken_provider"])
        self.assertEqual(
            response["providers_queried"],
            ["openstreetmap", "broken_provider"],
        )
        self.assertEqual(response["providers_contributing"], ["openstreetmap"])
        self.assertEqual(response["winning_sources"], ["openstreetmap"])
        self.assertEqual(response["providers_used"], ["openstreetmap"])
        self.assertEqual(response["availability_counts"], {
            "live": 0,
            "reported": 0,
            "estimated": 0,
        })
        self.assertEqual(coordinator.data, {"sentinel": "unchanged"})

    async def test_explicit_overrides_are_passed_without_becoming_state(self):
        coordinator = Coordinator()
        _, handler, _ = await self.registered([Entry("one", coordinator)])
        response = await handler(ServiceCall({
            "latitude": 37.98,
            "longitude": 23.73,
            "radius_m": 2200,
            "parking_types": ("street", "underground"),
            "max_results": 9,
            "include_restricted": True,
        }))
        _, _, kwargs = coordinator.calls[-1]
        self.assertEqual(kwargs["radius_m"], 2200)
        self.assertEqual(kwargs["parking_types"], ("street", "underground"))
        self.assertEqual(kwargs["max_results"], 9)
        self.assertIs(kwargs["include_restricted"], True)
        self.assertEqual(response["parking_types"], ["street", "underground"])

    async def test_explicit_config_entry_selects_credentials_context(self):
        first, second = Coordinator(), Coordinator()
        entries = [Entry("one", first), Entry("two", second)]
        _, handler, _ = await self.registered(entries)
        await handler(ServiceCall({
            "config_entry_id": "two",
            "latitude": 1.3,
            "longitude": 103.8,
        }))
        self.assertEqual(len(first.calls), 0)
        self.assertEqual(len(second.calls), 1)

    async def test_missing_or_ambiguous_entries_are_translatable_validation_errors(self):
        scenarios = [
            ([], {}, "action_no_loaded_entry"),
            ([Entry("one", Coordinator()), Entry("two", Coordinator())], {}, "action_multiple_loaded_entries"),
            ([Entry("one", Coordinator())], {"config_entry_id": "missing"}, "action_entry_not_found"),
            ([Entry("one", Coordinator(), ConfigEntryState.NOT_LOADED)], {"config_entry_id": "one"}, "action_entry_not_loaded"),
        ]
        for entries, extra, key in scenarios:
            with self.subTest(key=key):
                _, handler, _ = await self.registered(entries)
                with self.assertRaises(ServiceValidationErrorModule.ServiceValidationError) as raised:
                    await handler(ServiceCall({
                        **extra,
                        "latitude": 50.1,
                        "longitude": 8.6,
                    }))
                self.assertEqual(raised.exception.translation_key, key)

    async def test_invalid_search_options_and_operational_failure_use_correct_exception_type(self):
        for coordinator, expected_key, expected_type in [
            (BadOptionsCoordinator(), "action_invalid_search_options", ServiceValidationErrorModule.ServiceValidationError),
            (FailingCoordinator(), "action_search_failed", ServiceValidationErrorModule.HomeAssistantError),
        ]:
            with self.subTest(key=expected_key):
                _, handler, _ = await self.registered([Entry("one", coordinator)])
                with self.assertRaises(expected_type) as raised:
                    await handler(ServiceCall({
                        "latitude": 50.1,
                        "longitude": 8.6,
                    }))
                self.assertEqual(raised.exception.translation_key, expected_key)

    def test_parking_type_validation_rejects_empty_duplicates_and_unknowns(self):
        for value in ([], ["street", "street"], ["future"], [1]):
            with self.subTest(value=value):
                with self.assertRaises(Invalid):
                    service._parking_types(value)
        self.assertEqual(
            service._parking_types(["street", "underground"]),
            ("street", "underground"),
        )

    def test_response_is_json_serializable_and_contains_no_credentials_or_raw_errors(self):
        search = {
            "suggestions": [{"name": "P", "latitude": 1.0, "longitude": 2.0}],
            "destination_latitude": 1.0,
            "destination_longitude": 2.0,
            "radius_m": 500,
            "parking_types": ["open"],
            "max_results_per_category": 3,
            "include_restricted": False,
            "category_counts": {category: 0 for category in const.CATEGORIES},
            "providers_used": ["openstreetmap"],
            "provider_errors": {"secret-provider": "SECRET api key"},
            "provider_load_errors": {"broken": "ImportError"},
            "partial_data": True,
            "realtime_result_count": 0,
            "reported_result_count": 0,
            "estimated_result_count": 0,
        }
        result = service._response(search)
        json.dumps(result, allow_nan=False)
        serialized = json.dumps(result)
        self.assertNotIn("SECRET", serialized)
        self.assertEqual(result["unavailable_sources"], ["broken", "secret-provider"])


class TranslationTests(unittest.TestCase):
    def test_all_locales_describe_action_fields_and_exceptions(self):
        files = [ROOT / "strings.json", *(ROOT / "translations").glob("*.json")]
        expected_fields = {
            "latitude", "longitude", "radius_m", "parking_types",
            "max_results", "include_restricted", "config_entry_id",
        }
        expected_errors = {
            "action_entry_not_found",
            "action_entry_not_loaded",
            "action_no_loaded_entry",
            "action_multiple_loaded_entries",
            "action_invalid_search_options",
            "action_search_failed",
        }
        for path in files:
            with self.subTest(path=path.name):
                obj = json.loads(path.read_text(encoding="utf-8"))
                action = obj["services"]["find_parking"]
                self.assertTrue(action["name"])
                self.assertTrue(action["description"])
                self.assertEqual(set(action["fields"]), expected_fields)
                self.assertTrue(action["sections"]["provider_settings"]["name"])
                self.assertTrue(expected_errors.issubset(obj["exceptions"]))
                self.assertTrue(all(obj["exceptions"][key]["message"] for key in expected_errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
