"""Internal Harburg Aktuell web source.

The redesigned Harburg Aktuell site no longer exposes a valid RSS feed that
Home Assistant Feedreader can configure reliably. This helper polls the public
homepage, discovers new article URLs and emits normal feedreader events so the
existing Lagezentrum Gemini automation can process them unchanged.

This source is context-only. It never affects the deterministic DEFCON engine.
"""

from __future__ import annotations

from collections import deque
from datetime import timedelta
from html import unescape
from html.parser import HTMLParser
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HARBURG_HOME_URL = "https://harburg-aktuell.de/"
HARBURG_SOURCE_NAME = "Harburg Aktuell"
HARBURG_POLL_MINUTES = 5
HARBURG_INITIAL_ARTICLE_LIMIT = 20
HARBURG_SEEN_LIMIT = 250
HARBURG_STORAGE_VERSION = 1

_ARTICLE_PATH_RE = re.compile(r"/[^?#]+-\d+/?$")
_DATE_RE = re.compile(
    r"\b(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonnabend|Sonntag),?\s+"
    r"\d{1,2}\.\s+[A-Za-zÄÖÜäöüß]+\s+20\d{2},\s+\d{1,2}:\d{2}\b"
)
_SPACE_RE = re.compile(r"\s+")


def _clean_text(value: str, limit: int = 4000) -> str:
    text = unescape(_SPACE_RE.sub(" ", value or "")).strip()
    return text[:limit]


def _is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in {"harburg-aktuell.de", "www.harburg-aktuell.de"}:
        return False
    return bool(_ARTICLE_PATH_RE.search(parsed.path))


class _HomepageParser(HTMLParser):
    """Extract article links and visible titles from the Harburg homepage."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._parts: list[str] = []
        self.items: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if not href:
            return
        absolute = urljoin(HARBURG_HOME_URL, href)
        if _is_article_url(absolute):
            self._href = absolute
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        title = _clean_text(" ".join(self._parts), 500)
        if len(title) >= 8:
            self.items.append((self._href, title))
        self._href = None
        self._parts = []


class _ArticleParser(HTMLParser):
    """Extract a title and the first useful paragraphs from one article page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_h1 = False
        self._after_h1 = False
        self._in_p = False
        self._h1_parts: list[str] = []
        self._p_parts: list[str] = []
        self.title = ""
        self.paragraphs: list[str] = []
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "h1" and not self.title:
            self._in_h1 = True
            self._h1_parts = []
        elif tag == "p" and self._after_h1 and len(self.paragraphs) < 10:
            self._in_p = True
            self._p_parts = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.all_text.append(text)
        if self._in_h1:
            self._h1_parts.append(data)
        elif self._in_p:
            self._p_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.title = _clean_text(" ".join(self._h1_parts), 500)
            self._after_h1 = True
        elif tag == "p" and self._in_p:
            self._in_p = False
            paragraph = _clean_text(" ".join(self._p_parts), 1500)
            if len(paragraph) >= 40 and "Werbung" not in paragraph:
                self.paragraphs.append(paragraph)


class HarburgAktuellSource:
    """Poll Harburg Aktuell and republish new items through the feedreader bus event."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._session = async_get_clientsession(hass)
        self._remove_interval = None
        self._refreshing = False
        self._seen: deque[str] = deque(maxlen=HARBURG_SEEN_LIMIT)
        self._store: Store[list[str]] = Store(
            hass,
            HARBURG_STORAGE_VERSION,
            f"{DOMAIN}.harburg_aktuell.{entry.entry_id}",
        )

    @callback
    def async_start(self) -> None:
        """Start polling without blocking integration startup."""
        if self._remove_interval is not None:
            return
        self._remove_interval = async_track_time_interval(
            self.hass,
            self._async_interval,
            timedelta(minutes=HARBURG_POLL_MINUTES),
        )
        self.entry.async_create_task(
            self.hass,
            self.async_refresh(),
            "DEFCON Home Harburg Aktuell initial refresh",
        )

    @callback
    def async_stop(self) -> None:
        """Stop periodic polling."""
        if self._remove_interval is not None:
            self._remove_interval()
            self._remove_interval = None

    async def _async_interval(self, _now: Any) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Fetch the homepage and emit feedreader events for newly found articles."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if not self._seen:
                stored = await self._store.async_load()
                if stored:
                    self._seen.extend(str(item) for item in stored[-HARBURG_SEEN_LIMIT:])

            html = await self._fetch_text(HARBURG_HOME_URL)
            if not html:
                return

            parser = _HomepageParser()
            parser.feed(html)

            unique: list[tuple[str, str]] = []
            discovered: set[str] = set()
            for link, title in parser.items:
                if link in discovered:
                    continue
                discovered.add(link)
                unique.append((link, title))

            if not unique:
                _LOGGER.warning("Harburg Aktuell page contained no discoverable article links")
                return

            seen_set = set(self._seen)
            if seen_set:
                candidates = [item for item in unique if item[0] not in seen_set]
            else:
                candidates = unique[:HARBURG_INITIAL_ARTICLE_LIMIT]

            for link, _title in reversed(unique):
                if link not in seen_set:
                    self._seen.append(link)
                    seen_set.add(link)

            await self._store.async_save(list(self._seen))

            for link, homepage_title in reversed(candidates[:HARBURG_INITIAL_ARTICLE_LIMIT]):
                event_data = await self._article_event(link, homepage_title)
                self.hass.bus.async_fire("feedreader", event_data)

            if candidates:
                _LOGGER.debug(
                    "Harburg Aktuell emitted %d new article(s)",
                    len(candidates[:HARBURG_INITIAL_ARTICLE_LIMIT]),
                )
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning("Unable to refresh Harburg Aktuell: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected Harburg Aktuell refresh failure")
        finally:
            self._refreshing = False

    async def _fetch_text(self, url: str) -> str:
        try:
            async with self._session.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; DEFCON-Home/0.4.6; "
                        "+https://github.com/adrien3287/defcon-ha)"
                    )
                },
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                response.raise_for_status()
                return await response.text(errors="ignore")
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Harburg Aktuell fetch failed for %s: %s", url, err)
            return ""

    async def _article_event(self, link: str, homepage_title: str) -> dict[str, Any]:
        article_html = await self._fetch_text(link)
        title = homepage_title
        description = ""
        content = ""
        published = ""

        if article_html:
            parser = _ArticleParser()
            parser.feed(article_html)
            if parser.title:
                title = parser.title
            useful = [
                paragraph
                for paragraph in parser.paragraphs
                if "WhatsApp-Newsticker" not in paragraph
                and "Melde dich jetzt" not in paragraph
            ]
            if useful:
                description = useful[0][:700]
                content = " ".join(useful[:8])[:4000]
            full_text = _clean_text(" ".join(parser.all_text), 12000)
            match = _DATE_RE.search(full_text)
            if match:
                published = match.group(0)

        return {
            "title": title,
            "description": description,
            "content": content,
            "link": link,
            "feed_url": HARBURG_HOME_URL,
            "published": published,
            "source": HARBURG_SOURCE_NAME,
        }
