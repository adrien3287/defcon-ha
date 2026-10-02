"""Button platform for DEFCON Home."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up DEFCON Home buttons."""
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DefconRefreshButton(coordinator, entry)])


class DefconRefreshButton(CoordinatorEntity[DefconCoordinator], ButtonEntity):
    """Force a deterministic local reevaluation."""

    _attr_has_entity_name = True
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
