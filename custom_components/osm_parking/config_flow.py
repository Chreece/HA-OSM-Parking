from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import selector

from .const import (
    CATEGORIES,
    CONF_DESTINATION_ENTITY,
    CONF_GOLEMIO_API_KEY,
    CONF_GOLEMIO_ENABLED,
    CONF_INCLUDE_RESTRICTED,
    CONF_MAX_RESULTS,
    CONF_RADIUS_M,
    CONF_TDX_CLIENT_ID,
    CONF_TDX_CLIENT_SECRET,
    CONF_TDX_ENABLED,
    CONF_TFNSW_API_KEY,
    CONF_TFNSW_ENABLED,
    DEFAULT_INCLUDE_RESTRICTED,
    DEFAULT_MAX_PER_CATEGORY,
    DEFAULT_RADIUS_M,
    DOMAIN,
    PROVIDER_SECRET_KEYS,
    enabled_key,
)


def _category_schema(defaults: dict[str, Any]) -> dict[Any, Any]:
    """Build category enable/disable controls."""
    schema: dict[Any, Any] = {}
    for category in CATEGORIES:
        schema[
            vol.Optional(
                enabled_key(category),
                default=bool(defaults.get(enabled_key(category), True)),
            )
        ] = selector.BooleanSelector()
    return schema


def _first_float(
    attrs: dict[str, Any], names: tuple[str, ...]
) -> float | None:
    """Return the first valid numeric attribute."""
    for name in names:
        if name not in attrs:
            continue
        try:
            return float(attrs[name])
        except (TypeError, ValueError):
            continue
    return None


def _state_coordinates(state: State | None) -> tuple[float, float] | None:
    """Return valid destination coordinates from a state."""
    if state is None:
        return None

    if str(state.state or "").strip().lower() in {
        "",
        "unknown",
        "unavailable",
        "none",
    }:
        return None

    lat = _first_float(state.attributes, ("latitude", "lat"))
    lon = _first_float(state.attributes, ("longitude", "lon", "lng"))
    if lat is None or lon is None:
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def _destination_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """Return all currently usable destination entities."""
    options: list[selector.SelectOptionDict] = []

    for state in hass.states.async_all():
        coordinates = _state_coordinates(state)
        if coordinates is None:
            continue

        lat, lon = coordinates
        friendly_name = str(
            state.attributes.get("friendly_name") or state.entity_id
        )
        options.append(
            selector.SelectOptionDict(
                value=state.entity_id,
                label=(
                    f"{friendly_name} ({state.entity_id}) "
                    f"— {lat:.5f}, {lon:.5f}"
                ),
            )
        )

    return sorted(options, key=lambda item: item["label"].casefold())


def _schema(
    hass: HomeAssistant,
    defaults: dict[str, Any],
    *,
    include_provider_credentials: bool = False,
) -> vol.Schema:
    """Build the complete configuration form."""
    destination_options = _destination_options(hass)
    current_destination = str(
        defaults.get(CONF_DESTINATION_ENTITY, "")
    ).strip()

    destination_field = (
        vol.Required(CONF_DESTINATION_ENTITY, default=current_destination)
        if current_destination
        else vol.Required(CONF_DESTINATION_ENTITY)
    )

    fields: dict[Any, Any] = {
        destination_field: selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=destination_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=bool(current_destination),
            )
        ),
        vol.Required(
            CONF_RADIUS_M,
            default=int(defaults.get(CONF_RADIUS_M, DEFAULT_RADIUS_M)),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=100,
                max=10000,
                step=100,
                unit_of_measurement="m",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_INCLUDE_RESTRICTED,
            default=bool(
                defaults.get(CONF_INCLUDE_RESTRICTED, DEFAULT_INCLUDE_RESTRICTED)
            ),
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_MAX_RESULTS,
            default=int(defaults.get(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY)),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=25,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }
    fields.update(_category_schema(defaults))

    if include_provider_credentials:
        fields.update(
            {
                vol.Optional(
                    CONF_GOLEMIO_ENABLED,
                    default=bool(defaults.get(CONF_GOLEMIO_ENABLED, True)),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_GOLEMIO_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        autocomplete="new-password",
                    )
                ),
                vol.Optional(
                    CONF_TFNSW_ENABLED,
                    default=bool(defaults.get(CONF_TFNSW_ENABLED, True)),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_TFNSW_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        autocomplete="new-password",
                    )
                ),
                vol.Optional(
                    CONF_TDX_ENABLED,
                    default=bool(defaults.get(CONF_TDX_ENABLED, True)),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_TDX_CLIENT_ID): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        autocomplete="new-password",
                    )
                ),
                vol.Optional(CONF_TDX_CLIENT_SECRET): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        autocomplete="new-password",
                    )
                ),
            }
        )

    return vol.Schema(fields)


class OsmParkingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the OSM Parking config flow."""

    VERSION = 2
    MINOR_VERSION = 5

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a new parking search."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = dict(user_input)
            destination_entity = str(data[CONF_DESTINATION_ENTITY]).strip()

            if _state_coordinates(self.hass.states.get(destination_entity)) is None:
                errors[CONF_DESTINATION_ENTITY] = "invalid_destination_entity"
            else:
                await self.async_set_unique_id(destination_entity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=destination_entity,
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input or {}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowWithReload:
        """Return the options flow."""
        return OsmParkingOptionsFlow()


class OsmParkingOptionsFlow(OptionsFlowWithReload):
    """Handle editable OSM Parking options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save options."""
        errors: dict[str, str] = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            destination_entity = str(
                user_input[CONF_DESTINATION_ENTITY]
            ).strip()
            current_destination = str(
                defaults.get(CONF_DESTINATION_ENTITY, "")
            ).strip()

            if (
                destination_entity != current_destination
                and _state_coordinates(
                    self.hass.states.get(destination_entity)
                ) is None
            ):
                errors[CONF_DESTINATION_ENTITY] = "invalid_destination_entity"
            else:
                data = dict(user_input)
                # Password selectors are intentionally never pre-filled.
                # Leaving one blank keeps the previously stored credential.
                for key in PROVIDER_SECRET_KEYS:
                    value = str(data.get(key, "") or "").strip()
                    if value:
                        data[key] = value
                    elif defaults.get(key):
                        data[key] = defaults[key]
                    else:
                        data.pop(key, None)
                return self.async_create_entry(data=data)
            defaults = {**defaults, **user_input}

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                self.hass,
                defaults,
                include_provider_credentials=True,
            ),
            errors=errors,
        )
