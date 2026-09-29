"""State aggregation and DEFCON evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DWD_ENTITIES,
    CONF_HVV_ENTITIES,
    CONF_MANUAL_OVERRIDE,
    CONF_NINA_ENTITIES,
    CONF_OTHER_ENTITIES,
    DEFAULT_OVERRIDE,
    DOMAIN,
    EVENT_LEVEL_CHANGED,
    LEVEL_COLORS,
    LEVEL_NAMES,
)

_LOGGER = logging.getLogger(__name__)

_HVV_PROBLEM = (
    "störung",
    "stoerung",
    "ausfall",
    "entfällt",
    "entfaellt",
    "gesperrt",
    "sperrung",
    "unterbrochen",
    "ersatzverkehr",
    "verspät",
    "disruption",
    "cancelled",
    "canceled",
    "suspended",
    "closed",
    "delay",
)
_HVV_SEVERE = (
    "kein verkehr",
    "verkehr eingestellt",
    "komplett gesperrt",
    "vollsperrung",
    "service suspended",
    "no service",
)
_GENERIC_PROBLEM = (
    "alert",
    "alarm",
    "warning",
    "unsafe",
    "problem",
    "fault",
    "critical",
    "störung",
    "stoerung",
    "warnung",
)


@dataclass(slots=True)
class DefconReason:
    """One active reason contributing to the current level."""

    source: str
    entity_id: str
    title: str
    detail: str
    level: int
    severity: str = ""


@dataclass(slots=True)
class DefconSnapshot:
    """Evaluated DEFCON state."""

    level: int
    automatic_level: int
    level_name: str
    color: str
    summary: str
    reasons: list[DefconReason]
    evaluated_at: datetime
    manual_override: str

    def as_attributes(self) -> dict[str, Any]:
        """Return entity-safe attributes."""
        return {
            "automatic_level": self.automatic_level,
            "level_name": self.level_name,
            "color": self.color,
            "summary": self.summary,
            "manual_override": self.manual_override,
            "reasons": [asdict(reason) for reason in self.reasons],
            "active_reason_count": len(self.reasons),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class DefconCoordinator(DataUpdateCoordinator[DefconSnapshot]):
    """Aggregate existing Home Assistant entities into one household DEFCON level."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry
        self._remove_listener = None
        self._last_level: int | None = None

    @property
    def source_entities(self) -> list[str]:
        """Return all configured source entities."""
        entity_ids: list[str] = []
        for key in (
            CONF_NINA_ENTITIES,
            CONF_DWD_ENTITIES,
            CONF_HVV_ENTITIES,
            CONF_OTHER_ENTITIES,
        ):
            entity_ids.extend(self.entry.data.get(key, []))
        return list(dict.fromkeys(entity_ids))

    @callback
    def async_start(self) -> None:
        """Listen for changes on all configured source entities."""
        if self._remove_listener or not self.source_entities:
            return
        self._remove_listener = async_track_state_change_event(
            self.hass, self.source_entities, self._async_source_changed
        )

    @callback
    def async_stop(self) -> None:
        """Stop listening for source changes."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _async_source_changed(self, _event: Any) -> None:
        """Refresh when a monitored entity changes state or attributes."""
        self.entry.async_create_task(
            self.hass, self.async_request_refresh(), "DEFCON Home source refresh"
        )

    async def async_set_override(self, option: str) -> None:
        """Persist and apply the manual override."""
        options = dict(self.entry.options)
        options[CONF_MANUAL_OVERRIDE] = option
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self.async_request_refresh()

    async def _async_update_data(self) -> DefconSnapshot:
        """Evaluate all source entities."""
        reasons: list[DefconReason] = []

        for entity_id in self.entry.data.get(CONF_NINA_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = await self._async_analyse_nina(state)
                if reason:
                    reasons.append(reason)

        for entity_id in self.entry.data.get(CONF_DWD_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reasons.extend(self._analyse_dwd(state))

        for entity_id in self.entry.data.get(CONF_HVV_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = self._analyse_hvv(state)
                if reason:
                    reasons.append(reason)

        for entity_id in self.entry.data.get(CONF_OTHER_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = self._analyse_generic(state)
                if reason:
                    reasons.append(reason)

        reasons.sort(key=lambda reason: (reason.level, reason.source, reason.title))
        automatic_level = min((reason.level for reason in reasons), default=5)

        override = self.entry.options.get(CONF_MANUAL_OVERRIDE, DEFAULT_OVERRIDE)
        level = automatic_level
        if isinstance(override, str) and override.startswith("defcon_"):
            try:
                level = int(override.rsplit("_", 1)[1])
            except ValueError:
                level = automatic_level

        summary = self._build_summary(reasons, automatic_level, level, override)
        snapshot = DefconSnapshot(
            level=level,
            automatic_level=automatic_level,
            level_name=LEVEL_NAMES[level],
            color=LEVEL_COLORS[level],
            summary=summary,
            reasons=reasons,
            evaluated_at=dt_util.utcnow(),
            manual_override=override,
        )

        if self._last_level is not None and self._last_level != level:
            self.hass.bus.async_fire(
                EVENT_LEVEL_CHANGED,
                {
                    "old_level": self._last_level,
                    "new_level": level,
                    "automatic_level": automatic_level,
                    "summary": summary,
                    "reasons": [asdict(reason) for reason in reasons],
                },
            )
        self._last_level = level
        return snapshot

    async def _async_analyse_nina(self, state: State) -> DefconReason | None:
        """Analyse an official NINA warning entity."""
        if state.state in ("off", "0", STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None

        details: dict[str, Any] = {}
        if self.hass.services.has_service("nina", "get_details"):
            try:
                response = await self.hass.services.async_call(
                    "nina",
                    "get_details",
                    {},
                    blocking=True,
                    target={"entity_id": state.entity_id},
                    return_response=True,
                )
                if isinstance(response, dict):
                    candidate = response.get(state.entity_id)
                    if isinstance(candidate, dict):
                        details = candidate
            except (HomeAssistantError, ServiceNotFound, ValueError) as err:
                _LOGGER.debug("Unable to retrieve NINA details for %s: %s", state.entity_id, err)

        attrs = {**state.attributes, **details}
        headline = self._first_text(attrs, "headline", "title", "event")
        detail = self._first_text(attrs, "description", "instruction", "sender")
        severity = str(attrs.get("severity", "")).strip()
        urgency = str(attrs.get("urgency", "")).strip()
        status = str(attrs.get("msgType", attrs.get("message_type", ""))).lower()

        if "cancel" in status or "entwarn" in headline.lower():
            return None

        # Household policy: every active official civil-protection warning selected
        # by the user raises at least DEFCON 3. Extreme/immediate warnings raise 2.
        level = 3
        if severity.lower() == "extreme" or (
            severity.lower() == "severe" and urgency.lower() == "immediate"
        ):
            level = 2
        elif severity.lower() == "minor":
            level = 4

        return DefconReason(
            source="NINA",
            entity_id=state.entity_id,
            title=headline or state.name or "Official warning",
            detail=self._clean_text(detail),
            level=level,
            severity=severity,
        )

    def _analyse_dwd(self, state: State) -> list[DefconReason]:
        """Analyse DWD current/advance warning level sensors."""
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return []

        try:
            sensor_level = int(float(state.state))
        except (TypeError, ValueError):
            sensor_level = 0

        warning_indexes: set[int] = set()
        for key in state.attributes:
            match = re.fullmatch(r"warning_(\d+)_level", key)
            if match:
                warning_indexes.add(int(match.group(1)))

        reasons: list[DefconReason] = []
        if warning_indexes:
            for index in sorted(warning_indexes):
                try:
                    raw_level = int(state.attributes.get(f"warning_{index}_level", 0))
                except (TypeError, ValueError):
                    continue
                reason = self._dwd_reason(state, raw_level, index)
                if reason:
                    reasons.append(reason)
        elif sensor_level > 0:
            reason = self._dwd_reason(state, sensor_level, None)
            if reason:
                reasons.append(reason)

        return reasons

    def _dwd_reason(
        self, state: State, warning_level: int, index: int | None
    ) -> DefconReason | None:
        """Build one DWD warning reason."""
        if warning_level <= 0:
            return None

        is_advance = "advance" in state.entity_id.lower() or "vorab" in state.entity_id.lower()
        if warning_level >= 4:
            level = 3 if is_advance else 2
        elif warning_level >= 3:
            level = 4 if is_advance else 3
        else:
            level = 4

        prefix = f"warning_{index}_" if index is not None else ""
        title = self._first_text(
            state.attributes,
            f"{prefix}headline",
            f"{prefix}name",
            "friendly_name",
        )
        detail = self._first_text(
            state.attributes,
            f"{prefix}description",
            f"{prefix}instruction",
        )

        return DefconReason(
            source="DWD",
            entity_id=state.entity_id,
            title=title or state.name or "Weather warning",
            detail=self._clean_text(detail),
            level=level,
            severity=str(warning_level),
        )

    def _analyse_hvv(self, state: State) -> DefconReason | None:
        """Analyse selected HVV status entities conservatively."""
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "off", "0", "none", "None"):
            return None

        text = self._state_text(state).lower()
        severe = any(keyword in text for keyword in _HVV_SEVERE)
        problem = severe or any(keyword in text for keyword in _HVV_PROBLEM)

        if not problem:
            # Some HVV entities expose delay as a plain minute value.
            match = re.search(r"(-?\d+)\s*(?:min|minute)", text)
            if match and int(match.group(1)) >= 15:
                problem = True

        if not problem:
            return None

        return DefconReason(
            source="HVV",
            entity_id=state.entity_id,
            title=state.name or "HVV disruption",
            detail=self._clean_text(self._state_text(state), 400),
            level=4,
            severity="major" if severe else "disruption",
        )

    def _analyse_generic(self, state: State) -> DefconReason | None:
        """Analyse an optional generic problem/alarm entity."""
        if state.state in ("off", "0", "ok", "normal", STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None

        text = self._state_text(state).lower()
        active_boolean = state.state.lower() in ("on", "true", "unsafe", "problem")
        if not active_boolean and not any(keyword in text for keyword in _GENERIC_PROBLEM):
            return None

        return DefconReason(
            source="Other",
            entity_id=state.entity_id,
            title=state.name or state.entity_id,
            detail=self._clean_text(self._state_text(state), 400),
            level=4,
            severity="generic",
        )

    @staticmethod
    def _first_text(attrs: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = attrs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _clean_text(value: str, limit: int = 700) -> str:
        text = re.sub(r"<[^>]+>", " ", value or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit]

    def _state_text(self, state: State) -> str:
        parts = [state.state, state.name or ""]
        for value in state.attributes.values():
            if isinstance(value, (str, int, float)):
                parts.append(str(value))
        return " | ".join(parts)

    @staticmethod
    def _build_summary(
        reasons: list[DefconReason], automatic_level: int, level: int, override: str
    ) -> str:
        if not reasons:
            base = "No active warning or monitored disruption"
        else:
            most_severe = [reason for reason in reasons if reason.level == automatic_level][:3]
            base = "; ".join(reason.title for reason in most_severe)

        if override != DEFAULT_OVERRIDE and level != automatic_level:
            return f"Manual override to DEFCON {level}. Automatic: DEFCON {automatic_level}. {base}"
        return base
