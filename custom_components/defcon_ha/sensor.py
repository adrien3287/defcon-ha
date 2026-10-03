"""Sensor platform for DEFCON Home."""

from __future__ import annotations

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_RSS_ANALYZED
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
            LagezentrumNewsContextSensor(entry),
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



class LagezentrumNewsContextSensor(RestoreSensor, SensorEntity):
    """Keep the latest relevant RSS article classified by the user's AI automation."""

    _attr_has_entity_name = False
    _attr_name = "Lagezentrum News Context"
    _attr_icon = "mdi:newspaper-variant-multiple"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lagezentrum_news_context"
        self._attr_native_value = "idle"
        self._attrs: dict = {
            "importance": 0,
            "category": "other",
            "scope": "",
            "protective_action": False,
            "summary_fr": "",
            "reason": "",
            "recommended_action": "aucune",
            "title": "",
            "link": "",
            "feed_url": "",
            "analyzed_at": "",
        }
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Local deterministic situation engine",
        }

    async def async_added_to_hass(self) -> None:
        """Restore the previous context and subscribe to analyzed RSS events."""
        await super().async_added_to_hass()

        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is not None and last_sensor_data.native_value is not None:
            self._attr_native_value = last_sensor_data.native_value

        last_state = await self.async_get_last_state()
        if last_state is not None:
            for key in self._attrs:
                if key in last_state.attributes:
                    self._attrs[key] = last_state.attributes[key]

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_RSS_ANALYZED, self._handle_rss_event)
        )

    @callback
    def _handle_rss_event(self, event: Event) -> None:
        """Store only RSS items classified as relevant."""
        data = event.data

        relevant_raw = data.get("relevant", False)
        relevant = (
            relevant_raw
            if isinstance(relevant_raw, bool)
            else str(relevant_raw).strip().lower() in {"true", "1", "yes", "on"}
        )
        try:
            importance = int(float(data.get("importance", 0)))
        except (TypeError, ValueError):
            importance = 0

        if not relevant or importance < 1:
            return

        if importance >= 3:
            state = "important"
        elif importance == 2:
            state = "watch"
        else:
            state = "information"

        protective_raw = data.get("protective_action", False)
        protective_action = (
            protective_raw
            if isinstance(protective_raw, bool)
            else str(protective_raw).strip().lower() in {"true", "1", "yes", "on"}
        )

        self._attr_native_value = state
        self._attrs = {
            "importance": importance,
            "category": str(data.get("category", "other")),
            "scope": str(data.get("scope", "")),
            "protective_action": protective_action,
            "summary_fr": str(data.get("summary_fr", "")),
            "reason": str(data.get("reason", "")),
            "recommended_action": str(data.get("recommended_action", "aucune")),
            "title": str(data.get("title", "")),
            "link": str(data.get("link", "")),
            "feed_url": str(data.get("feed_url", "")),
            "analyzed_at": event.time_fired.isoformat(),
        }
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Return the latest relevant contextual article."""
        return self._attrs
