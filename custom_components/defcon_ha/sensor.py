"""Sensor platform for DEFCON Home."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DefconCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DEFCON Home sensor."""
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DefconLevelSensor(coordinator, entry)])


class DefconLevelSensor(CoordinatorEntity[DefconCoordinator], SensorEntity):
    """Current household DEFCON level."""

    _attr_has_entity_name = True
    _attr_name = "Level"
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_level"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }

    @property
    def native_value(self) -> int:
        """Return current DEFCON level."""
        return self.coordinator.data.level

    @property
    def extra_state_attributes(self) -> dict:
        """Return current explanation and source details."""
        attrs = self.coordinator.data.as_attributes()
        attrs["source_entities"] = self.coordinator.source_entities
        return attrs
