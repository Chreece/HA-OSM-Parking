from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers import selector

from .const import (
    CATEGORIES,
    CONF_DESTINATION_ENTITY,
    CONF_INCLUDE_RESTRICTED,
    CONF_MAX_RESULTS,
    CONF_RADIUS_M,
    CONF_REFRESH_MINUTES,
    DEFAULT_INCLUDE_RESTRICTED,
    DEFAULT_MAX_PER_CATEGORY,
    DEFAULT_RADIUS_M,
    DEFAULT_REFRESH_MINUTES,
    DOMAIN,
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


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the complete configuration form."""
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_DESTINATION_ENTITY,
            default=defaults.get(CONF_DESTINATION_ENTITY, "sensor.termine_geocode"),
        ): selector.EntitySelector(selector.EntitySelectorConfig()),
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
            CONF_REFRESH_MINUTES,
            default=str(defaults.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES)),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["5", "10", "15", "30", "60", "120"],
                mode=selector.SelectSelectorMode.DROPDOWN,
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
    return vol.Schema(fields)


def _normalise_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise selector values to their stored types."""
    data = dict(user_input)
    data[CONF_REFRESH_MINUTES] = int(data[CONF_REFRESH_MINUTES])
    return data


class OsmParkingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the OSM Parking config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a new parking search."""
        if user_input is not None:
            data = _normalise_input(user_input)
            await self.async_set_unique_id(str(data[CONF_DESTINATION_ENTITY]).strip())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=str(data[CONF_DESTINATION_ENTITY]), data=data
            )

        return self.async_show_form(step_id="user", data_schema=_schema({}))

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
        if user_input is not None:
            return self.async_create_entry(data=_normalise_input(user_input))

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
