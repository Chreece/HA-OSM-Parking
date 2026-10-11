from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any

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
    CONF_REFRESH_MINUTES,
    DEFAULT_MAX_PER_CATEGORY,
    DOMAIN,
    PLATFORMS,
    enabled_key,
    max_key,
)
from .coordinator import OsmParkingCoordinator

CARD_URL = f"/{DOMAIN}/osm-parking-map-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "osm-parking-map-card.js"

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


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide frontend resources."""
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=False)]
        )
    except RuntimeError:
        # The same URL can already be registered after a reload.
        pass
    add_extra_js_url(hass, CARD_URL)
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
            hass.async_create_task(coordinator.async_request_refresh())

        remove_listener = async_track_state_change_event(
            hass, [destination_entity], _destination_changed
        )

    entry.runtime_data = OsmParkingRuntimeData(
        coordinator=coordinator,
        remove_destination_listener=remove_listener,
    )

    # The coordinator deliberately returns a waiting state while the configured
    # destination entity is still restoring during Home Assistant startup.
    # This keeps the integration loaded, so the state-change listener above can
    # refresh it immediately once the destination has valid coordinates.
    await coordinator.async_config_entry_first_refresh()

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
        data.pop(CONF_REFRESH_MINUTES, None)
        options.pop(CONF_REFRESH_MINUTES, None)
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
