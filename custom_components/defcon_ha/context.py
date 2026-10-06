"""Event-driven contextual situation layer for DEFCON Home.

The context engine is deliberately separate from the deterministic DEFCON engine.
It stores AI-classified/news events, expires them by category, correlates repeated
reports and exposes an indicative (non-authoritative) DEFCON recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONTEXT_ACTIVE_LIMIT,
    CONTEXT_HISTORY_LIMIT,
    CONTEXT_REFRESH_MINUTES,
    CONTEXT_STALE_GRACE_HOURS,
    CONTEXT_TTL_HOURS,
    DOMAIN,
    EVENT_RSS_ANALYZED,
)

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_TRUE_VALUES = {"true", "1", "yes", "on"}
_ALLOWED_LIFECYCLE = {"new", "update", "resolved"}
_ALLOWED_SOURCE_TIERS = {"local", "national", "strategic"}
_ALLOWED_SOURCE_CLASSES = {"official", "aggregator", "public_media", "established_media", "other"}
_ALLOWED_RELEVANCE = {"direct", "potential", "none"}

_SOURCE_CONFIDENCE = {
    "official": 95,
    "aggregator": 85,
    "public_media": 85,
    "established_media": 80,
    "other": 60,
}


@dataclass(slots=True)
class ContextSnapshot:
    """Current contextual situation snapshot."""

    status: str
    active_event_count: int
    stale_event_count: int
    recommended_defcon: int
    highest_importance: int
    highest_confidence: int
    top_event: dict[str, Any] | None
    active_events: list[dict[str, Any]]
    stale_events: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]
    evaluated_at: datetime


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE_VALUES


def _as_int(
    value: Any,
    default: int = 0,
    minimum: int = 0,
    maximum: int = 100,
) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _clean_text(value: Any, *, max_len: int = 2000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9äöüß_-]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-")[:96]


def _fallback_key(data: dict[str, Any]) -> str:
    canonical = "|".join(
        (
            _clean_text(data.get("category", "other"), max_len=64).lower(),
            _clean_text(data.get("scope", ""), max_len=64).lower(),
            _clean_text(data.get("title", ""), max_len=300).lower(),
        )
    )
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return f"auto-{digest}"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return dt_util.as_utc(parsed)


def _expiry_for_event(normalized: dict[str, Any], now: datetime) -> tuple[datetime, str]:
    """Return expiry, preferring an explicit future event validity date."""
    valid_until = _parse_dt(normalized.get("valid_until"))
    if valid_until is not None:
        return valid_until, "explicit_event_date"

    ttl = timedelta(
        hours=_as_int(normalized.get("ttl_hours"), 12, 1, 168)
    )
    return now + ttl, "category_ttl"


def _event_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        _as_int(item.get("importance"), 0, 0, 3),
        1 if _as_bool(item.get("protective_action")) else 0,
        _as_int(item.get("confidence_score"), 0, 0, 100),
        _clean_text(item.get("last_seen"), max_len=64),
    )


class ContextCoordinator(DataUpdateCoordinator[ContextSnapshot]):
    """Track contextual events independently from deterministic DEFCON."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_context",
            update_interval=timedelta(minutes=CONTEXT_REFRESH_MINUTES),
        )
        self.entry = entry
        self._store = Store[dict[str, Any]](
            hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.context.{entry.entry_id}",
        )
        self._loaded = False
        self._events: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._remove_event_listener = None

    async def _async_update_data(self) -> ContextSnapshot:
        if not self._loaded:
            await self._async_load()
        now = dt_util.utcnow()
        changed = self._sweep(now)
        if changed:
            await self._async_save()
        return self._snapshot(now)

    async def _async_load(self) -> None:
        stored = await self._store.async_load() or {}
        raw_events = stored.get("events", [])
        raw_history = stored.get("history", [])
        self._events = [
            dict(item) for item in raw_events if isinstance(item, dict)
        ]
        self._history = [
            dict(item) for item in raw_history if isinstance(item, dict)
        ]
        self._loaded = True

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "events": self._events,
                "history": self._history,
            }
        )

    @callback
    def async_start(self) -> None:
        """Subscribe to analyzed context events."""
        if self._remove_event_listener is not None:
            return
        self._remove_event_listener = self.hass.bus.async_listen(
            EVENT_RSS_ANALYZED,
            self._handle_event,
        )

    @callback
    def async_stop(self) -> None:
        """Stop listening to context events."""
        if self._remove_event_listener is not None:
            self._remove_event_listener()
            self._remove_event_listener = None

    @callback
    def _handle_event(self, event: Event) -> None:
        self.hass.async_create_task(self._async_ingest_event(event))

    async def _async_ingest_event(self, event: Event) -> None:
        await self.async_ingest(
            dict(event.data),
            now=dt_util.as_utc(event.time_fired),
        )

    async def async_ingest(
        self,
        data: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> bool:
        """Ingest one normalized-context candidate from any source."""
        if not self._loaded:
            await self._async_load()

        event_time = dt_util.as_utc(now) if now is not None else dt_util.utcnow()
        changed = self._ingest(dict(data), event_time)
        changed |= self._sweep(event_time)

        if changed:
            await self._async_save()
            self.async_set_updated_data(self._snapshot(event_time))
        return changed

    async def async_sync_source(
        self,
        source_system: str,
        candidates: list[dict[str, Any]],
        *,
        now: datetime | None = None,
    ) -> bool:
        """Atomically ingest and reconcile one structured source."""
        if not self._loaded:
            await self._async_load()

        event_time = dt_util.as_utc(now) if now is not None else dt_util.utcnow()
        active_event_keys: set[str] = set()
        changed = False

        for raw in candidates:
            candidate = dict(raw)
            candidate["source_system"] = source_system
            normalized = self._normalize(candidate, event_time)
            active_event_keys.add(normalized["event_key"])
            changed |= self._ingest(candidate, event_time)

        kept: list[dict[str, Any]] = []
        for item in self._events:
            if (
                item.get("source_system") == source_system
                and item.get("event_key") not in active_event_keys
            ):
                resolved = dict(item)
                resolved["status"] = "resolved"
                resolved["resolved_at"] = event_time.isoformat()
                resolved["resolution_reason"] = "source_no_longer_reports"
                self._append_history(resolved)
                changed = True
                continue
            kept.append(item)

        self._events = kept
        changed |= self._sweep(event_time)

        if changed:
            await self._async_save()
            self.async_set_updated_data(self._snapshot(event_time))
        return changed

    async def async_reconcile_source(
        self,
        source_system: str,
        active_event_keys: set[str],
        *,
        now: datetime | None = None,
    ) -> bool:
        """Resolve events a structured source no longer reports.

        Reconciliation is source-scoped so a failed/missing CommonSight layer
        never clears events from unrelated sources.
        """
        if not self._loaded:
            await self._async_load()

        event_time = dt_util.as_utc(now) if now is not None else dt_util.utcnow()
        kept: list[dict[str, Any]] = []
        changed = False

        for item in self._events:
            if (
                item.get("source_system") == source_system
                and item.get("event_key") not in active_event_keys
            ):
                resolved = dict(item)
                resolved["status"] = "resolved"
                resolved["resolved_at"] = event_time.isoformat()
                resolved["resolution_reason"] = "source_no_longer_reports"
                self._append_history(resolved)
                changed = True
                continue
            kept.append(item)

        if changed:
            self._events = kept
            await self._async_save()
            self.async_set_updated_data(self._snapshot(event_time))
        return changed

    def _normalize(self, data: dict[str, Any], now: datetime) -> dict[str, Any]:
        category = (
            _slug(_clean_text(data.get("category", "other"), max_len=64))
            or "other"
        )
        scope = _slug(_clean_text(data.get("scope", ""), max_len=64))

        lifecycle = _clean_text(
            data.get("lifecycle", "new"), max_len=16
        ).lower()
        if lifecycle not in _ALLOWED_LIFECYCLE:
            lifecycle = "new"

        source_tier = _clean_text(
            data.get("source_tier", "local"), max_len=16
        ).lower()
        if source_tier not in _ALLOWED_SOURCE_TIERS:
            source_tier = "local"

        source_class = _clean_text(
            data.get("source_class", "other"), max_len=32
        ).lower()
        if source_class not in _ALLOWED_SOURCE_CLASSES:
            source_class = "other"

        direct_relevance = _clean_text(
            data.get("direct_relevance", "potential"), max_len=16
        ).lower()
        if direct_relevance not in _ALLOWED_RELEVANCE:
            direct_relevance = "potential"

        explicit_key = _slug(
            _clean_text(
                data.get("event_key") or data.get("incident_key"),
                max_len=128,
            )
        )
        event_key = explicit_key or _fallback_key(data)

        importance = _as_int(data.get("importance"), 0, 0, 3)
        analysis_confidence = _as_int(
            data.get("analysis_confidence"), 75, 0, 100
        )
        source_confidence = _SOURCE_CONFIDENCE[source_class]
        confidence_score = round(
            (source_confidence * 0.7) + (analysis_confidence * 0.3)
        )

        ttl_hours = CONTEXT_TTL_HOURS.get(
            category,
            CONTEXT_TTL_HOURS["other"],
        )

        published_at = _parse_dt(data.get("published_at"))
        event_start_at = _parse_dt(data.get("event_start_at"))
        valid_until = _parse_dt(data.get("valid_until"))
        source_name = _clean_text(data.get("source_name"), max_len=120)
        feed_url = _clean_text(data.get("feed_url"), max_len=500)
        link = _clean_text(data.get("link"), max_len=500)
        source_identity = source_name or feed_url or link or "unknown"
        source_system = _clean_text(
            data.get("source_system"), max_len=80
        ).lower()

        return {
            "event_key": event_key,
            "title": _clean_text(data.get("title"), max_len=500),
            "original_title": _clean_text(
                data.get("original_title"), max_len=500
            ),
            "event_timing_text": _clean_text(
                data.get("event_timing_text"), max_len=1000
            ),
            "summary_fr": _clean_text(data.get("summary_fr"), max_len=2000),
            "reason": _clean_text(data.get("reason"), max_len=2000),
            "recommended_action": _clean_text(
                data.get("recommended_action", "aucune"),
                max_len=1500,
            ),
            "category": category,
            "scope": scope,
            "affected_area": _clean_text(
                data.get("affected_area"), max_len=300
            ),
            "direct_relevance": direct_relevance,
            "protective_action": _as_bool(data.get("protective_action")),
            "importance": importance,
            "lifecycle": lifecycle,
            "source_name": source_name,
            "source_identity": source_identity,
            "source_system": source_system,
            "source_tier": source_tier,
            "source_class": source_class,
            "feed_url": feed_url,
            "link": link,
            "analysis_confidence": analysis_confidence,
            "source_confidence": source_confidence,
            "confidence_score": confidence_score,
            "published_at": (
                published_at.isoformat() if published_at else ""
            ),
            "event_start_at": (
                event_start_at.isoformat() if event_start_at else ""
            ),
            "valid_until": (
                valid_until.isoformat() if valid_until else ""
            ),
            "ttl_hours": ttl_hours,
            "received_at": now.isoformat(),
        }

    def _ingest(self, data: dict[str, Any], now: datetime) -> bool:
        normalized = self._normalize(data, now)
        relevant = _as_bool(data.get("relevant"))
        lifecycle = normalized["lifecycle"]

        index = self._find_event_index(normalized)
        if lifecycle == "resolved":
            if index is None:
                if relevant:
                    resolved = self._new_event(normalized, now)
                    resolved["status"] = "resolved"
                    resolved["resolved_at"] = now.isoformat()
                    self._append_history(resolved)
                    return True
                return False

            item = self._events.pop(index)
            self._merge_event(item, normalized, now)
            item["status"] = "resolved"
            item["resolved_at"] = now.isoformat()
            self._append_history(item)
            return True

        if not relevant or normalized["importance"] < 1:
            return False

        if index is None:
            item = self._new_event(normalized, now)
            self._events.append(item)
        else:
            item = self._events[index]
            self._merge_event(item, normalized, now)

        self._trim_events()
        return True

    def _find_event_index(
        self,
        normalized: dict[str, Any],
    ) -> int | None:
        event_key = normalized["event_key"]
        link = normalized.get("link")
        for index, item in enumerate(self._events):
            if item.get("event_key") == event_key:
                return index
            if link and item.get("link") == link:
                return index
        return None

    def _new_event(
        self,
        normalized: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        expires_at, validity_source = _expiry_for_event(normalized, now)
        source_identity = normalized["source_identity"]
        return {
            **normalized,
            "status": "active",
            "first_seen": now.isoformat(),
            "last_seen": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "validity_source": validity_source,
            "stale_since": "",
            "resolved_at": "",
            "sources": [
                {
                    "name": normalized["source_name"],
                    "identity": source_identity,
                    "class": normalized["source_class"],
                    "tier": normalized["source_tier"],
                    "feed_url": normalized["feed_url"],
                    "link": normalized["link"],
                }
            ],
            "corroboration_count": 1,
        }

    def _merge_event(
        self,
        item: dict[str, Any],
        normalized: dict[str, Any],
        now: datetime,
    ) -> None:
        old_importance = _as_int(item.get("importance"), 0, 0, 3)
        new_importance = _as_int(
            normalized.get("importance"), 0, 0, 3
        )

        # Keep an earlier explicit event date when an update does not repeat it.
        old_event_start_at = item.get("event_start_at", "")
        old_valid_until = item.get("valid_until", "")
        old_original_title = item.get("original_title", "")
        old_event_timing_text = item.get("event_timing_text", "")
        old_link = item.get("link", "")
        if not normalized.get("event_start_at") and old_event_start_at:
            normalized["event_start_at"] = old_event_start_at
        if not normalized.get("valid_until") and old_valid_until:
            normalized["valid_until"] = old_valid_until
        if not normalized.get("original_title") and old_original_title:
            normalized["original_title"] = old_original_title
        if not normalized.get("event_timing_text") and old_event_timing_text:
            normalized["event_timing_text"] = old_event_timing_text
        if not normalized.get("link") and old_link:
            normalized["link"] = old_link

        # Keep the highest observed importance until an explicit resolution.
        item.update(normalized)
        item["importance"] = max(old_importance, new_importance)
        item["status"] = "active"
        item["last_seen"] = now.isoformat()
        item["stale_since"] = ""
        item["resolved_at"] = ""

        expires_at, validity_source = _expiry_for_event(item, now)
        item["expires_at"] = expires_at.isoformat()
        item["validity_source"] = validity_source

        sources = item.get("sources")
        if not isinstance(sources, list):
            sources = []

        source_identity = normalized["source_identity"]
        if not any(
            isinstance(source, dict)
            and source.get("identity") == source_identity
            for source in sources
        ):
            sources.append(
                {
                    "name": normalized["source_name"],
                    "identity": source_identity,
                    "class": normalized["source_class"],
                    "tier": normalized["source_tier"],
                    "feed_url": normalized["feed_url"],
                    "link": normalized["link"],
                }
            )

        item["sources"] = sources[-8:]
        item["corroboration_count"] = len(item["sources"])

        bonus = min(
            10,
            max(0, len(item["sources"]) - 1) * 5,
        )
        source_confidence = max(
            [
                _SOURCE_CONFIDENCE.get(
                    str(source.get("class")),
                    60,
                )
                for source in item["sources"]
                if isinstance(source, dict)
            ]
            or [60]
        )
        analysis_confidence = _as_int(
            item.get("analysis_confidence"), 75, 0, 100
        )
        item["source_confidence"] = source_confidence
        item["confidence_score"] = min(
            100,
            round(
                (source_confidence * 0.7)
                + (analysis_confidence * 0.3)
            )
            + bonus,
        )

    def _sweep(self, now: datetime) -> bool:
        changed = False
        kept: list[dict[str, Any]] = []

        for item in self._events:
            status = str(item.get("status", "active"))
            expires_at = _parse_dt(item.get("expires_at"))

            if (
                status == "active"
                and expires_at is not None
                and now >= expires_at
            ):
                item["status"] = "stale"
                item["stale_since"] = now.isoformat()
                changed = True

            if item.get("status") == "stale":
                stale_since = (
                    _parse_dt(item.get("stale_since"))
                    or expires_at
                    or now
                )
                if now >= stale_since + timedelta(
                    hours=CONTEXT_STALE_GRACE_HOURS
                ):
                    item["status"] = "resolved"
                    item["resolved_at"] = now.isoformat()
                    item["resolution_reason"] = (
                        "expired_after_stale_grace"
                    )
                    self._append_history(item)
                    changed = True
                    continue

            kept.append(item)

        self._events = kept
        if self._trim_events():
            changed = True
        return changed

    def _trim_events(self) -> bool:
        if len(self._events) <= CONTEXT_ACTIVE_LIMIT:
            return False

        self._events.sort(key=_event_sort_key, reverse=True)
        overflow = self._events[CONTEXT_ACTIVE_LIMIT:]
        self._events = self._events[:CONTEXT_ACTIVE_LIMIT]
        now = dt_util.utcnow().isoformat()
        for item in overflow:
            item["status"] = "resolved"
            item["resolved_at"] = now
            item["resolution_reason"] = "event_limit"
            self._append_history(item)
        return True

    def _append_history(self, item: dict[str, Any]) -> None:
        self._history.insert(0, dict(item))
        self._history = self._history[:CONTEXT_HISTORY_LIMIT]

    def _snapshot(self, now: datetime) -> ContextSnapshot:
        active = [
            dict(item)
            for item in self._events
            if item.get("status") == "active"
        ]
        stale = [
            dict(item)
            for item in self._events
            if item.get("status") == "stale"
        ]

        active.sort(key=_event_sort_key, reverse=True)
        stale.sort(key=_event_sort_key, reverse=True)

        top_event = active[0] if active else None
        highest_importance = (
            _as_int(top_event.get("importance"), 0, 0, 3)
            if top_event
            else 0
        )
        highest_confidence = max(
            (
                _as_int(
                    item.get("confidence_score"),
                    0,
                    0,
                    100,
                )
                for item in active
            ),
            default=0,
        )

        if highest_importance >= 3:
            status = "important"
        elif highest_importance == 2:
            status = "watch"
        elif highest_importance == 1:
            status = "information"
        elif stale:
            status = "stale"
        else:
            status = "idle"

        recommended_defcon = 5
        if top_event is not None:
            confidence = _as_int(
                top_event.get("confidence_score"),
                0,
                0,
                100,
            )
            corroboration = _as_int(
                top_event.get("corroboration_count"),
                1,
                1,
                20,
            )
            protective = _as_bool(
                top_event.get("protective_action")
            )
            if highest_importance >= 3:
                recommended_defcon = (
                    3
                    if protective
                    or confidence >= 75
                    or corroboration >= 2
                    else 4
                )
            elif highest_importance == 2:
                recommended_defcon = 4

        return ContextSnapshot(
            status=status,
            active_event_count=len(active),
            stale_event_count=len(stale),
            recommended_defcon=recommended_defcon,
            highest_importance=highest_importance,
            highest_confidence=highest_confidence,
            top_event=top_event,
            active_events=active,
            stale_events=stale,
            recent_events=[
                dict(item) for item in self._history[:10]
            ],
            evaluated_at=now,
        )
