"""Button platform for DEFCON Home."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, RSS_RECOMMENDED_SOURCES
from .coordinator import DefconCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DEFCON Home buttons."""
    coordinator: DefconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DefconRefreshButton(coordinator, entry),
            DefconInstallRssSourcesButton(hass, entry),
        ]
    )


class DefconRefreshButton(CoordinatorEntity[DefconCoordinator], ButtonEntity):
    """Force a deterministic local reevaluation."""

    _attr_has_entity_name = True
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: DefconCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class DefconInstallRssSourcesButton(ButtonEntity):
    """Bulk-install the curated Feedreader sources used by the context layer."""

    _attr_has_entity_name = True
    _attr_name = "Install RSS sources"
    _attr_icon = "mdi:rss"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_install_rss_sources"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "DEFCON Home",
            "manufacturer": "DEFCON Home",
            "model": "Household situation engine",
        }
        self._running = False
        self._last_result: dict[str, Any] = {
            "installed_now": [],
            "already_present": [],
            "failed": [],
            "last_run": "",
        }

    def _existing_urls(self) -> set[str]:
        """Return URLs already configured in the Feedreader integration."""
        return {
            str(config_entry.data.get(CONF_URL, "")).strip()
            for config_entry in self.hass.config_entries.async_entries("feedreader")
            if config_entry.data.get(CONF_URL)
        }

    @staticmethod
    def _source_is_present(source: dict[str, Any], existing_urls: set[str]) -> bool:
        """Return true if the canonical URL or one of its known aliases exists."""
        candidates = {str(source["url"]).strip()}
        candidates.update(
            str(alias).strip()
            for alias in source.get("aliases", [])
            if alias
        )
        return bool(candidates & existing_urls)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose current install coverage and the result of the last run."""
        existing_urls = self._existing_urls()
        configured = [
            source["name"]
            for source in RSS_RECOMMENDED_SOURCES
            if self._source_is_present(source, existing_urls)
        ]
        missing = [
            source["name"]
            for source in RSS_RECOMMENDED_SOURCES
            if not self._source_is_present(source, existing_urls)
        ]
        return {
            "recommended_count": len(RSS_RECOMMENDED_SOURCES),
            "configured_count": len(configured),
            "missing_count": len(missing),
            "configured_sources": configured,
            "missing_sources": missing,
            "running": self._running,
            **self._last_result,
        }

    async def async_press(self) -> None:
        """Install every missing curated Feedreader entry."""
        if self._running:
            return

        self._running = True
        self.async_write_ha_state()

        installed_now: list[str] = []
        already_present: list[str] = []
        failed: list[dict[str, str]] = []

        try:
            existing_urls = self._existing_urls()

            for source in RSS_RECOMMENDED_SOURCES:
                name = str(source["name"])
                url = str(source["url"])

                if self._source_is_present(source, existing_urls):
                    already_present.append(name)
                    continue

                try:
                    result = await self.hass.config_entries.flow.async_init(
                        "feedreader",
                        context={"source": config_entries.SOURCE_USER},
                        data={CONF_URL: url},
                    )
                except Exception as err:  # defensive: one broken feed must not stop all
                    _LOGGER.exception("Unable to add Feedreader source %s", name)
                    failed.append({"name": name, "error": str(err)})
                    continue

                result_type = result.get("type")

                if result_type is FlowResultType.CREATE_ENTRY:
                    installed_now.append(name)
                    existing_urls.add(url)
                    continue

                if result_type is FlowResultType.ABORT:
                    reason = str(result.get("reason", "aborted"))
                    if reason in {"already_configured", "already_in_progress"}:
                        already_present.append(name)
                        existing_urls.add(url)
                    else:
                        failed.append({"name": name, "error": reason})
                    continue

                errors = result.get("errors") or {}
                failed.append(
                    {
                        "name": name,
                        "error": (
                            str(errors)
                            if errors
                            else f"unexpected_flow_result:{result_type}"
                        ),
                    }
                )

            self._last_result = {
                "installed_now": installed_now,
                "already_present": already_present,
                "failed": failed,
                "last_run": dt_util.utcnow().isoformat(),
            }
        finally:
            self._running = False
            self.async_write_ha_state()
