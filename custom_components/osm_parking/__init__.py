from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import uuid
from typing import Any

from homeassistant.components import lovelace
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CATEGORIES,
    CONF_DESTINATION_ENTITY,
    CONF_MAX_RESULTS,
    DEFAULT_MAX_PER_CATEGORY,
    DOMAIN,
    PLATFORMS,
    enabled_key,
    max_key,
)
from .coordinator import OsmParkingCoordinator

CARD_URL = f"/{DOMAIN}/osm-parking-map-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "osm-parking-map-card.js"
CARD_VERSION = "0.3.8"
_CARD_BOOT_TOKEN = uuid.uuid4().hex[:10]
CARD_RESOURCE_URL = f"{CARD_URL}?v={CARD_VERSION}-{_CARD_BOOT_TOKEN}"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class OsmParkingRuntimeData:
    coordinator: OsmParkingCoordinator
    remove_destination_listener: Callable[[], None] | None = None


type OsmParkingConfigEntry = ConfigEntry[OsmParkingRuntimeData]


def _destination_signature(state: State | None) -> tuple[Any, ...]:
    """Return only destination fields that should trigger a parking refresh."""
    if state is None:
        return (None,)

    attrs = state.attributes
    return (
        state.state,
        attrs.get("display_name"),
        attrs.get("friendly_name"),
        attrs.get("latitude"),
        attrs.get("lat"),
        attrs.get("longitude"),
        attrs.get("lon"),
        attrs.get("lng"),
    )


async def _async_register_card_resource(hass: HomeAssistant) -> None:
    """Register the bundled card as a Lovelace module resource.

    Storage-mode resources are the normal Lovelace loading path, so Home
    Assistant loads them before creating custom cards. A per-process token makes
    the module URL new on every Home Assistant start; this allows the frontend
    to recover even if the previous process' resource URL failed to import
    during a restart.

    YAML resource mode is read-only from integrations, so keep the frontend
    extra-module mechanism as a fallback there.
    """
    lovelace_data = hass.data.get(lovelace.LOVELACE_DATA)
    if lovelace_data is None:
        add_extra_js_url(hass, CARD_RESOURCE_URL)
        return

    resources = lovelace_data.resources
    if not isinstance(resources, lovelace.resources.ResourceStorageCollection):
        add_extra_js_url(hass, CARD_RESOURCE_URL)
        return

    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    for item in resources.async_items():
        item_url = str(item.get("url", ""))
        if item_url.split("?", 1)[0] != CARD_URL:
            continue

        if item_url != CARD_RESOURCE_URL:
            await resources.async_update_item(
                item["id"],
                {"url": CARD_RESOURCE_URL},
            )
        return

    await resources.async_create_item(
        {"res_type": "module", "url": CARD_RESOURCE_URL}
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide frontend resources."""
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=True)]
        )
    except RuntimeError:
        # The same URL can already be registered after a reload.
        pass

    await _async_register_card_resource(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: OsmParkingConfigEntry
) -> bool:
    """Set up an OSM Parking config entry."""
    coordinator = OsmParkingCoordinator(hass, entry)

    destination_entity = str(
        entry.options.get(
            CONF_DESTINATION_ENTITY,
            entry.data.get(CONF_DESTINATION_ENTITY, ""),
        )
    ).strip()

    remove_listener: Callable[[], None] | None = None
    if destination_entity:

        @callback
        def _destination_changed(event: Event) -> None:
            """Refresh only when the configured destination meaningfully changes."""
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if _destination_signature(old_state) == _destination_signature(new_state):
                return
            coordinator.async_reset_retry_cycle()
            hass.async_create_task(coordinator.async_request_refresh())

        remove_listener = async_track_state_change_event(
            hass, [destination_entity], _destination_changed
        )

    entry.runtime_data = OsmParkingRuntimeData(
        coordinator=coordinator,
        remove_destination_listener=remove_listener,
    )

    # Do not fail config-entry setup just because every public Overpass
    # endpoint is temporarily unavailable. A failed real fetch enables temporary
    # retry polling in the coordinator; a successful fetch disables it again.
    # A restoring destination still returns a normal waiting state and relies on
    # the destination state-change listener rather than polling.
    await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(
    hass: HomeAssistant, entry: OsmParkingConfigEntry
) -> bool:
    """Unload an OSM Parking config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data.remove_destination_listener is not None:
        entry.runtime_data.remove_destination_listener()
    return unloaded


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate legacy entries to the current event-driven model."""
    data = dict(config_entry.data)
    options = dict(config_entry.options)
    version = config_entry.version
    minor_version = config_entry.minor_version
    changed = False

    if version < 2:
        legacy_max = int(data.get(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY))
        for category in CATEGORIES:
            data.setdefault(enabled_key(category), True)
            data.setdefault(max_key(category), legacy_max)
        version = 2
        minor_version = 2
        changed = True

    if version == 2 and minor_version < 3:
        data.pop("refresh_minutes", None)
        options.pop("refresh_minutes", None)
        minor_version = 3
        changed = True

    if changed:
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=version,
            minor_version=minor_version,
        )

    return True
