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
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DefconLevelSensor(coordinator, entry),
            DefconLocalSensor(coordinator, entry),
            DefconExternalSensor(coordinator, entry),
            DefconInfrastructureSensor(coordinator, entry),
            DefconSourceHealthSensor(coordinator, entry),
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
            "model": "Local deterministic situation engine",
        }


class DefconLevelSensor(_DefconBaseSensor):
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
    """Compatibility sensor: all deterministic HA sources before manual override."""

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
            "external_level": self.coordinator.data.external_level,
            "infrastructure_level": self.coordinator.data.infrastructure_level,
            "reasons": [
                reason.__dict__ if hasattr(reason, "__dict__") else {
                    "source": reason.source,
                    "category": reason.category,
                    "entity_id": reason.entity_id,
                    "title": reason.title,
                    "detail": reason.detail,
                    "level": reason.level,
                    "severity": reason.severity,
                }
                for reason in self.coordinator.data.reasons
            ],
        }


class DefconExternalSensor(_DefconBaseSensor):
    _attr_name = "External level"
    _attr_icon = "mdi:weather-hurricane"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_external_level"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.external_level

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "reasons": [
                {
                    "source": reason.source,
                    "category": reason.category,
                    "entity_id": reason.entity_id,
                    "title": reason.title,
                    "detail": reason.detail,
                    "level": reason.level,
                    "severity": reason.severity,
                }
                for reason in self.coordinator.data.external_reasons
            ]
        }


class DefconInfrastructureSensor(_DefconBaseSensor):
    _attr_name = "Infrastructure level"
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_infrastructure_level"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.infrastructure_level

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "reasons": [
                {
                    "source": reason.source,
                    "category": reason.category,
                    "entity_id": reason.entity_id,
                    "title": reason.title,
                    "detail": reason.detail,
                    "level": reason.level,
                    "severity": reason.severity,
                }
                for reason in self.coordinator.data.infrastructure_reasons
            ]
        }


class DefconSourceHealthSensor(_DefconBaseSensor):
    _attr_name = "Source health"
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_source_health"

    @property
    def native_value(self) -> str:
        return "ok" if not self.coordinator.data.degraded_sources else "degraded"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "degraded_source_count": len(self.coordinator.data.degraded_sources),
            "degraded_sources": self.coordinator.data.degraded_sources,
            "source_entities": self.coordinator.source_entities,
        }
