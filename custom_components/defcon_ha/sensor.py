"""Sensor platform for DEFCON Home."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .context import ContextCoordinator
from .coordinator import DefconCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    context: ContextCoordinator = hass.data[DOMAIN][f"{entry.entry_id}_context"]
    async_add_entities(
        [
            DefconLevelSensor(coordinator, entry),
            DefconLocalSensor(coordinator, entry),
            DefconExternalSensor(coordinator, entry),
            DefconInfrastructureSensor(coordinator, entry),
            DefconSourceHealthSensor(coordinator, entry),
            ContextStatusSensor(context, entry),
            ContextActiveEventsSensor(context, entry),
            ContextRecommendedDefconSensor(context, entry),
            LagezentrumNewsContextSensor(context, entry),
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



class _ContextBaseSensor(CoordinatorEntity[ContextCoordinator], SensorEntity):
    """Base class for the informational context layer."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ContextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Local deterministic situation engine",
        }


class ContextStatusSensor(_ContextBaseSensor):
    """Overall state of active contextual events."""

    _attr_name = "Context status"
    _attr_icon = "mdi:radar"

    def __init__(self, coordinator: ContextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_context_status"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return {
            "active_event_count": data.active_event_count,
            "stale_event_count": data.stale_event_count,
            "highest_importance": data.highest_importance,
            "highest_confidence": data.highest_confidence,
            "evaluated_at": data.evaluated_at.isoformat(),
            "affects_defcon": False,
        }


class ContextActiveEventsSensor(_ContextBaseSensor):
    """Number of currently active contextual events."""

    _attr_name = "Context active events"
    _attr_icon = "mdi:alert-decagram-outline"

    def __init__(self, coordinator: ContextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_context_active_events"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.active_event_count

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "stale_event_count": self.coordinator.data.stale_event_count,
        }


class ContextRecommendedDefconSensor(_ContextBaseSensor):
    """Indicative DEFCON recommendation from the context layer only."""

    _attr_name = "Context recommended DEFCON"
    _attr_icon = "mdi:shield-search"

    def __init__(self, coordinator: ContextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_context_recommended_defcon"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.recommended_defcon

    @property
    def extra_state_attributes(self) -> dict:
        top = self.coordinator.data.top_event or {}
        return {
            "advisory_only": True,
            "affects_defcon": False,
            "top_event_key": top.get("event_key", ""),
            "top_event_title": top.get("title", ""),
            "highest_importance": self.coordinator.data.highest_importance,
            "highest_confidence": self.coordinator.data.highest_confidence,
        }


class LagezentrumNewsContextSensor(_ContextBaseSensor):
    """Compatibility/detail sensor exposing the context event queue."""

    _attr_has_entity_name = False
    _attr_name = "Lagezentrum News Context"
    _attr_icon = "mdi:newspaper-variant-multiple"
    _unrecorded_attributes = frozenset(
        {"active_events", "stale_events", "recent_events"}
    )

    def __init__(self, coordinator: ContextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        # Keep the 0.3.x unique ID so existing installations retain the entity.
        self._attr_unique_id = f"{entry.entry_id}_lagezentrum_news_context"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        top = data.top_event or {}

        attrs = {
            "importance": top.get("importance", 0),
            "category": top.get("category", "other"),
            "scope": top.get("scope", ""),
            "affected_area": top.get("affected_area", ""),
            "direct_relevance": top.get("direct_relevance", ""),
            "protective_action": top.get("protective_action", False),
            "summary_fr": top.get("summary_fr", ""),
            "reason": top.get("reason", ""),
            "recommended_action": top.get("recommended_action", "aucune"),
            "title": top.get("title", ""),
            "link": top.get("link", ""),
            "feed_url": top.get("feed_url", ""),
            "source_name": top.get("source_name", ""),
            "source_tier": top.get("source_tier", ""),
            "source_class": top.get("source_class", ""),
            "event_key": top.get("event_key", ""),
            "event_status": top.get("status", ""),
            "confidence_score": top.get("confidence_score", 0),
            "corroboration_count": top.get("corroboration_count", 0),
            "event_start_at": top.get("event_start_at", ""),
            "valid_until": top.get("valid_until", ""),
            "validity_source": top.get("validity_source", "category_ttl"),
            "expires_at": top.get("expires_at", ""),
            "last_seen": top.get("last_seen", ""),
            "active_event_count": data.active_event_count,
            "stale_event_count": data.stale_event_count,
            "context_recommended_defcon": data.recommended_defcon,
            "affects_defcon": False,
            "active_events": data.active_events,
            "stale_events": data.stale_events,
            "recent_events": data.recent_events,
            "evaluated_at": data.evaluated_at.isoformat(),
        }
        return attrs
