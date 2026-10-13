"""Four-step setup and options wizard for OSM Parking.

1. Destination and search distance.
2. Parking types and filters.
3. Credential-requiring providers (multiselect).
4. Only the credentials needed for selected providers, if any.

Changes are committed only when the wizard finishes. Existing credentials are
never prefilled and are preserved even when their provider is deselected.
"""

from __future__ import annotations

import math
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import selector

from .const import (
    CATEGORIES,
    CONF_ATHENS_ZONES_ENABLED,
    CONF_DESTINATION_ENTITY,
    CONF_INCLUDE_RESTRICTED,
    CONF_MAX_RESULTS,
    CONF_RADIUS_M,
    DEFAULT_INCLUDE_RESTRICTED,
    DEFAULT_MAX_PER_CATEGORY,
    DEFAULT_RADIUS_M,
    DOMAIN,
)
from .flow_helpers import (
    CONF_CREDENTIAL_PROVIDERS,
    CONF_PARKING_TYPES,
    CREDENTIAL_PROVIDERS,
    PROVIDER_NAMES,
    category_flags,
    credential_keys,
    credential_provider_flags,
    prepared_credentials,
    selected_categories,
    selected_credential_providers,
    valid_multiselect,
    valid_positive_integer,
)


def _first_float(
    attrs: dict[str, Any], names: tuple[str, ...]
) -> float | None:
    """Return the first finite numeric attribute from the supported aliases."""
    for name in names:
        if name not in attrs or isinstance(attrs[name], bool):
            continue
        try:
            result = float(attrs[name])
            if math.isfinite(result):
                return result
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def _state_coordinates(state: State | None) -> tuple[float, float] | None:
    """Read latitude/longitude only from a usable, non-restoring entity."""
    if state is None:
        return None
    if str(state.state or "").strip().lower() in {
        "", "unknown", "unavailable", "none",
    }:
        return None
    lat = _first_float(state.attributes, ("latitude", "lat"))
    lon = _first_float(state.attributes, ("longitude", "lon", "lng"))
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def _destination_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """List all compatible destination entities with coordinates in the label."""
    choices: list[selector.SelectOptionDict] = []
    for state in hass.states.async_all():
        coords = _state_coordinates(state)
        if coords is None:
            continue
        lat, lon = coords
        name = str(state.attributes.get("friendly_name") or state.entity_id)
        choices.append(
            selector.SelectOptionDict(
                value=state.entity_id,
                label=f"{name} ({state.entity_id}) — {lat:.5f}, {lon:.5f}",
            )
        )
    return sorted(choices, key=lambda entry: entry["label"].casefold())


def _distance_schema(
    hass: HomeAssistant, settings: dict[str, Any]
) -> vol.Schema:
    """Wizard step 1: destination and distance, nothing else."""
    current = str(settings.get(CONF_DESTINATION_ENTITY) or "").strip()
    marker = (
        vol.Required(CONF_DESTINATION_ENTITY, default=current)
        if current
        else vol.Required(CONF_DESTINATION_ENTITY)
    )
    distance = settings.get(CONF_RADIUS_M, DEFAULT_RADIUS_M)
    # Invalid frontend input must re-render a valid form, never crash while
    # computing the default for an error response (NaN/inf/text are possible).
    distance_default = (
        int(distance)
        if valid_positive_integer(distance, 100, 10000)
        else DEFAULT_RADIUS_M
    )
    return vol.Schema({
        marker: selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_destination_options(hass),
                mode=selector.SelectSelectorMode.DROPDOWN,
                # Preserve an existing entity while it is restoring.
                custom_value=bool(current),
            )
        ),
        vol.Required(
            CONF_RADIUS_M,
            default=distance_default,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=100, max=10000, step=100, unit_of_measurement="m",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    })


def _categories_schema(settings: dict[str, Any]) -> vol.Schema:
    """Wizard step 2: simple multiselect and common parking filters."""
    return vol.Schema({
        vol.Required(
            CONF_PARKING_TYPES,
            default=selected_categories(settings),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(CATEGORIES),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_PARKING_TYPES,
                multiple=True,
            )
        ),
        vol.Required(
            CONF_MAX_RESULTS,
            default=int(settings.get(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY)),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=25, step=1, mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_INCLUDE_RESTRICTED,
            default=bool(settings.get(
                CONF_INCLUDE_RESTRICTED, DEFAULT_INCLUDE_RESTRICTED,
            )),
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_ATHENS_ZONES_ENABLED,
            default=bool(settings.get(CONF_ATHENS_ZONES_ENABLED, False)),
        ): selector.BooleanSelector(),
    })


def _providers_schema(settings: dict[str, Any]) -> vol.Schema:
    """Wizard step 3: key-protected providers (none is a valid choice)."""
    return vol.Schema({
        vol.Optional(
            CONF_CREDENTIAL_PROVIDERS,
            default=selected_credential_providers(settings),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(CREDENTIAL_PROVIDERS),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_CREDENTIAL_PROVIDERS,
                multiple=True,
            )
        ),
    })


def _credentials_schema(
    chosen: list[str], settings: dict[str, Any]
) -> vol.Schema:
    """Wizard step 4: selected passwords only, with no pre-filled secrets."""
    fields: dict[Any, Any] = {}
    for key in credential_keys(chosen):
        existing = str(settings.get(key) or "").strip()
        marker = vol.Optional(key) if existing else vol.Required(key)
        fields[marker] = selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD,
                autocomplete="new-password",
            )
        )
    return vol.Schema(fields)


