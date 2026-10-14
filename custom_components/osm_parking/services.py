"""Home Assistant response action for coordinate-based parking searches."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CATEGORIES, DOMAIN

SERVICE_FIND_PARKING = "find_parking"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_RADIUS_M = "radius_m"
ATTR_PARKING_TYPES = "parking_types"
ATTR_MAX_RESULTS = "max_results"
ATTR_INCLUDE_RESTRICTED = "include_restricted"


def _parking_types(value: Any) -> tuple[str, ...]:
    """Validate and preserve a unique list of supported parking categories."""
    values = cv.ensure_list(value)
    if (
        not values
        or any(not isinstance(item, str) or item not in CATEGORIES for item in values)
        or len(values) != len(set(values))
    ):
        raise vol.Invalid("Select one or more unique supported parking types")
    return tuple(values)


FIND_PARKING_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_LATITUDE): vol.All(
            vol.Coerce(float),
            vol.Range(min=-90, max=90),
        ),
        vol.Required(ATTR_LONGITUDE): vol.All(
            vol.Coerce(float),
            vol.Range(min=-180, max=180),
        ),
        vol.Optional(ATTR_RADIUS_M): vol.All(
            vol.Coerce(int),
            vol.Range(min=100, max=10_000),
        ),
        vol.Optional(ATTR_PARKING_TYPES): _parking_types,
        vol.Optional(ATTR_MAX_RESULTS): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=25),
        ),
        vol.Optional(ATTR_INCLUDE_RESTRICTED): cv.boolean,
    }
)


def _loaded_entry(
    hass: HomeAssistant,
    requested_id: str | None,
) -> ConfigEntry:
    """Resolve the provider settings/credentials entry for an action call."""
    if requested_id:
        entry = hass.config_entries.async_get_entry(requested_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_entry_not_found",
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_entry_not_loaded",
            )
        if getattr(entry, "runtime_data", None) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_entry_not_loaded",
            )
        return entry

    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and getattr(entry, "runtime_data", None) is not None
    ]
    if not loaded:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_no_loaded_entry",
        )
    if len(loaded) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_multiple_loaded_entries",
        )
    return loaded[0]


def _response(search: dict[str, Any]) -> ServiceResponse:
    """Return only JSON-safe parking data and useful search metadata."""
    parkings = [dict(item) for item in search["suggestions"]]
    unavailable = sorted(
        {
            *search.get("provider_errors", {}).keys(),
            *search.get("provider_load_errors", {}).keys(),
        }
    )
    return {
        "parkings": parkings,
        "count": len(parkings),
        "latitude": search["destination_latitude"],
        "longitude": search["destination_longitude"],
        "radius_m": search["radius_m"],
        "parking_types": list(search["parking_types"]),
        "max_results_per_category": search["max_results_per_category"],
        "include_restricted": search["include_restricted"],
        "category_counts": dict(search["category_counts"]),
        "providers_used": list(search["providers_used"]),
        "partial_data": bool(search["partial_data"]),
        "unavailable_sources": unavailable,
        "availability_counts": {
            "live": int(search["realtime_result_count"]),
            "reported": int(search["reported_result_count"]),
            "estimated": int(search["estimated_result_count"]),
        },
    }


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration actions exactly once."""
    if hass.services.has_service(DOMAIN, SERVICE_FIND_PARKING):
        return

    async def async_find_parking(call: ServiceCall) -> ServiceResponse:
        """Search parking around arbitrary coordinates and return the list."""
        entry = _loaded_entry(
            hass,
            call.data.get(ATTR_CONFIG_ENTRY_ID),
        )
        coordinator = entry.runtime_data.coordinator

        try:
            search = await coordinator.async_search_coordinates(
                call.data[ATTR_LATITUDE],
                call.data[ATTR_LONGITUDE],
                radius_m=call.data.get(ATTR_RADIUS_M),
                parking_types=call.data.get(ATTR_PARKING_TYPES),
                max_results=call.data.get(ATTR_MAX_RESULTS),
                include_restricted=call.data.get(ATTR_INCLUDE_RESTRICTED),
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_invalid_search_options",
            ) from err
        except UpdateFailed as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_search_failed",
            ) from err

        return _response(search)

    hass.services.async_register(
        DOMAIN,
        SERVICE_FIND_PARKING,
        async_find_parking,
        schema=FIND_PARKING_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
