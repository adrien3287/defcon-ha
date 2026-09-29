"""Private GitHub context feed support for DEFCON Home."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTEXT_ENABLED,
    CONF_GITHUB_OWNER,
    CONF_GITHUB_PATH,
    CONF_GITHUB_REPO,
    CONF_GITHUB_TOKEN,
    DEFAULT_CONTEXT_ENABLED,
    DEFAULT_GITHUB_OWNER,
    DEFAULT_GITHUB_PATH,
    DEFAULT_GITHUB_REPO,
)


@dataclass(slots=True)
class ContextFeed:
    """Normalized external context feed."""

    level: int | None
    summary: str
    reasons: list[dict[str, Any]]
    weak_signals: list[dict[str, Any]]
    generated_at: datetime | None
    valid_until: datetime | None
    status: str
    error: str = ""
    report_markdown: str = ""

    @property
    def is_fresh(self) -> bool:
        """Return whether this feed may influence the final level."""
        if self.status != "fresh" or self.level is None or self.valid_until is None:
            return False
        return self.valid_until > dt_util.utcnow()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def _safe_level(value: Any) -> int | None:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    return level if 1 <= level <= 5 else None


def _normalize_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


async def async_fetch_context_feed(
    hass: HomeAssistant, settings: dict[str, Any]
) -> ContextFeed:
    """Fetch and normalize the private GitHub JSON feed."""
    if not settings.get(CONF_CONTEXT_ENABLED, DEFAULT_CONTEXT_ENABLED):
        return ContextFeed(
            level=None,
            summary="Flux contextuel désactivé",
            reasons=[],
            weak_signals=[],
            generated_at=None,
            valid_until=None,
            status="disabled",
            report_markdown="",
        )

    owner = str(settings.get(CONF_GITHUB_OWNER, DEFAULT_GITHUB_OWNER)).strip()
    repo = str(settings.get(CONF_GITHUB_REPO, DEFAULT_GITHUB_REPO)).strip()
    path = str(settings.get(CONF_GITHUB_PATH, DEFAULT_GITHUB_PATH)).strip().lstrip("/")
    token = str(settings.get(CONF_GITHUB_TOKEN, "")).strip()

    if not owner or not repo or not path:
        return ContextFeed(
            level=None,
            summary="Flux contextuel non configuré",
            reasons=[],
            weak_signals=[],
            generated_at=None,
            valid_until=None,
            status="error",
            error="missing_repository_configuration",
            report_markdown="",
        )

    url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/"
        f"{quote(repo, safe='')}/contents/{quote(path, safe='/')}"
    )
    headers = {
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DEFCON-Home",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(15):
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    raise ValueError("feed_not_found_or_repository_not_authorized")
                if response.status in (401, 403):
                    raise ValueError("github_authentication_or_permission_failed")
                response.raise_for_status()
                raw = await response.text()
    except (TimeoutError, ClientError, ValueError) as err:
        return ContextFeed(
            level=None,
            summary="Flux contextuel indisponible",
            reasons=[],
            weak_signals=[],
            generated_at=None,
            valid_until=None,
            status="error",
            error=str(err),
            report_markdown="",
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ContextFeed(
            level=None,
            summary="Le flux contextuel contient un JSON invalide",
            reasons=[],
            weak_signals=[],
            generated_at=None,
            valid_until=None,
            status="error",
            error="invalid_json",
            report_markdown="",
        )

    if not isinstance(payload, dict):
        return ContextFeed(
            level=None,
            summary="Le flux contextuel contient un objet racine invalide",
            reasons=[],
            weak_signals=[],
            generated_at=None,
            valid_until=None,
            status="error",
            error="invalid_root",
            report_markdown="",
        )

    level = _safe_level(payload.get("context_defcon", payload.get("defcon")))
    generated_at = _parse_datetime(payload.get("generated_at", payload.get("updated_at")))
    valid_until = _parse_datetime(payload.get("valid_until"))
    summary = str(payload.get("summary", "")).strip()
    reasons = _normalize_list(payload.get("reasons"))
    weak_signals = _normalize_list(payload.get("weak_signals"))
    report_markdown = str(payload.get("report_markdown", "")).strip()

    if level is None or valid_until is None:
        return ContextFeed(
            level=level,
            summary=summary or "Flux contextuel incomplet",
            reasons=reasons,
            weak_signals=weak_signals,
            generated_at=generated_at,
            valid_until=valid_until,
            status="error",
            error="missing_or_invalid_level_or_valid_until",
            report_markdown=report_markdown,
        )

    status = "fresh" if valid_until > dt_util.utcnow() else "stale"
    return ContextFeed(
        level=level,
        summary=summary,
        reasons=reasons,
        weak_signals=weak_signals,
        generated_at=generated_at,
        valid_until=valid_until,
        status=status,
        error="" if status == "fresh" else "feed_expired",
        report_markdown=report_markdown,
    )