class _WizardSteps:
    """Same second, third and fourth step for setup and options."""

    _pending: dict[str, Any]
    _chosen: list[str]

    async def async_step_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure parking types, maximum count and optional zone overlay."""
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = user_input.get(CONF_PARKING_TYPES, [])
            maximum = user_input.get(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY)
            if not valid_multiselect(chosen, CATEGORIES, allow_empty=False):
                errors["base"] = "no_parking_types"
            elif not valid_positive_integer(maximum, 1, 25):
                errors[CONF_MAX_RESULTS] = "invalid_max_results"
            else:
                self._pending.update(category_flags(chosen))
                self._pending[CONF_MAX_RESULTS] = int(maximum)
                self._pending[CONF_INCLUDE_RESTRICTED] = bool(
                    user_input.get(CONF_INCLUDE_RESTRICTED, False)
                )
                self._pending[CONF_ATHENS_ZONES_ENABLED] = bool(
                    user_input.get(CONF_ATHENS_ZONES_ENABLED, False)
                )
                return await self.async_step_providers()

        return self.async_show_form(
            step_id="categories",
            data_schema=_categories_schema(self._pending),
            errors=errors,
        )

    async def async_step_providers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Multi-select providers that require keys, independently of region."""
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = user_input.get(CONF_CREDENTIAL_PROVIDERS, [])
            if not valid_multiselect(
                chosen, tuple(CREDENTIAL_PROVIDERS), allow_empty=True,
            ):
                errors["base"] = "invalid_provider_selection"
            else:
                self._chosen = chosen
                self._pending.update(credential_provider_flags(chosen))
                if chosen:
                    return await self.async_step_credentials()
                # Skip an empty credential page when no provider needs one.
                return self._finish_entry()

        return self.async_show_form(
            step_id="providers",
            data_schema=_providers_schema(self._pending),
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Only selected secrets; blank means retain existing credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            changes, missing = prepared_credentials(
                self._pending, user_input, self._chosen,
            )
            if not missing:
                self._pending.update(changes)
                return self._finish_entry()
            errors.update({key: "missing_credentials" for key in missing})

        return self.async_show_form(
            step_id="credentials",
            data_schema=_credentials_schema(self._chosen, self._pending),
            description_placeholders={
                "selected_providers": ", ".join(
                    PROVIDER_NAMES[provider] for provider in self._chosen
                ),
            },
            errors=errors,
        )

    def _finish_entry(self) -> ConfigFlowResult:
        raise NotImplementedError


class OsmParkingConfigFlow(_WizardSteps, config_entries.ConfigFlow, domain=DOMAIN):
    """Create a parking destination using the new guided setup."""

    VERSION = 2
    MINOR_VERSION = 5

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: destination and maximum search distance."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = str(user_input.get(CONF_DESTINATION_ENTITY) or "").strip()
            distance = user_input.get(CONF_RADIUS_M, DEFAULT_RADIUS_M)
            if _state_coordinates(self.hass.states.get(entity_id)) is None:
                errors[CONF_DESTINATION_ENTITY] = "invalid_destination_entity"
            elif not valid_positive_integer(distance, 100, 10000):
                errors[CONF_RADIUS_M] = "invalid_radius"
            else:
                await self.async_set_unique_id(entity_id)
                self._abort_if_unique_id_configured()
                self._pending = {
                    CONF_DESTINATION_ENTITY: entity_id,
                    CONF_RADIUS_M: int(distance),
                }
                self._chosen = []
                return await self.async_step_categories()

        return self.async_show_form(
            step_id="user",
            data_schema=_distance_schema(self.hass, user_input or {}),
            errors=errors,
        )

    def _finish_entry(self) -> ConfigFlowResult:
        """Write config entry exactly once at completion."""
        return self.async_create_entry(
            title=self._pending[CONF_DESTINATION_ENTITY],
            data=self._pending,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowWithReload:
        return OsmParkingOptionsFlow()


class OsmParkingOptionsFlow(_WizardSteps, OptionsFlowWithReload):
    """Edit an existing config entry without losing its stored settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 (options): destination and distance."""
        if not hasattr(self, "_pending"):
            self._pending = {
                **self.config_entry.data,
                **self.config_entry.options,
            }
            self._chosen = []
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = str(user_input.get(CONF_DESTINATION_ENTITY) or "").strip()
            prior_entity = str(
                self._pending.get(CONF_DESTINATION_ENTITY) or ""
            ).strip()
            distance = user_input.get(CONF_RADIUS_M, DEFAULT_RADIUS_M)
            if not entity_id or (
                entity_id != prior_entity
                and _state_coordinates(self.hass.states.get(entity_id)) is None
            ):
                errors[CONF_DESTINATION_ENTITY] = "invalid_destination_entity"
            elif not valid_positive_integer(distance, 100, 10000):
                errors[CONF_RADIUS_M] = "invalid_radius"
            else:
                self._pending[CONF_DESTINATION_ENTITY] = entity_id
                self._pending[CONF_RADIUS_M] = int(distance)
                return await self.async_step_categories()

        return self.async_show_form(
            step_id="init",
            data_schema=_distance_schema(self.hass, self._pending),
            errors=errors,
        )

    def _finish_entry(self) -> ConfigFlowResult:
        """OptionsFlowWithReload applies the result after the final step."""
        return self.async_create_entry(data=self._pending)
