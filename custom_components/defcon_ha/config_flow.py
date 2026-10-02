"""Config flow for DEFCON Home."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_SOC_ENTITIES,
    CONF_BFS_ASSESSMENT_ENTITIES,
    CONF_DWD_ADVANCE_ENTITIES,
    CONF_DWD_CURRENT_ENTITIES,
    CONF_FIRE_HEAT_ENTITIES,
    CONF_FIRE_SMOKE_ENTITIES,
    CONF_FLOOD_ENTITIES,
    CONF_GRID_ALARM_ENTITIES,
    CONF_GRID_VOLTAGE_ENTITIES,
    CONF_LIGHTNING_COUNT_ENTITIES,
    CONF_LIGHTNING_DISTANCE_ENTITIES,
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
    DEFAULT_NAME,
    DEFAULT_NINA_ENTITIES,
    DEFAULT_NOAA_ENTITIES,
    DEFAULT_PEGEL_STAGE_ENTITIES,
    DEFAULT_UBA_LQI_ENTITIES,
    DEFAULT_WAN_TELEKOM_ENTITIES,
    DEFAULT_WAN_VODAFONE_ENTITIES,
    DOMAIN,
)

_ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=True)
)


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    values = values or {}

    def current(key: str, default: list[str]) -> list[str]:
        value = values.get(key, default)
        return list(value) if isinstance(value, (list, tuple)) else list(default)

    return vol.Schema(
        {
            vol.Optional(
                CONF_NINA_ENTITIES,
                default=current(CONF_NINA_ENTITIES, DEFAULT_NINA_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_DWD_CURRENT_ENTITIES,
                default=current(CONF_DWD_CURRENT_ENTITIES, DEFAULT_DWD_CURRENT_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_DWD_ADVANCE_ENTITIES,
                default=current(CONF_DWD_ADVANCE_ENTITIES, DEFAULT_DWD_ADVANCE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_FLOOD_ENTITIES,
                default=current(CONF_FLOOD_ENTITIES, DEFAULT_FLOOD_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_PEGEL_STAGE_ENTITIES,
                default=current(CONF_PEGEL_STAGE_ENTITIES, DEFAULT_PEGEL_STAGE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_UBA_LQI_ENTITIES,
                default=current(CONF_UBA_LQI_ENTITIES, DEFAULT_UBA_LQI_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_BFS_ASSESSMENT_ENTITIES,
                default=current(CONF_BFS_ASSESSMENT_ENTITIES, DEFAULT_BFS_ASSESSMENT_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_LIGHTNING_COUNT_ENTITIES,
                default=current(CONF_LIGHTNING_COUNT_ENTITIES, DEFAULT_LIGHTNING_COUNT_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_LIGHTNING_DISTANCE_ENTITIES,
                default=current(CONF_LIGHTNING_DISTANCE_ENTITIES, DEFAULT_LIGHTNING_DISTANCE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_NOAA_ENTITIES,
                default=current(CONF_NOAA_ENTITIES, DEFAULT_NOAA_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_FIRE_HEAT_ENTITIES,
                default=current(CONF_FIRE_HEAT_ENTITIES, DEFAULT_FIRE_HEAT_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_FIRE_SMOKE_ENTITIES,
                default=current(CONF_FIRE_SMOKE_ENTITIES, DEFAULT_FIRE_SMOKE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_GRID_VOLTAGE_ENTITIES,
                default=current(CONF_GRID_VOLTAGE_ENTITIES, DEFAULT_GRID_VOLTAGE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_GRID_ALARM_ENTITIES,
                default=current(CONF_GRID_ALARM_ENTITIES, DEFAULT_GRID_ALARM_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_BATTERY_SOC_ENTITIES,
                default=current(CONF_BATTERY_SOC_ENTITIES, DEFAULT_BATTERY_SOC_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_WAN_TELEKOM_ENTITIES,
                default=current(CONF_WAN_TELEKOM_ENTITIES, DEFAULT_WAN_TELEKOM_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_WAN_VODAFONE_ENTITIES,
                default=current(CONF_WAN_VODAFONE_ENTITIES, DEFAULT_WAN_VODAFONE_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_OTHER_ENTITIES,
                default=current(CONF_OTHER_ENTITIES, []),
            ): _ENTITY_SELECTOR,
        }
    )


class DefconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DEFCON Home."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DefconOptionsFlow:
        return DefconOptionsFlow()


class DefconOptionsFlow(config_entries.OptionsFlow):
    """Edit deterministic DEFCON source entities."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=_schema(current))
