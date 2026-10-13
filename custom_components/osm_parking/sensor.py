from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OsmParkingConfigEntry
from .const import DOMAIN
from .coordinator import OsmParkingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OsmParkingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OSM Parking sensor entities."""
    async_add_entities([OsmParkingSensor(entry.runtime_data.coordinator, entry)])


class OsmParkingSensor(CoordinatorEntity[OsmParkingCoordinator], SensorEntity):
    """Sensor exposing parking suggestions and metadata."""

    _attr_icon = "mdi:parking"
    _attr_has_entity_name = True
    _attr_name = "Parking suggestions"

    def __init__(
        self, coordinator: OsmParkingCoordinator, entry: OsmParkingConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_suggestions"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OSM Parking",
            manufacturer="OpenStreetMap",
            model="Overpass parking search",
        )

    @property
    def available(self) -> bool:
        """Keep the status sensor available so failure details remain visible."""
        return True

    @property
    def native_value(self) -> str:
        """Return coordinator status as the sensor value."""
        if not self.coordinator.last_update_success:
            return "error"
        return str((self.coordinator.data or {}).get("status", "unknown"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose destination, parking suggestions, and recovery information."""
        attrs = dict(self.coordinator.data or {})
        attrs.setdefault(
            "destination_entity",
            self._entry.options.get(
                "destination_entity",
                self._entry.data.get("destination_entity"),
            ),
        )

        if self.coordinator.last_update_success:
            attrs.setdefault("auto_retry", False)
            return attrs

        # DataUpdateCoordinator intentionally preserves the previous successful
        # payload after a failed refresh. Do not expose those old suggestions as
        # current parking data; instead publish a structured failure state that
        # the bundled card can explain and recover from.
        error = str(self.coordinator.last_exception or "Unknown update error")
        attrs["status"] = "error"
        attrs["suggestions"] = []
        attrs["raw_result_count"] = 0
        attrs["error"] = error
        attrs["error_code"] = self._error_code(error)
        attrs["auto_retry"] = True
        attrs["retry_after_seconds"] = self.coordinator.retry_interval_seconds
        return attrs

    @staticmethod
    def _error_code(error: str) -> str:
        """Classify coordinator failures for user-facing recovery guidance."""
        lowered = error.lower()
        if "all overpass endpoints failed" in lowered:
            return "overpass_unavailable"
        if "overpass rejected the query" in lowered:
            return "overpass_rejected"
        if "no destination entity configured" in lowered:
            return "destination_not_configured"
        return "update_failed"
