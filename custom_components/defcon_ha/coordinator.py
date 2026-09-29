"""State aggregation and DEFCON evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
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
    CONTEXT_POLL_MINUTES,
    DEFAULT_OVERRIDE,
    DOMAIN,
    EVENT_LEVEL_CHANGED,
    LEVEL_COLORS,
    LEVEL_NAMES,
)
from .context_feed import ContextFeed, async_fetch_context_feed

_LOGGER = logging.getLogger(__name__)

_HVV_PROBLEM = (
    "störung", "stoerung", "ausfall", "entfällt", "entfaellt", "gesperrt",
    "sperrung", "unterbrochen", "ersatzverkehr", "verspät", "disruption",
    "cancelled", "canceled", "suspended", "closed", "delay",
)
_HVV_SEVERE = (
    "kein verkehr", "verkehr eingestellt", "komplett gesperrt", "vollsperrung",
    "service suspended", "no service",
)
_GENERIC_PROBLEM = (
    "alert", "alarm", "warning", "unsafe", "problem", "fault", "critical",
    "störung", "stoerung", "warnung",
)


@dataclass(slots=True)
class DefconReason:
    """One active local reason contributing to the current level."""

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
    local_level: int
    context_level: int | None
    context_status: str
    context_summary: str
    context_reasons: list[dict[str, Any]]
    weak_signals: list[dict[str, Any]]
    context_generated_at: datetime | None
    context_valid_until: datetime | None
    context_error: str
    context_report: str
    context_report: str
    level_name: str
    color: str
    summary: str
    local_reasons: list[DefconReason]
    evaluated_at: datetime
    manual_override: str

    @property
    def context_in_use(self) -> bool:
        return self.context_status == "fresh" and self.context_level is not None

    def combined_reasons(self) -> list[dict[str, Any]]:
        reasons = [asdict(reason) for reason in self.local_reasons]
        for reason in self.context_reasons:
            title = str(reason.get("title", "Context signal"))
            scope = str(reason.get("scope", ""))
            category = str(reason.get("category", ""))
            detail = " · ".join(part for part in (scope, category) if part)
            source_name = str(reason.get("source_name", "Context"))
            try:
                level = int(reason.get("level", self.context_level or 5))
            except (TypeError, ValueError):
                level = self.context_level or 5
            reasons.append(
                {
                    "source": f"Context · {source_name}",
                    "entity_id": "",
                    "title": title,
                    "detail": detail,
                    "level": level,
                    "severity": str(reason.get("status", "context")),
                    "scope": scope,
                    "category": category,
                    "source_url": str(reason.get("source_url", "")),
                }
            )
        reasons.sort(key=lambda item: (int(item.get("level", 5)), str(item.get("source", ""))))
        return reasons

    def as_attributes(self) -> dict[str, Any]:
        combined = self.combined_reasons()
        return {
            "automatic_level": self.automatic_level,
            "local_level": self.local_level,
            "context_level": self.context_level,
            "context_status": self.context_status,
            "context_in_use": self.context_in_use,
            "context_summary": self.context_summary,
            "context_reasons": self.context_reasons,
            "weak_signals": self.weak_signals,
            "context_generated_at": self.context_generated_at.isoformat() if self.context_generated_at else None,
            "context_valid_until": self.context_valid_until.isoformat() if self.context_valid_until else None,
            "context_error": self.context_error,
            "context_report": self.context_report,
            "context_report": self.context_report,
            "level_name": self.level_name,
            "color": self.color,
            "summary": self.summary,
            "manual_override": self.manual_override,
            "reasons": combined,
            "local_reasons": [asdict(reason) for reason in self.local_reasons],
            "active_reason_count": len(combined),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class DefconCoordinator(DataUpdateCoordinator[DefconSnapshot]):
    """Aggregate local HA signals and the private contextual feed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=CONTEXT_POLL_MINUTES),
        )
        self.entry = entry
        self._remove_listener = None
        self._last_level: int | None = None

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def source_entities(self) -> list[str]:
        entity_ids: list[str] = []
        settings = self.settings
        for key in (
            CONF_NINA_ENTITIES,
            CONF_DWD_ENTITIES,
            CONF_HVV_ENTITIES,
            CONF_OTHER_ENTITIES,
        ):
            entity_ids.extend(settings.get(key, []))
        return list(dict.fromkeys(entity_ids))

    @callback
    def async_start(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        if self.source_entities:
            self._remove_listener = async_track_state_change_event(
                self.hass, self.source_entities, self._async_source_changed
            )

    @callback
    def async_stop(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _async_source_changed(self, _event: Any) -> None:
        self.entry.async_create_task(
            self.hass, self.async_request_refresh(), "DEFCON Home source refresh"
        )

    async def async_set_override(self, option: str) -> None:
        options = dict(self.entry.options)
        options[CONF_MANUAL_OVERRIDE] = option
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self.async_request_refresh()

    async def _async_update_data(self) -> DefconSnapshot:
        settings = self.settings
        local_reasons: list[DefconReason] = []

        for entity_id in settings.get(CONF_NINA_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = await self._async_analyse_nina(state)
                if reason:
                    local_reasons.append(reason)

        for entity_id in settings.get(CONF_DWD_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                local_reasons.extend(self._analyse_dwd(state))

        for entity_id in settings.get(CONF_HVV_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = self._analyse_hvv(state)
                if reason:
                    local_reasons.append(reason)

        for entity_id in settings.get(CONF_OTHER_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state:
                reason = self._analyse_generic(state)
                if reason:
                    local_reasons.append(reason)

        local_reasons.sort(key=lambda reason: (reason.level, reason.source, reason.title))
        local_level = min((reason.level for reason in local_reasons), default=5)

        context: ContextFeed = await async_fetch_context_feed(self.hass, settings)
        context_effective_level = context.level if context.is_fresh and context.level is not None else 5
        automatic_level = min(local_level, context_effective_level)

        override = settings.get(CONF_MANUAL_OVERRIDE, DEFAULT_OVERRIDE)
        level = automatic_level
        if isinstance(override, str) and override.startswith("defcon_"):
            try:
                level = int(override.rsplit("_", 1)[1])
            except ValueError:
                level = automatic_level

        summary = self._build_summary(
            local_reasons, local_level, context, automatic_level, level, override
        )
        snapshot = DefconSnapshot(
            level=level,
            automatic_level=automatic_level,
            local_level=local_level,
            context_level=context.level,
            context_status=context.status,
            context_summary=context.summary,
            context_reasons=context.reasons,
            weak_signals=context.weak_signals,
            context_generated_at=context.generated_at,
            context_valid_until=context.valid_until,
            context_error=context.error,
            context_report=context.report_markdown,
            context_report=context.report_markdown,
            level_name=LEVEL_NAMES[level],
            color=LEVEL_COLORS[level],
            summary=summary,
            local_reasons=local_reasons,
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
                    "local_level": local_level,
                    "context_level": context.level,
                    "context_status": context.status,
                    "summary": summary,
                    "reasons": snapshot.combined_reasons(),
                },
            )
        self._last_level = level
        return snapshot

    async def _async_analyse_nina(self, state: State) -> DefconReason | None:
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
        if warning_level <= 0:
            return None

        entity_lower = state.entity_id.lower()
        friendly = str(state.attributes.get("friendly_name", "")).lower()
        is_advance = any(
            token in entity_lower or token in friendly
            for token in ("advance", "vorab", "antici")
        )
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
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "off", "0", "none", "None"):
            return None

        text = self._state_text(state).lower()
        severe = any(keyword in text for keyword in _HVV_SEVERE)
        problem = severe or any(keyword in text for keyword in _HVV_PROBLEM)
        if not problem:
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
        local_reasons: list[DefconReason],
        local_level: int,
        context: ContextFeed,
        automatic_level: int,
        level: int,
        override: str,
    ) -> str:
        local_summary = "No active local warning"
        if local_reasons:
            local_summary = "; ".join(
                reason.title for reason in local_reasons if reason.level == local_level
            )[:700]

        if context.is_fresh:
            base = (
                f"Local DEFCON {local_level}: {local_summary}. "
                f"Context DEFCON {context.level}: {context.summary}"
            )
        elif context.status == "disabled":
            base = f"Local DEFCON {local_level}: {local_summary}. Context feed disabled."
        else:
            base = (
                f"Local DEFCON {local_level}: {local_summary}. "
                f"Context feed {context.status}; ignored for automatic level."
            )

        if override != DEFAULT_OVERRIDE and level != automatic_level:
            return (
                f"Manual override to DEFCON {level}. Automatic: DEFCON {automatic_level}. "
                f"{base}"
            )
        return base
