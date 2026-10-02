"""Deterministic Home Assistant state aggregation and DEFCON evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import logging
import re
from typing import Any, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_SOC_ENTITIES,
    CONF_BFS_ASSESSMENT_ENTITIES,
    CONF_DWD_ADVANCE_ENTITIES,
    CONF_DWD_CURRENT_ENTITIES,
    CONF_DWD_ENTITIES,
    CONF_FIRE_HEAT_ENTITIES,
    CONF_FIRE_SMOKE_ENTITIES,
    CONF_FLOOD_ENTITIES,
    CONF_GRID_ALARM_ENTITIES,
    CONF_GRID_VOLTAGE_ENTITIES,
    CONF_LIGHTNING_COUNT_ENTITIES,
    CONF_LIGHTNING_DISTANCE_ENTITIES,
    CONF_MANUAL_OVERRIDE,
    CONF_NINA_ENTITIES,
    CONF_NOAA_ENTITIES,
    CONF_OTHER_ENTITIES,
    CONF_PEGEL_STAGE_ENTITIES,
    CONF_UBA_LQI_ENTITIES,
    CONF_WAN_TELEKOM_ENTITIES,
    CONF_WAN_VODAFONE_ENTITIES,
    DEFAULT_BATTERY_SOC_ENTITIES,
    DEFAULT_BFS_ASSESSMENT_ENTITIES,
    DEFAULT_DWD_ADVANCE_ENTITIES,
    DEFAULT_DWD_CURRENT_ENTITIES,
    DEFAULT_FIRE_HEAT_ENTITIES,
    DEFAULT_FIRE_SMOKE_ENTITIES,
    DEFAULT_FLOOD_ENTITIES,
    DEFAULT_GRID_ALARM_ENTITIES,
    DEFAULT_GRID_VOLTAGE_ENTITIES,
    DEFAULT_LIGHTNING_COUNT_ENTITIES,
    DEFAULT_LIGHTNING_DISTANCE_ENTITIES,
    DEFAULT_NINA_ENTITIES,
    DEFAULT_NOAA_ENTITIES,
    DEFAULT_OVERRIDE,
    DEFAULT_PEGEL_STAGE_ENTITIES,
    DEFAULT_UBA_LQI_ENTITIES,
    DEFAULT_WAN_TELEKOM_ENTITIES,
    DEFAULT_WAN_VODAFONE_ENTITIES,
    DOMAIN,
    EVENT_LEVEL_CHANGED,
    LEVEL_COLORS,
    LEVEL_NAMES,
    REFRESH_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

_UNAVAILABLE = {STATE_UNKNOWN, STATE_UNAVAILABLE, "none", "None", ""}
_GENERIC_PROBLEM = (
    "alert", "alarm", "warning", "unsafe", "problem", "fault", "critical",
    "störung", "stoerung", "warnung",
)


@dataclass(slots=True)
class DefconReason:
    """One active reason contributing to a deterministic DEFCON level."""

    source: str
    category: str
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
    external_level: int
    infrastructure_level: int
    level_name: str
    color: str
    summary: str
    reasons: list[DefconReason]
    external_reasons: list[DefconReason]
    infrastructure_reasons: list[DefconReason]
    degraded_sources: list[dict[str, str]]
    evaluated_at: datetime
    manual_override: str

    def as_attributes(self) -> dict[str, Any]:
        return {
            "automatic_level": self.automatic_level,
            "local_level": self.local_level,
            "external_level": self.external_level,
            "infrastructure_level": self.infrastructure_level,
            "level_name": self.level_name,
            "color": self.color,
            "summary": self.summary,
            "manual_override": self.manual_override,
            "reasons": [asdict(reason) for reason in self.reasons],
            "external_reasons": [asdict(reason) for reason in self.external_reasons],
            "infrastructure_reasons": [asdict(reason) for reason in self.infrastructure_reasons],
            "active_reason_count": len(self.reasons),
            "degraded_sources": self.degraded_sources,
            "degraded_source_count": len(self.degraded_sources),
            "evaluated_at": self.evaluated_at.isoformat(),
            "engine": "local_deterministic",
        }


class DefconCoordinator(DataUpdateCoordinator[DefconSnapshot]):
    """Aggregate configured HA entities. No external JSON or AI is used."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=REFRESH_MINUTES),
        )
        self.entry = entry
        self._remove_listener = None
        self._last_level: int | None = None

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def _configured(self, key: str, default: list[str]) -> list[str]:
        value = self.settings.get(key, default)
        return list(value) if isinstance(value, (list, tuple)) else list(default)

    def _dwd_current_entities(self) -> list[str]:
        if CONF_DWD_CURRENT_ENTITIES in self.settings:
            return self._configured(CONF_DWD_CURRENT_ENTITIES, DEFAULT_DWD_CURRENT_ENTITIES)
        legacy = self.settings.get(CONF_DWD_ENTITIES)
        if isinstance(legacy, (list, tuple)):
            current = [e for e in legacy if "antici" not in e.lower() and "advance" not in e.lower()]
            if current:
                return current
        return list(DEFAULT_DWD_CURRENT_ENTITIES)

    def _dwd_advance_entities(self) -> list[str]:
        if CONF_DWD_ADVANCE_ENTITIES in self.settings:
            return self._configured(CONF_DWD_ADVANCE_ENTITIES, DEFAULT_DWD_ADVANCE_ENTITIES)
        legacy = self.settings.get(CONF_DWD_ENTITIES)
        if isinstance(legacy, (list, tuple)):
            advance = [e for e in legacy if "antici" in e.lower() or "advance" in e.lower()]
            if advance:
                return advance
        return list(DEFAULT_DWD_ADVANCE_ENTITIES)

    @property
    def source_entities(self) -> list[str]:
        groups = [
            self._configured(CONF_NINA_ENTITIES, DEFAULT_NINA_ENTITIES),
            self._dwd_current_entities(),
            self._dwd_advance_entities(),
            self._configured(CONF_FLOOD_ENTITIES, DEFAULT_FLOOD_ENTITIES),
            self._configured(CONF_PEGEL_STAGE_ENTITIES, DEFAULT_PEGEL_STAGE_ENTITIES),
            self._configured(CONF_UBA_LQI_ENTITIES, DEFAULT_UBA_LQI_ENTITIES),
            self._configured(CONF_BFS_ASSESSMENT_ENTITIES, DEFAULT_BFS_ASSESSMENT_ENTITIES),
            self._configured(CONF_LIGHTNING_COUNT_ENTITIES, DEFAULT_LIGHTNING_COUNT_ENTITIES),
            self._configured(CONF_LIGHTNING_DISTANCE_ENTITIES, DEFAULT_LIGHTNING_DISTANCE_ENTITIES),
            self._configured(CONF_NOAA_ENTITIES, DEFAULT_NOAA_ENTITIES),
            self._configured(CONF_FIRE_HEAT_ENTITIES, DEFAULT_FIRE_HEAT_ENTITIES),
            self._configured(CONF_FIRE_SMOKE_ENTITIES, DEFAULT_FIRE_SMOKE_ENTITIES),
            self._configured(CONF_GRID_VOLTAGE_ENTITIES, DEFAULT_GRID_VOLTAGE_ENTITIES),
            self._configured(CONF_GRID_ALARM_ENTITIES, DEFAULT_GRID_ALARM_ENTITIES),
            self._configured(CONF_BATTERY_SOC_ENTITIES, DEFAULT_BATTERY_SOC_ENTITIES),
            self._configured(CONF_WAN_TELEKOM_ENTITIES, DEFAULT_WAN_TELEKOM_ENTITIES),
            self._configured(CONF_WAN_VODAFONE_ENTITIES, DEFAULT_WAN_VODAFONE_ENTITIES),
            self._configured(CONF_OTHER_ENTITIES, []),
        ]
        entity_ids: list[str] = []
        for group in groups:
            entity_ids.extend(group)
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

    def _states(
        self,
        entity_ids: Iterable[str],
        source: str,
        degraded: list[dict[str, str]],
    ) -> list[State]:
        states: list[State] = []
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state is None:
                degraded.append({"source": source, "entity_id": entity_id, "status": "missing"})
                continue
            if state.state in _UNAVAILABLE:
                degraded.append({"source": source, "entity_id": entity_id, "status": state.state})
                continue
            states.append(state)
        return states

    async def _async_update_data(self) -> DefconSnapshot:
        degraded: list[dict[str, str]] = []
        external: list[DefconReason] = []
        infrastructure: list[DefconReason] = []

        for state in self._states(
            self._configured(CONF_NINA_ENTITIES, DEFAULT_NINA_ENTITIES), "NINA", degraded
        ):
            reason = await self._async_analyse_nina(state)
            if reason:
                external.append(reason)

        for state in self._states(self._dwd_current_entities(), "DWD current", degraded):
            external.extend(self._analyse_dwd(state, advance=False))
        for state in self._states(self._dwd_advance_entities(), "DWD advance", degraded):
            external.extend(self._analyse_dwd(state, advance=True))

        for state in self._states(
            self._configured(CONF_FLOOD_ENTITIES, DEFAULT_FLOOD_ENTITIES),
            "Flood warning",
            degraded,
        ):
            reason = self._analyse_numeric_scale(state, "Hochwasser", "hydrology")
            if reason:
                external.append(reason)

        for state in self._states(
            self._configured(CONF_PEGEL_STAGE_ENTITIES, DEFAULT_PEGEL_STAGE_ENTITIES),
            "PEGELONLINE",
            degraded,
        ):
            reason = self._analyse_numeric_scale(state, "PEGELONLINE", "hydrology")
            if reason:
                external.append(reason)

        uba_states = self._states(
            self._configured(CONF_UBA_LQI_ENTITIES, DEFAULT_UBA_LQI_ENTITIES),
            "UBA LQI",
            degraded,
        )
        uba_reason = self._analyse_uba_group(uba_states)
        if uba_reason:
            external.append(uba_reason)

        for state in self._states(
            self._configured(CONF_BFS_ASSESSMENT_ENTITIES, DEFAULT_BFS_ASSESSMENT_ENTITIES),
            "BfS ODL",
            degraded,
        ):
            reason = self._analyse_bfs(state)
            if reason:
                external.append(reason)

        lightning = self._analyse_lightning(degraded)
        if lightning:
            external.append(lightning)

        external.extend(self._analyse_noaa(degraded))

        fire = self._analyse_fire(degraded)
        if fire:
            infrastructure.append(fire)

        grid = self._analyse_grid(degraded)
        if grid:
            infrastructure.append(grid)

        internet = self._analyse_internet(degraded)
        if internet:
            infrastructure.append(internet)

        if grid and grid.level <= 3 and internet and internet.level <= 3:
            infrastructure.append(
                DefconReason(
                    source="Infrastructure",
                    category="correlation",
                    entity_id="",
                    title="Coupure combinée électricité + Internet",
                    detail="Perte électrique significative et perte simultanée des deux accès Internet.",
                    level=2,
                    severity="correlated",
                )
            )

        for state in self._states(
            self._configured(CONF_OTHER_ENTITIES, []), "Other", degraded
        ):
            reason = self._analyse_generic(state)
            if reason:
                infrastructure.append(reason)

        external.sort(key=lambda r: (r.level, r.source, r.title))
        infrastructure.sort(key=lambda r: (r.level, r.source, r.title))
        reasons = sorted(external + infrastructure, key=lambda r: (r.level, r.source, r.title))

        external_level = min((r.level for r in external), default=5)
        infrastructure_level = min((r.level for r in infrastructure), default=5)
        local_level = min(external_level, infrastructure_level)
        automatic_level = local_level

        override = self.settings.get(CONF_MANUAL_OVERRIDE, DEFAULT_OVERRIDE)
        level = automatic_level
        if isinstance(override, str) and override.startswith("defcon_"):
            try:
                level = int(override.rsplit("_", 1)[1])
            except ValueError:
                level = automatic_level
        level = max(1, min(5, level))

        summary = self._build_summary(
            reasons, external_level, infrastructure_level, automatic_level, level, override
        )
        snapshot = DefconSnapshot(
            level=level,
            automatic_level=automatic_level,
            local_level=local_level,
            external_level=external_level,
            infrastructure_level=infrastructure_level,
            level_name=LEVEL_NAMES[level],
            color=LEVEL_COLORS[level],
            summary=summary,
            reasons=reasons,
            external_reasons=external,
            infrastructure_reasons=infrastructure,
            degraded_sources=degraded,
            evaluated_at=dt_util.utcnow(),
            manual_override=str(override),
        )

        if self._last_level is not None and self._last_level != level:
            self.hass.bus.async_fire(
                EVENT_LEVEL_CHANGED,
                {
                    "old_level": self._last_level,
                    "new_level": level,
                    "automatic_level": automatic_level,
                    "external_level": external_level,
                    "infrastructure_level": infrastructure_level,
                    "summary": summary,
                    "reasons": [asdict(reason) for reason in reasons],
                },
            )
        self._last_level = level
        return snapshot

    async def _async_analyse_nina(self, state: State) -> DefconReason | None:
        if state.state.lower() in ("off", "0", "false"):
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
                _LOGGER.debug("NINA details unavailable for %s: %s", state.entity_id, err)

        attrs = {**state.attributes, **details}
        headline = self._first_text(attrs, "headline", "title", "event")
        detail = self._first_text(attrs, "description", "instruction", "sender")
        severity = str(attrs.get("severity", "")).strip().lower()
        msg_type = str(attrs.get("msgType", attrs.get("message_type", ""))).lower()

        if "cancel" in msg_type or "entwarn" in headline.lower():
            return None

        level = {
            "minor": 4,
            "moderate": 3,
            "severe": 2,
            "extreme": 1,
        }.get(severity, 3)

        return DefconReason(
            source="NINA",
            category="official_warning",
            entity_id=state.entity_id,
            title=headline or state.name or "Official warning",
            detail=self._clean_text(detail),
            level=level,
            severity=severity or "active",
        )

    def _analyse_dwd(self, state: State, advance: bool) -> list[DefconReason]:
        try:
            sensor_level = int(float(state.state))
        except (TypeError, ValueError):
            sensor_level = 0

        warning_indexes: set[int] = set()
        for key in state.attributes:
            match = re.fullmatch(r"warning_(\d+)_level", key)
            if match:
                warning_indexes.add(int(match.group(1)))

        raw_levels: list[tuple[int, int | None]] = []
        if warning_indexes:
            for index in sorted(warning_indexes):
                try:
                    raw_levels.append((int(state.attributes.get(f"warning_{index}_level", 0)), index))
                except (TypeError, ValueError):
                    continue
        elif sensor_level > 0:
            raw_levels.append((sensor_level, None))

        reasons: list[DefconReason] = []
        for warning_level, index in raw_levels:
            if warning_level <= 0:
                continue
            if advance:
                level = 3 if warning_level >= 4 else 4
            else:
                level = 2 if warning_level >= 4 else 3 if warning_level >= 3 else 4

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
            reasons.append(
                DefconReason(
                    source="DWD anticipé" if advance else "DWD",
                    category="weather",
                    entity_id=state.entity_id,
                    title=title or state.name or "Weather warning",
                    detail=self._clean_text(detail),
                    level=level,
                    severity=str(warning_level),
                )
            )
        return reasons

    def _analyse_numeric_scale(
        self, state: State, source: str, category: str
    ) -> DefconReason | None:
        try:
            raw = int(float(state.state))
        except (TypeError, ValueError):
            return None
        if raw <= 0:
            return None
        level = 4 if raw == 1 else 3 if raw == 2 else 2 if raw == 3 else 1
        return DefconReason(
            source=source,
            category=category,
            entity_id=state.entity_id,
            title=state.name or source,
            detail=f"Niveau source: {raw}",
            level=level,
            severity=str(raw),
        )

    def _analyse_uba_group(self, states: list[State]) -> DefconReason | None:
        """Evaluate UBA LQI as a corroborated regional signal.

        One isolated LQI 3 is ignored. DEFCON 4 requires either:
        - at least one monitored station at LQI 4 or above, or
        - at least two monitored stations at LQI 3 or above.
        """
        readings: list[tuple[State, int]] = []
        for state in states:
            try:
                readings.append((state, int(float(state.state))))
            except (TypeError, ValueError):
                continue

        high = [(state, lqi) for state, lqi in readings if lqi >= 4]
        elevated = [(state, lqi) for state, lqi in readings if lqi >= 3]

        if not high and len(elevated) < 2:
            return None

        triggering = high if high else elevated
        detail = "; ".join(
            f"{state.name or state.entity_id}: LQI {lqi}"
            for state, lqi in triggering
        )
        return DefconReason(
            source="UBA LQI",
            category="air_quality",
            entity_id=",".join(state.entity_id for state, _ in triggering),
            title="Dégradation régionale de la qualité de l'air",
            detail=detail,
            level=4,
            severity="corroborated",
        )

    def _analyse_bfs(self, state: State) -> DefconReason | None:
        value = state.state.strip().lower().replace(" ", "_")
        normal = (
            "within_natural_range",
            "natural_range",
            "normal",
            "unauffaellig",
            "unauffällig",
        )
        if any(token in value for token in normal) or "below" in value:
            return None
        severe = any(
            token in value
            for token in ("strong", "significant", "alarm", "critical", "extreme", "severe")
        )
        return DefconReason(
            source="BfS ODL",
            category="radiation",
            entity_id=state.entity_id,
            title=state.name or "Radiation assessment",
            detail=state.state,
            level=2 if severe else 3,
            severity=state.state,
        )

    def _analyse_lightning(
        self, degraded: list[dict[str, str]]
    ) -> DefconReason | None:
        counts = self._states(
            self._configured(CONF_LIGHTNING_COUNT_ENTITIES, DEFAULT_LIGHTNING_COUNT_ENTITIES),
            "Blitzortung count",
            degraded,
        )
        count = max((self._as_float(s.state) or 0 for s in counts), default=0)
        if count <= 0:
            return None

        # Blitzortung distance is often "unknown" when there has been no strike.
        # Only evaluate its availability after a non-zero strike count.
        distances = self._states(
            self._configured(CONF_LIGHTNING_DISTANCE_ENTITIES, DEFAULT_LIGHTNING_DISTANCE_ENTITIES),
            "Blitzortung distance",
            degraded,
        )
        distance_values = [self._as_float(s.state) for s in distances]
        distance_values = [v for v in distance_values if v is not None]
        distance = min(distance_values) if distance_values else None
        if distance is None:
            level = 4
        elif distance <= 5:
            level = 3
        elif distance <= 15:
            level = 4
        else:
            return None
        detail = f"{int(count)} impact(s)"
        if distance is not None:
            detail += f", plus proche à {distance:.1f} km"
        return DefconReason(
            source="Blitzortung",
            category="lightning",
            entity_id=counts[0].entity_id if counts else "",
            title="Foudre à proximité",
            detail=detail,
            level=level,
            severity="nearby",
        )

    def _analyse_noaa(self, degraded: list[dict[str, str]]) -> list[DefconReason]:
        reasons: list[DefconReason] = []
        states = self._states(
            self._configured(CONF_NOAA_ENTITIES, DEFAULT_NOAA_ENTITIES),
            "NOAA Space Weather",
            degraded,
        )
        for state in states:
            eid = state.entity_id.lower()
            value = state.state.strip().lower()
            number = self._as_float(state.state)
            level: int | None = None
            if "planetary_k_index" in eid or eid.endswith("k_index"):
                if number is not None:
                    level = 2 if number >= 8 else 3 if number >= 7 else 4 if number >= 5 else None
            elif "a_index" in eid and number is not None:
                level = 2 if number >= 100 else 3 if number >= 50 else 4 if number >= 30 else None
            elif "polar_cap" in eid:
                level = 2 if "red" in value else 3 if "orange" in value else 4 if "yellow" in value else None
            if level is not None:
                reasons.append(
                    DefconReason(
                        source="NOAA Space Weather",
                        category="space_weather",
                        entity_id=state.entity_id,
                        title=state.name or "Space weather",
                        detail=state.state,
                        level=level,
                        severity=state.state,
                    )
                )
        return reasons

    def _analyse_fire(self, degraded: list[dict[str, str]]) -> DefconReason | None:
        heat_states = self._states(
            self._configured(CONF_FIRE_HEAT_ENTITIES, DEFAULT_FIRE_HEAT_ENTITIES),
            "Fire heat",
            degraded,
        )
        smoke_states = self._states(
            self._configured(CONF_FIRE_SMOKE_ENTITIES, DEFAULT_FIRE_SMOKE_ENTITIES),
            "Fire smoke",
            degraded,
        )
        heat = any(self._is_active(s) for s in heat_states)
        smoke = any(self._is_active(s) for s in smoke_states)
        if not heat and not smoke:
            return None
        if heat and smoke:
            title, level, severity = "Chaleur et fumée détectées dans la chaufferie", 1, "heat+smoke"
        elif smoke:
            title, level, severity = "Fumée détectée dans la chaufferie", 2, "smoke"
        else:
            title, level, severity = "Chaleur anormale détectée dans la chaufferie", 2, "heat"
        return DefconReason(
            source="Incendie maison",
            category="fire",
            entity_id=",".join(s.entity_id for s in heat_states + smoke_states),
            title=title,
            detail="Détection locale Home Assistant.",
            level=level,
            severity=severity,
        )

    def _analyse_grid(self, degraded: list[dict[str, str]]) -> DefconReason | None:
        voltage_states = self._states(
            self._configured(CONF_GRID_VOLTAGE_ENTITIES, DEFAULT_GRID_VOLTAGE_ENTITIES),
            "Grid voltage",
            degraded,
        )
        alarm_states = self._states(
            self._configured(CONF_GRID_ALARM_ENTITIES, DEFAULT_GRID_ALARM_ENTITIES),
            "Victron grid alarm",
            degraded,
        )
        soc_states = self._states(
            self._configured(CONF_BATTERY_SOC_ENTITIES, DEFAULT_BATTERY_SOC_ENTITIES),
            "Battery SOC",
            degraded,
        )

        voltages = [(s.entity_id, self._as_float(s.state)) for s in voltage_states]
        bad = [(eid, v) for eid, v in voltages if v is not None and (v < 180 or v > 260)]
        alarm = any(
            s.state.strip().lower() not in ("no_alarm", "no alarm", "off", "0", "normal", "ok")
            for s in alarm_states
        )

        level: int | None = None
        severity = ""
        if alarm:
            level, severity = 3, "grid_lost"
        elif len(bad) >= 2:
            level, severity = 3, "multi_phase_fault"
        elif len(bad) == 1:
            level, severity = 4, "single_phase_fault"

        if level is None:
            return None

        soc_values = [self._as_float(s.state) for s in soc_states]
        soc_values = [v for v in soc_values if v is not None]
        soc = min(soc_values) if soc_values else None
        if severity in ("grid_lost", "multi_phase_fault") and soc is not None:
            if soc < 20:
                level = 1
            elif soc < 35:
                level = 2

        voltage_text = ", ".join(
            f"{eid.rsplit('_', 2)[-2:]}={v:.1f}V" for eid, v in voltages if v is not None
        )
        detail = voltage_text or "Tensions réseau indisponibles"
        if soc is not None:
            detail += f"; SOC batterie {soc:.0f}%"

        return DefconReason(
            source="Réseau électrique",
            category="power",
            entity_id=",".join(s.entity_id for s in voltage_states + alarm_states),
            title="Anomalie alimentation électrique",
            detail=detail,
            level=level,
            severity=severity,
        )

    def _analyse_internet(self, degraded: list[dict[str, str]]) -> DefconReason | None:
        telekom = self._states(
            self._configured(CONF_WAN_TELEKOM_ENTITIES, DEFAULT_WAN_TELEKOM_ENTITIES),
            "WAN Telekom",
            degraded,
        )
        vodafone = self._states(
            self._configured(CONF_WAN_VODAFONE_ENTITIES, DEFAULT_WAN_VODAFONE_ENTITIES),
            "WAN Vodafone",
            degraded,
        )

        telekom_down = bool(telekom) and all(not self._is_active(s) for s in telekom)
        vodafone_down = bool(vodafone) and all(not self._is_active(s) for s in vodafone)
        if not telekom_down and not vodafone_down:
            return None

        if telekom_down and vodafone_down:
            level, title, severity = 3, "Telekom et Vodafone indisponibles", "dual_wan_down"
        else:
            level = 4
            title = "Telekom indisponible" if telekom_down else "Vodafone indisponible"
            severity = "single_wan_down"

        return DefconReason(
            source="Internet",
            category="connectivity",
            entity_id=",".join(s.entity_id for s in telekom + vodafone),
            title=title,
            detail="État des liaisons Internet du routeur.",
            level=level,
            severity=severity,
        )

    def _analyse_generic(self, state: State) -> DefconReason | None:
        if state.state.lower() in ("off", "0", "ok", "normal", "false"):
            return None
        text = self._state_text(state).lower()
        active_boolean = state.state.lower() in ("on", "true", "unsafe", "problem")
        if not active_boolean and not any(keyword in text for keyword in _GENERIC_PROBLEM):
            return None
        return DefconReason(
            source="Other",
            category="other",
            entity_id=state.entity_id,
            title=state.name or state.entity_id,
            detail=self._clean_text(self._state_text(state), 400),
            level=4,
            severity="generic",
        )

    @staticmethod
    def _is_active(state: State) -> bool:
        return state.state.strip().lower() in (
            "on", "true", "1", "open", "detected", "alarm", "active", "connected"
        )

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
        reasons: list[DefconReason],
        external_level: int,
        infrastructure_level: int,
        automatic_level: int,
        level: int,
        override: str,
    ) -> str:
        if reasons:
            important = [r.title for r in reasons if r.level == automatic_level]
            base = "; ".join(important)[:700]
        else:
            base = "Aucune alerte active parmi les sources configurées"

        summary = (
            f"Externe DEFCON {external_level}; infrastructure DEFCON {infrastructure_level}. "
            f"{base}."
        )
        if override != DEFAULT_OVERRIDE and level != automatic_level:
            return (
                f"Override manuel DEFCON {level}; automatique DEFCON {automatic_level}. "
                f"{summary}"
            )
        return summary
