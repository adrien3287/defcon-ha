"""Manual override select for DEFCON Home."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DefconCoordinator

OPTIONS = ["auto", "defcon_5", "defcon_4", "defcon_3", "defcon_2", "defcon_1"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DEFCON Home override select."""
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DefconOverrideSelect(coordinator, entry)])


class DefconOverrideSelect(CoordinatorEntity[DefconCoordinator], SelectEntity):
    """Persistent manual override for the calculated DEFCON level."""

    _attr_has_entity_name = True
    _attr_name = "Manual override"
    _attr_icon = "mdi:shield-edit"
    _attr_options = OPTIONS

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_manual_override"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }

    @property
    def current_option(self) -> str:
        """Return selected override."""
        return self.coordinator.data.manual_override

    async def async_select_option(self, option: str) -> None:
        """Set override."""
        if option not in OPTIONS:
            raise ValueError(f"Unsupported DEFCON override: {option}")
        await self.coordinator.async_set_override(option)
