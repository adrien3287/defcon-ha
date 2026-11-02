"""Family DEFCON grid for qualified and independent RSS phenomena.

Only active, credible, individually corroborated events count. Duplicated
reports of the same phenomenon count once, and unclassified historic news
remains informational until re-analysed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

_SIGNAL_CLASSES = {"signal_faible", "signal_serieux"}
_PRIMARY_SOURCES = {"official", "public_media"}


@dataclass(slots=True)
class SignalAssessment:
    level: int
    weak_count: int
    serious_count: int
    counted_signals: list[dict[str, Any]]
    excluded_count: int


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _true(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1", "yes", "on"}


def _is_started(value: Any, now: datetime | None) -> bool:
    if not value or now is None:
        return True
    try:
        start = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if start.tzinfo is None:
            return False
        return start <= now
    except ValueError:
        return False


def assess_context_signals(
    events: Iterable[dict[str, Any]], now: datetime | None = None
) -> SignalAssessment:
    """Compute DEFCON 1–5 using S serious and Y independent weak signals.

    S>=2 or S>=1 and Y>=2 -> 2; S>=1 or Y>=3 -> 3;
    Y>=1 -> 4; otherwise 5. Confirmed urgent local protection -> 1.
    """
    groups: dict[str, dict[str, Any]] = {}
    excluded = 0

    for event in events:
        signal_class = str(event.get("signal_class") or "").strip().lower()
        source_class = str(event.get("source_class") or "other").strip().lower()
        corroboration = _number(event.get("corroboration_count"), 1)
        if (
            event.get("status") != "active"
            or signal_class not in _SIGNAL_CLASSES
            or not _true(event.get("signal_confirmed"))
            or event.get("direct_relevance") not in {"direct", "potential"}
            or _number(event.get("importance")) < 2
            or _number(event.get("analysis_confidence")) < 70
            or _number(event.get("confidence_score")) < 75
            or not _is_started(event.get("event_start_at"), now)
            or (source_class not in _PRIMARY_SOURCES and corroboration < 2)
        ):
            excluded += 1
            continue

        key = str(event.get("phenomenon_key") or event.get("event_key") or "").strip().lower()
        if not key:
            excluded += 1
            continue
        prior = groups.get(key)
        if prior is None or (
            signal_class == "signal_serieux"
            and prior.get("signal_class") != "signal_serieux"
        ):
            groups[key] = event

    counted = sorted(
        groups.values(),
        key=lambda item: str(item.get("phenomenon_key") or item.get("event_key") or ""),
    )
    serious = sum(x.get("signal_class") == "signal_serieux" for x in counted)
    weak = len(counted) - serious
    direct_danger = any(
        x.get("signal_class") == "signal_serieux"
        and x.get("source_class") == "official"
        and x.get("direct_relevance") == "direct"
        and _true(x.get("protective_action"))
        for x in counted
    )

    if direct_danger:
        level = 1
    elif serious >= 2 or (serious >= 1 and weak >= 2):
        level = 2
    elif serious >= 1 or weak >= 3:
        level = 3
    elif weak >= 1:
        level = 4
    else:
        level = 5

    return SignalAssessment(level, weak, serious, counted, excluded)
