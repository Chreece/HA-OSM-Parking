from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {
    "destination_latitude",
    "destination_longitude",
    "latitude",
    "longitude",
    "navigation_url",
    "geo_uri",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    runtime = getattr(entry, "runtime_data", None)
    coordinator = getattr(runtime, "coordinator", None)
    coordinator_data = coordinator.data if coordinator is not None else None
    return async_redact_data(
        {
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "coordinator": coordinator_data,
        },
        TO_REDACT,
    )
