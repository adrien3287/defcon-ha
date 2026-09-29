"""Config flow for DEFCON Home."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DWD_ENTITIES,
    CONF_HVV_ENTITIES,
    CONF_NINA_ENTITIES,
    CONF_OTHER_ENTITIES,
    DEFAULT_NAME,
    DOMAIN,
)

_ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=True)
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

        schema = vol.Schema(
            {
                vol.Optional(CONF_NINA_ENTITIES, default=[]): _ENTITY_SELECTOR,
                vol.Optional(CONF_DWD_ENTITIES, default=[]): _ENTITY_SELECTOR,
                vol.Optional(CONF_HVV_ENTITIES, default=[]): _ENTITY_SELECTOR,
                vol.Optional(CONF_OTHER_ENTITIES, default=[]): _ENTITY_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
