"""DEFCON Home integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CARD_FILE, CARD_URL, DOMAIN, PLATFORMS
from .coordinator import DefconCoordinator

_LOGGER = logging.getLogger(__name__)


def _entry_data(hass: HomeAssistant) -> dict[str, DefconCoordinator]:
    """Return integration runtime data."""
    return hass.data.setdefault(DOMAIN, {})


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DEFCON Home from a config entry."""
    await _async_register_frontend(hass)

    coordinator = DefconCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_start()

    _entry_data(hass)[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = _entry_data(hass).get(entry.entry_id)
    if coordinator:
        coordinator.async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        _entry_data(hass).pop(entry.entry_id, None)

    try:
        remove_extra_js_url(hass, CARD_URL)
        hass.data.pop(f"{DOMAIN}_frontend_registered", None)
    except ValueError:
        pass

    return unloaded
