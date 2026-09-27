from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CATEGORIES,
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


@dataclass
class OsmParkingRuntimeData:
    coordinator: OsmParkingCoordinator


type OsmParkingConfigEntry = ConfigEntry[OsmParkingRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide frontend resources."""
    if CARD_PATH.is_file():
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
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = OsmParkingRuntimeData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OsmParkingConfigEntry
) -> bool:
    """Unload an OSM Parking config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate legacy entries to the current category model."""
    if config_entry.version < 2:
        data = dict(config_entry.data)
        legacy_max = int(data.get(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY))
        for category in CATEGORIES:
            data.setdefault(enabled_key(category), True)
            data.setdefault(max_key(category), legacy_max)
        hass.config_entries.async_update_entry(
            config_entry, data=data, version=2, minor_version=2
        )
    return True
