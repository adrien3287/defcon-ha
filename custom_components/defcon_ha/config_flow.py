"""Config flow for DEFCON Home."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CONTEXT_ENABLED,
    CONF_DWD_ENTITIES,
    CONF_GITHUB_OWNER,
    CONF_GITHUB_PATH,
    CONF_GITHUB_REPO,
    CONF_GITHUB_TOKEN,
    CONF_HVV_ENTITIES,
    CONF_NINA_ENTITIES,
    CONF_OTHER_ENTITIES,
    DEFAULT_CONTEXT_ENABLED,
    DEFAULT_DWD_ENTITIES,
    DEFAULT_GITHUB_OWNER,
    DEFAULT_GITHUB_PATH,
    DEFAULT_GITHUB_REPO,
    DEFAULT_NAME,
    DEFAULT_NINA_ENTITIES,
    DOMAIN,
)

_ENTITY_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(multiple=True))
_TOKEN_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    values = values or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_NINA_ENTITIES,
                default=values.get(CONF_NINA_ENTITIES, DEFAULT_NINA_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_DWD_ENTITIES,
                default=values.get(CONF_DWD_ENTITIES, DEFAULT_DWD_ENTITIES),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_HVV_ENTITIES,
                default=values.get(CONF_HVV_ENTITIES, []),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_OTHER_ENTITIES,
                default=values.get(CONF_OTHER_ENTITIES, []),
            ): _ENTITY_SELECTOR,
            vol.Optional(
                CONF_CONTEXT_ENABLED,
                default=values.get(CONF_CONTEXT_ENABLED, DEFAULT_CONTEXT_ENABLED),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_GITHUB_OWNER,
                default=values.get(CONF_GITHUB_OWNER, DEFAULT_GITHUB_OWNER),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_GITHUB_REPO,
                default=values.get(CONF_GITHUB_REPO, DEFAULT_GITHUB_REPO),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_GITHUB_PATH,
                default=values.get(CONF_GITHUB_PATH, DEFAULT_GITHUB_PATH),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_GITHUB_TOKEN,
                default=values.get(CONF_GITHUB_TOKEN, ""),
            ): _TOKEN_SELECTOR,
        }
    )


class DefconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DEFCON Home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create the single DEFCON Home configuration."""
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
        """Return options flow."""
        return DefconOptionsFlow(config_entry)


class DefconOptionsFlow(config_entries.OptionsFlow):
    """Edit DEFCON Home sources and private context feed settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            data = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=data)

        return self.async_show_form(step_id="init", data_schema=_schema(current))
