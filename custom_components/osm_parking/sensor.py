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
    def native_value(self) -> str:
        """Return coordinator status as the sensor value."""
        return str((self.coordinator.data or {}).get("status", "unknown"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose destination and parking suggestions."""
        attrs = dict(self.coordinator.data or {})
        attrs.setdefault(
            "destination_entity",
            self._entry.options.get(
                "destination_entity",
                self._entry.data.get("destination_entity"),
            ),
        )
        return attrs
