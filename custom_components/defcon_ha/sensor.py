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
    """Set up DEFCON Home sensors."""
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DefconLevelSensor(coordinator, entry),
            DefconLocalSensor(coordinator, entry),
            DefconContextSensor(coordinator, entry),
        ]
    )


class _DefconBaseSensor(CoordinatorEntity[DefconCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }


class DefconLevelSensor(_DefconBaseSensor):
    """Effective household DEFCON level."""

    _attr_name = "Level"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_level"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.level

    @property
    def extra_state_attributes(self) -> dict:
        attrs = self.coordinator.data.as_attributes()
        attrs["source_entities"] = self.coordinator.source_entities
        return attrs


class DefconLocalSensor(_DefconBaseSensor):
    """Immediate local DEFCON level from Home Assistant entities."""

    _attr_name = "Local level"
    _attr_icon = "mdi:home-alert"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_local_level"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.local_level

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "reasons": [
                {
                    "source": reason.source,
                    "entity_id": reason.entity_id,
                    "title": reason.title,
                    "detail": reason.detail,
                    "level": reason.level,
                    "severity": reason.severity,
                }
                for reason in self.coordinator.data.local_reasons
            ],
            "source_entities": self.coordinator.source_entities,
        }


class DefconContextSensor(_DefconBaseSensor):
    """Contextual DEFCON level from the private GitHub feed."""

    _attr_name = "Context level"
    _attr_icon = "mdi:newspaper-variant-multiple"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_context_level"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.context_level

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return {
            "status": data.context_status,
            "in_use": data.context_in_use,
            "summary": data.context_summary,
            "reasons": data.context_reasons,
            "weak_signals": data.weak_signals,
            "generated_at": data.context_generated_at.isoformat() if data.context_generated_at else None,
            "valid_until": data.context_valid_until.isoformat() if data.context_valid_until else None,
            "error": data.context_error,
        }
