"""DEFCON Home integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CARD_FILE,
    CARD_URL,
    CONF_DWD_ADVANCE_ENTITIES,
    CONF_DWD_CURRENT_ENTITIES,
    CONF_DWD_ENTITIES,
    CONF_FIRE_HEAT_ENTITIES,
    CONF_FIRE_SMOKE_ENTITIES,
    DOMAIN,
    PLATFORMS,
)
from .context import ContextCoordinator
from .coordinator import DefconCoordinator

_LOGGER = logging.getLogger(__name__)


def _entry_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration runtime data."""
    return hass.data.setdefault(DOMAIN, {})


def _context_key(entry: ConfigEntry) -> str:
    """Return runtime key for the independent context coordinator."""
    return f"{entry.entry_id}_context"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and load the bundled Lovelace card."""
    marker = f"{DOMAIN}_frontend_registered"
    if hass.data.get(marker):
        return

    card_path = Path(__file__).parent / CARD_FILE
    if not card_path.exists():
        _LOGGER.warning("DEFCON Home card was not found at %s", card_path)
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(card_path), False)]
        )
    except RuntimeError:
        pass

    add_extra_js_url(hass, CARD_URL)
    hass.data[marker] = True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated sources/feed settings without requiring a restart."""
    coordinator = _entry_data(hass).get(entry.entry_id)
    if coordinator is None:
        return
    coordinator.async_start()
    await coordinator.async_request_refresh()

    context = _entry_data(hass).get(_context_key(entry))
    if isinstance(context, ContextCoordinator):
        await context.async_request_refresh()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy DEFCON Home config entries."""
    if entry.version >= 3:
        return True

    data = dict(entry.data)
    options = dict(entry.options)

    if entry.version < 2:
        legacy_dwd = data.pop(CONF_DWD_ENTITIES, [])
        if isinstance(legacy_dwd, (list, tuple)):
            data.setdefault(
                CONF_DWD_CURRENT_ENTITIES,
                [e for e in legacy_dwd if "antici" not in e.lower() and "advance" not in e.lower()],
            )
            data.setdefault(
                CONF_DWD_ADVANCE_ENTITIES,
                [e for e in legacy_dwd if "antici" in e.lower() or "advance" in e.lower()],
            )

        for legacy_key in (
            "context_enabled",
            "github_owner",
            "github_repo",
            "github_path",
            "github_token",
            "hvv_entities",
        ):
            data.pop(legacy_key, None)

    if entry.version < 3:
        old_heat = ["binary_sensor.chaufferie_detection_incendie_entree_0"]
        old_smoke = ["binary_sensor.chaufferie_detection_incendie_entree_1"]
        new_heat = ["binary_sensor.chaufferie_detection_incendie_entree_1"]
        new_smoke = ["binary_sensor.chaufferie_detection_incendie_entree_0"]

        for container in (data, options):
            if (
                container.get(CONF_FIRE_HEAT_ENTITIES) == old_heat
                and container.get(CONF_FIRE_SMOKE_ENTITIES) == old_smoke
            ):
                container[CONF_FIRE_HEAT_ENTITIES] = new_heat
                container[CONF_FIRE_SMOKE_ENTITIES] = new_smoke

    hass.config_entries.async_update_entry(
        entry,
        data=data,
        options=options,
        version=3,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DEFCON Home from a config entry."""
    await _async_register_frontend(hass)

    coordinator = DefconCoordinator(hass, entry)
    context = ContextCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    await context.async_config_entry_first_refresh()

    coordinator.async_start()
    context.async_start()

    runtime = _entry_data(hass)
    runtime[entry.entry_id] = coordinator
    runtime[_context_key(entry)] = context

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    runtime = _entry_data(hass)
    coordinator = runtime.get(entry.entry_id)
    context = runtime.get(_context_key(entry))

    if isinstance(coordinator, DefconCoordinator):
        coordinator.async_stop()
    if isinstance(context, ContextCoordinator):
        context.async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime.pop(entry.entry_id, None)
        runtime.pop(_context_key(entry), None)

    try:
        remove_extra_js_url(hass, CARD_URL)
        hass.data.pop(f"{DOMAIN}_frontend_registered", None)
    except ValueError:
        pass

    return unloaded
