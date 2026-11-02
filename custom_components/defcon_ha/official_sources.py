"""Official situation feeds and HA Tankerkoenig fuel prices for Lagezentrum.

Operator pages are checked directly; a failed check is 'unknown', never 'normal'.
No external JSON or additional API credentials are required here.
Tankerkoenig itself must be configured separately in Home Assistant.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .official_parsers import fuel_medians, parse_electricity, parse_gas, parse_water

_LOGGER = logging.getLogger(__name__)

OFFICIAL_URLS = {
    "gas": "https://www.bundesnetzagentur.de/DE/Gasversorgung/aktuelle_gasversorgung/start.html",
    "water": "https://www.hamburgwasser.de/service/aktuell/stoerungen",
    "electricity": "https://www.hamburger-energienetze.de/stoerung-melden",
}
PARSERS = {"gas": parse_gas, "water": parse_water, "electricity": parse_electricity}
CHECK_INTERVAL = timedelta(minutes=10)
GAS_INTERVAL = timedelta(hours=6)
FUEL_HISTORY_DAYS = 35
SOURCE_MAX_AGE = {"gas": timedelta(hours=26), "water": timedelta(minutes=25), "electricity": timedelta(minutes=25)}


@dataclass(slots=True)
class OfficialSnapshot:
    sources: dict[str, dict[str, Any]]
    fuel: dict[str, Any]
    signals: list[dict[str, Any]]
    evaluated_at: datetime


def _official_signal(key: str, category: str, title: str, detail: str, *,
                     severity: str = "signal_faible", relevance: str = "potential",
                     source: str = "official", url: str = "", major_crisis: bool = False) -> dict[str, Any]:
    return {
        "status": "active",
        "event_key": key,
        "phenomenon_key": key,
        "signal_class": severity,
        "signal_confirmed": True,
        "major_crisis": major_crisis,
        "importance": 3 if severity == "signal_serieux" else 2,
        "analysis_confidence": 95,
        "confidence_score": 95 if source == "official" else 80,
        "source_class": source,
        "corroboration_count": 1,
        "direct_relevance": relevance,
        "protective_action": False,
        "category": category,
        "title": title,
        "summary_fr": detail,
        "link": url,
    }


class OfficialSourcesCoordinator(DataUpdateCoordinator[OfficialSnapshot]):
    """Load three operator pages, and locally aggregate Tankerkoenig prices."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_official",
            update_interval=CHECK_INTERVAL,
        )
        self.entry = entry
        self.session = aiohttp_client.async_get_clientsession(hass)
        self._store = Store[dict[str, Any]](hass, 1, f"{DOMAIN}.official.{entry.entry_id}")
        self._history: list[dict[str, Any]] = []
        self._loaded = False
        self._gas_last_fetch: datetime | None = None
        self._gas_result: dict[str, Any] | None = None

    async def _fetch(self, key: str) -> dict[str, Any]:
        try:
            async with self.session.get(
                OFFICIAL_URLS[key],
                timeout=aiohttp.ClientTimeout(total=18),
                headers={"User-Agent": "DEFCON-Home/0.5 (+https://github.com/adrien3287/defcon-ha)"},
            ) as response:
                response.raise_for_status()
                html = await response.text(errors="replace")
                if len(html) < 300:
                    raise ValueError("Unexpectedly short operator response")
                parsed = PARSERS[key](html)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            _LOGGER.warning("Official Lagezentrum source %s not verified: %s", key, exc)
            parsed = {"status": "unknown", "detail": str(exc)[:250]}
        except Exception:
            _LOGGER.exception("Unexpected official source failure for %s", key)
            parsed = {"status": "unknown", "detail": "unexpected fetch or parse error"}
        return {**parsed, "source_url": OFFICIAL_URLS[key], "checked_at": dt_util.utcnow().isoformat()}

    def _fuel_readings(self) -> tuple[dict[str, Any], dict[str, int]]:
        """Use only price entities belonging to the installed Tankerkoenig integration."""
        prices: dict[str, list[float]] = {"diesel": [], "e5": [], "e10": []}
        registry = er.async_get(self.hass)
        for reg_entry in registry.entities.values():
            if reg_entry.platform != "tankerkoenig" or reg_entry.domain != "sensor":
                continue
            state = self.hass.states.get(reg_entry.entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            try:
                price = float(state.state)
            except (TypeError, ValueError):
                continue
            name = (str(state.attributes.get("fuel_type", "")) or
                    str(reg_entry.original_name or "")).lower().replace(" ", "_")
            entity_id = reg_entry.entity_id.lower()
            if "diesel" in name or entity_id.endswith("_diesel"):
                fuel = "diesel"
            elif "e10" in name or entity_id.endswith("_super_e10"):
                fuel = "e10"
            elif "super" in name or "e5" in name or entity_id.endswith("_super"):
                fuel = "e5"
            else:
                continue
            if 0.5 <= price <= 4.0:
                prices[fuel].append(price)
        return fuel_medians(prices), {key: len(v) for key, v in prices.items()}

    async def _async_update_data(self) -> OfficialSnapshot:
        if not self._loaded:
            saved = await self._store.async_load() or {}
            self._history = [i for i in saved.get("history", []) if isinstance(i, dict)]
            self._loaded = True

        now = dt_util.utcnow()
        gas_due = self._gas_last_fetch is None or now - self._gas_last_fetch >= GAS_INTERVAL
        if gas_due:
            # Load all three independent operator sources concurrently.
            gas, water, electricity = await asyncio.gather(
                self._fetch("gas"), self._fetch("water"), self._fetch("electricity")
            )
            self._gas_last_fetch = now
            self._gas_result = gas
        else:
            gas = dict(self._gas_result or {"status": "unknown"})
            water, electricity = await asyncio.gather(
                self._fetch("water"), self._fetch("electricity")
            )
        # Never treat a stale cached page as current.
        for key, source in (("gas", gas),):
            seen = source.get("checked_at")
            try:
                then = datetime.fromisoformat(str(seen))
            except (ValueError, TypeError):
                then = None
            if then is None or then.tzinfo is None or now - then > SOURCE_MAX_AGE[key]:
                gas = {**gas, "status": "unknown", "detail": "Source outdated"}

        sources = {"gas": gas, "water": water, "electricity": electricity}

        medians, counts = self._fuel_readings()
        today = now.date().isoformat()
        daily = {"date": today, "gas": gas.get("storage_percent") if gas.get("status") != "unknown" else None,
                 **medians}
        changed = not self._history or self._history[-1].get("date") != today
        if changed:
            self._history.append(daily)
        else:
            self._history[-1].update({key: value for key, value in daily.items() if value is not None})
        self._history = [
            item for item in self._history
            if item.get("date", "") >= (now.date() - timedelta(days=FUEL_HISTORY_DAYS)).isoformat()
        ]
        if changed:
            await self._store.async_save({"history": self._history})

        previous = next((
            row for row in reversed(self._history)
            if row.get("date", "") <= (now.date() - timedelta(days=7)).isoformat()
        ), {})
        trends = {}
        for fuel in ("diesel", "e5", "e10", "gas"):
            current = daily.get(fuel)
            baseline = previous.get(fuel)
            if isinstance(current, (float, int)) and isinstance(baseline, (float, int)) and baseline > 0:
                trends[fuel] = round((current - baseline) / baseline * 100, 1)
            else:
                trends[fuel] = None
        fuel_data = {
            "status": "ok" if any(v is not None for v in medians.values()) else "not_configured",
            "medians": medians, "station_counts": counts,
            "change_7d_percent": {key: trends[key] for key in ("diesel", "e5", "e10")},
            "gas_change_7d_percent": trends["gas"],
            "source_url": "https://www.home-assistant.io/integrations/tankerkoenig",
            "checked_at": now.isoformat(),
        }
        signals: list[dict[str, Any]] = []
        if gas.get("status") == "crisis":
            signals.append(_official_signal(
                "germany-gas-supply", "energy", "Crise de l'approvisionnement gazier allemand",
                gas.get("detail", ""), severity="signal_serieux", url=OFFICIAL_URLS["gas"], major_crisis=True,
            ))
        elif gas.get("status") == "stable" and gas.get("lower_than_previous_years") and gas.get("storage_percent", 100) < 65:
            signals.append(_official_signal(
                "germany-gas-storage", "energy", "Stockage gaz allemand sensiblement bas",
                f"Stockage {gas['storage_percent']} %, approvisionnement officiellement stable.",
                url=OFFICIAL_URLS["gas"],
            ))

        for key, label, category in (
            ("water", "Incident eau Hamburg Wasser", "water"),
            ("electricity", "Perturbation réseau Hamburger Energienetze", "electricity"),
        ):
            source = sources[key]
            if source.get("status") == "active" and source.get("local"):
                signals.append(_official_signal(
                    f"hamburg-{key if key == 'water' else 'electricity'}-local", category, label, source.get("detail", ""),
                    relevance="direct" if "Koboldweg" in source.get("area", "") else "potential",
                    url=OFFICIAL_URLS[key],
                ))

        # A 7-day price jump is a precursor, NOT evidence of a fuel shortage.
        # Require 3 different stations and a >=25% sustained local median rise.
        if any(
            counts.get(k, 0) >= 3 and trends.get(k) is not None and trends[k] >= 25
            for k in ("diesel", "e5", "e10")
        ):
            signals.append(_official_signal(
                "hamburg-fuel-price-spike", "supply", "Hausse anormale du prix des carburants",
                f"Médianes locales sur 7 jours : {fuel_data['change_7d_percent']}. "
                "Hausse de prix seulement, aucune pénurie prouvée.",
                source="official", url="https://www.home-assistant.io/integrations/tankerkoenig",
            ))

        return OfficialSnapshot(sources, fuel_data, signals, now)
