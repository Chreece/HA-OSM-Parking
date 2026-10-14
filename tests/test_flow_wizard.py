"""Contract tests for the four-step Home Assistant OSM Parking wizard.

The real flow is imported with lightweight Home Assistant and Voluptuous
stubs so CI can verify navigation and credential persistence without a full
Home Assistant installation or external network.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "osm_parking"
_UNSET = object()


class Marker:
    def __init__(self, key, default=_UNSET, required=False):
        self.key = key
        self.default = default
        self.required = required

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return isinstance(other, Marker) and self.key == other.key


class Schema:
    def __init__(self, schema):
        self.schema = schema


class ConfigBase:
    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_form(self, *, step_id, data_schema, errors=None, **kwargs):
        return {
            "type": "form",
            "step_id": step_id,
            "schema": data_schema,
            "errors": errors or {},
            **kwargs,
        }

    def async_create_entry(self, *, data, title=None):
        return {"type": "create_entry", "title": title, "data": dict(data)}

    async def async_set_unique_id(self, uid):
        self.unique_id = uid

    def _abort_if_unique_id_configured(self):
        if getattr(self, "unique_id", None) == "already-configured":
            raise ValueError("already_configured")


class State:
    def __init__(self, entity_id, state, **attributes):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes


class HassStates:
    def __init__(self, *states):
        self.all_states = list(states)
        self.by_id = {state.entity_id: state for state in states}

    def get(self, entity_id):
        return self.by_id.get(entity_id)

    def async_all(self):
        return list(self.all_states)


class Hass:
    def __init__(self, *states):
        self.states = HassStates(*states)


def _make_stubs():
    vol = types.ModuleType("voluptuous")
    vol.Required = lambda key, default=_UNSET: Marker(key, default, True)
    vol.Optional = lambda key, default=_UNSET: Marker(key, default, False)
    vol.Schema = Schema
    sys.modules["voluptuous"] = vol

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    sys.modules["homeassistant"] = ha
    ce = types.ModuleType("homeassistant.config_entries")
    ce.ConfigFlow = ConfigBase
    ce.OptionsFlowWithReload = ConfigBase
    ce.ConfigFlowResult = dict
    ce.ConfigEntry = type("ConfigEntry", (), {})
    sys.modules["homeassistant.config_entries"] = ce
    ha.config_entries = ce
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = Hass
    core.State = State
    sys.modules["homeassistant.core"] = core
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers
    select = types.ModuleType("homeassistant.helpers.selector")

    class SelectSelectorMode:
        DROPDOWN = "dropdown"

    class NumberSelectorMode:
        BOX = "box"

    class TextSelectorType:
        PASSWORD = "password"

    class Config:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    select.SelectOptionDict = dict
    select.SelectSelectorMode = SelectSelectorMode
    select.NumberSelectorMode = NumberSelectorMode
    select.TextSelectorType = TextSelectorType
    select.SelectSelectorConfig = Config
    select.NumberSelectorConfig = Config
    select.TextSelectorConfig = Config
    select.SelectSelector = lambda config: ("select", config)
    select.NumberSelector = lambda config: ("number", config)
    select.TextSelector = lambda config: ("text", config)
    select.BooleanSelector = lambda: ("boolean", None)
    sys.modules["homeassistant.helpers.selector"] = select
    helpers.selector = select

    for name, folder in (
        ("custom_components", ROOT.parent),
        ("custom_components.osm_parking", ROOT),
    ):
        pkg = sys.modules.get(name)
        if pkg is None:
            pkg = types.ModuleType(name)
            sys.modules[name] = pkg
        pkg.__path__ = [str(folder)]


def load_module(qualified, path):
    spec = importlib.util.spec_from_file_location(qualified, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = obj
    spec.loader.exec_module(obj)
    return obj


_make_stubs()
const = load_module("custom_components.osm_parking.const", ROOT / "const.py")
helper = load_module(
    "custom_components.osm_parking.flow_helpers", ROOT / "flow_helpers.py"
)
wizard = load_module(
    "custom_components.osm_parking.config_flow", ROOT / "config_flow.py"
)


def fields(result):
    return {marker.key: marker for marker in result["schema"].schema}


def destination():
    return State(
        "sensor.destination", "Central Station",
        latitude=50.9384967, longitude=6.9828844,
        friendly_name="Köln Central Station",
    )


def initial_config():
    return {
        "destination_entity": "sensor.destination",
        "radius_m": 1800,
    }


def category_config(categories=("paid", "street")):
    return {
        "parking_types": list(categories),
        "max_results": 8,
        "include_restricted": False,
        "athens_zones_enabled": True,
    }


class WizardFlows(unittest.IsolatedAsyncioTestCase):
    def new_flow(self):
        obj = wizard.OsmParkingConfigFlow()
        obj.hass = Hass(destination(), State("sensor.broken", "unavailable"))
        return obj

    async def test_new_setup_all_four_steps_and_conditional_secrets(self):
        flow = self.new_flow()
        step1 = await flow.async_step_user()
        self.assertEqual(step1["step_id"], "user")
        self.assertEqual(set(fields(step1)), {"destination_entity", "radius_m"})

        step2 = await flow.async_step_user(initial_config())
        self.assertEqual(step2["step_id"], "categories")
        self.assertEqual(
            set(fields(step2)),
            {"parking_types", "max_results", "include_restricted"},
        )
        self.assertEqual(
            fields(step2)["parking_types"].default, list(const.CATEGORIES)
        )

        step3 = await flow.async_step_categories(category_config())
        self.assertEqual(step3["step_id"], "providers")
        self.assertEqual(set(fields(step3)), {"credential_providers"})
        selection = step3["schema"].schema[fields(step3)["credential_providers"]][1]
        self.assertTrue(selection.multiple)
        self.assertEqual(selection.translation_key, "credential_providers")

        step4 = await flow.async_step_providers(
            {"credential_providers": ["golemio", "tdx"]}
        )
        self.assertEqual(step4["step_id"], "credentials")
        self.assertEqual(
            set(fields(step4)),
            {"golemio_api_key", "tdx_client_id", "tdx_client_secret"},
        )
        self.assertNotIn("ura_access_key", fields(step4))
        self.assertEqual(
            step4["description_placeholders"]["selected_providers"],
            "Prague Golemio, Taiwan TDX",
        )
        self.assertTrue(all(
            marker.default is _UNSET for marker in fields(step4).values()
        ))
        self.assertFalse(hasattr(flow, "_final_entry"))

        result = await flow.async_step_credentials({
            "golemio_api_key": " GOP ",
            "tdx_client_id": " ID ",
            "tdx_client_secret": " SECRET ",
        })
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "sensor.destination")
        self.assertEqual(result["data"]["golemio_api_key"], "GOP")
        self.assertEqual(result["data"]["tdx_client_id"], "ID")
        self.assertEqual(result["data"]["tdx_client_secret"], "SECRET")
        self.assertTrue(result["data"]["category_paid_enabled"])
        self.assertFalse(result["data"]["category_open_enabled"])
        self.assertTrue(result["data"]["category_street_enabled"])
        self.assertTrue(result["data"]["golemio_enabled"])
        self.assertTrue(result["data"]["tdx_enabled"])
        self.assertFalse(result["data"]["ura_enabled"])
        self.assertFalse(result["data"]["tfnsw_enabled"])
        self.assertNotIn("athens_zones_enabled", result["data"])
        self.assertNotIn("credential_providers", result["data"])
        self.assertNotIn("parking_types", result["data"])
        self.assertEqual(flow.unique_id, "sensor.destination")

    async def test_no_credential_providers_skips_empty_fourth_page(self):
        flow = self.new_flow()
        await flow.async_step_user(initial_config())
        await flow.async_step_categories(category_config())
        result = await flow.async_step_providers(
            {"credential_providers": []}
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertTrue(all(
            result["data"][enabled] is False
            for enabled, _ in helper.CREDENTIAL_PROVIDERS.values()
        ))
        self.assertNotIn("golemio_api_key", result["data"])

    async def test_no_types_validation_preserves_current_page(self):
        flow = self.new_flow()
        await flow.async_step_user(initial_config())
        result = await flow.async_step_categories(category_config([]))
        self.assertEqual(result["step_id"], "categories")
        self.assertEqual(result["errors"]["base"], "no_parking_types")
        self.assertNotIn("category_paid_enabled", flow._pending)

    async def test_invalid_selection_rejected(self):
        flow = self.new_flow()
        await flow.async_step_user(initial_config())
        await flow.async_step_categories(category_config())
        for selected in (["fake"], ["ura", "ura"], "ura"):
            page = await flow.async_step_providers(
                {"credential_providers": selected}
            )
            self.assertEqual(page["errors"]["base"], "invalid_provider_selection")

    async def test_credentials_require_all_fields_for_tdx(self):
        flow = self.new_flow()
        await flow.async_step_user(initial_config())
        await flow.async_step_categories(category_config())
        await flow.async_step_providers({"credential_providers": ["tdx"]})
        result = await flow.async_step_credentials(
            {"tdx_client_id": "test-client"}
        )
        self.assertEqual(result["step_id"], "credentials")
        self.assertEqual(result["errors"]["tdx_client_secret"], "missing_credentials")
        self.assertNotIn("tdx_client_id", flow._pending)
        done = await flow.async_step_credentials({
            "tdx_client_id": "test-client",
            "tdx_client_secret": "test-secret",
        })
        self.assertEqual(done["type"], "create_entry")
        self.assertEqual(done["data"]["tdx_client_id"], "test-client")

    async def test_invalid_destination_never_proceeds(self):
        flow = self.new_flow()
        result = await flow.async_step_user({
            "destination_entity": "sensor.broken", "radius_m": 1200,
        })
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(
            result["errors"]["destination_entity"],
            "invalid_destination_entity",
        )

    async def test_invalid_search_radius_never_proceeds(self):
        flow = self.new_flow()
        for radius in (99, 10001, float("nan")):
            result = await flow.async_step_user({
                "destination_entity": "sensor.destination",
                "radius_m": radius,
            })
            self.assertEqual(result["errors"]["radius_m"], "invalid_radius")

    async def test_options_restore_and_keep_saved_credentials(self):
        flow = wizard.OsmParkingOptionsFlow()
        flow.hass = Hass(
            State("sensor.restoring", "unavailable", friendly_name="Old location"),
            destination(),
        )
        entry = type("Entry", (), {})()
        entry.data = {
            "destination_entity": "sensor.restoring",
            "radius_m": 1500,
            "golemio_api_key": "ORIGINAL_SECRET",
            "golemio_enabled": True,
            "tdx_client_id": "DORMANT_CLIENT",
            "tdx_client_secret": "DORMANT_SECRET",
            "tdx_enabled": False,
            "category_street_enabled": False,
            "athens_zones_enabled": True,
            "custom_preexisting_setting": "keep_me",
        }
        entry.options = {"radius_m": 2300, "max_results": 4}
        flow.config_entry = entry

        page1 = await flow.async_step_init()
        self.assertEqual(page1["step_id"], "init")
        self.assertEqual(fields(page1)["radius_m"].default, 2300)
        self.assertTrue(
            page1["schema"].schema[fields(page1)["destination_entity"]][1].custom_value
        )

        page2 = await flow.async_step_init({
            "destination_entity": "sensor.restoring", "radius_m": 2600,
        })
        self.assertEqual(page2["step_id"], "categories")
        self.assertNotIn("street", fields(page2)["parking_types"].default)
        self.assertNotIn("athens_zones_enabled", fields(page2))

        page3 = await flow.async_step_categories(
            category_config(["paid", "underground"])
        )
        self.assertEqual(page3["step_id"], "providers")
        self.assertEqual(
            fields(page3)["credential_providers"].default, ["golemio"]
        )

        page4 = await flow.async_step_providers(
            {"credential_providers": ["golemio"]}
        )
        self.assertEqual(set(fields(page4)), {"golemio_api_key"})
        self.assertFalse(fields(page4)["golemio_api_key"].required)
        self.assertIs(fields(page4)["golemio_api_key"].default, _UNSET)
        self.assertNotIn("ORIGINAL_SECRET", str(page4))

        done = await flow.async_step_credentials({"golemio_api_key": ""})
        self.assertEqual(done["type"], "create_entry")
        data = done["data"]
        self.assertEqual(data["destination_entity"], "sensor.restoring")
        self.assertEqual(data["radius_m"], 2600)
        self.assertEqual(data["golemio_api_key"], "ORIGINAL_SECRET")
        self.assertEqual(data["tdx_client_id"], "DORMANT_CLIENT")
        self.assertEqual(data["tdx_client_secret"], "DORMANT_SECRET")
        self.assertFalse(data["tdx_enabled"])
        self.assertEqual(data["custom_preexisting_setting"], "keep_me")
        self.assertFalse(data["category_street_enabled"])
        self.assertTrue(data["category_underground_enabled"])

    async def test_options_disable_previous_provider_without_deleting_secret(self):
        flow = wizard.OsmParkingOptionsFlow()
        flow.hass = Hass(destination())
        entry = type("Entry", (), {})()
        entry.data = {
            "destination_entity": "sensor.destination",
            "radius_m": 1500,
            "ura_enabled": True,
            "ura_access_key": "SECRET_URA",
        }
        entry.options = {"max_results": 6}
        flow.config_entry = entry
        await flow.async_step_init(initial_config())
        await flow.async_step_categories(category_config())
        result = await flow.async_step_providers({"credential_providers": []})
        self.assertEqual(result["type"], "create_entry")
        self.assertFalse(result["data"]["ura_enabled"])
        self.assertEqual(result["data"]["ura_access_key"], "SECRET_URA")

    async def test_provider_defaults_only_enabled_with_saved_credentials(self):
        self.assertEqual(
            helper.selected_credential_providers({
                "golemio_enabled": True,
                "tdx_enabled": True,
                "tdx_client_id": "partial-id",
                "ura_enabled": False,
                "ura_access_key": "unused",
            }),
            ["tdx"],
        )

    async def test_first_float_rejects_boolean_nan_and_inf(self):
        self.assertIsNone(wizard._first_float({"lat": True, "latitude": float("inf")}, ("lat", "latitude")))
        self.assertEqual(wizard._first_float({"lat": "50.9"}, ("lat",)), 50.9)


class LocalizationContracts(unittest.TestCase):
    def test_all_supported_locales_have_four_steps_and_selector_options(self):
        files = [ROOT / "strings.json", *(ROOT / "translations").glob("*.json")]
        self.assertGreaterEqual(len(files), 15)
        for path in files:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                for section, first in (("config", "user"), ("options", "init")):
                    steps = data[section]["step"]
                    self.assertEqual(
                        set(steps), {first, "categories", "providers", "credentials"}
                    )
                    self.assertEqual(
                        set(steps[first]["data"]), {"destination_entity", "radius_m"}
                    )
                    self.assertEqual(
                        set(steps["categories"]["data"]),
                        {"parking_types", "max_results", "include_restricted"},
                    )
                    self.assertEqual(
                        set(steps["providers"]["data"]), {"credential_providers"}
                    )
                    self.assertEqual(
                        set(steps["credentials"]["data"]),
                        set(helper.credential_keys(list(helper.CREDENTIAL_PROVIDERS))),
                    )
                    self.assertIn("{selected_providers}", steps["credentials"]["description"])
                    for error in ("no_parking_types", "invalid_radius", "invalid_max_results", "invalid_provider_selection", "missing_credentials"):
                        self.assertTrue(data[section]["error"][error])
                self.assertEqual(
                    set(data["selector"]["parking_types"]["options"]),
                    set(const.CATEGORIES),
                )
                self.assertEqual(
                    set(data["selector"]["credential_providers"]["options"]),
                    set(helper.CREDENTIAL_PROVIDERS),
                )


if __name__ == "__main__":
    unittest.main()
