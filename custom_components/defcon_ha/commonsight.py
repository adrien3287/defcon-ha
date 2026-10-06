"""CommonSight integration for DEFCON Home.

CommonSight is treated as a secondary, structured situation-picture source.
It never changes the deterministic DEFCON level directly. Abnormal nearby
items are fed into the contextual event engine and layer freshness/errors are
exposed independently so "no alert" is never confused with "no data".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import math
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    COMMONSIGHT_MAX_RESPONSE_BYTES,
    COMMONSIGHT_REFRESH_MINUTES,
    COMMONSIGHT_REQUEST_TIMEOUT_SECONDS,
    CONF_COMMONSIGHT_BASE_URL,
    CONF_COMMONSIGHT_ENABLED,
    CONF_COMMONSIGHT_HOME_REGION,
    CONF_COMMONSIGHT_LAYERS,
    CONF_COMMONSIGHT_RADIUS_KM,
    CONF_COMMONSIGHT_SCOPE,
    DEFAULT_COMMONSIGHT_BASE_URL,
    DEFAULT_COMMONSIGHT_ENABLED,
    DEFAULT_COMMONSIGHT_HOME_REGION,
    DEFAULT_COMMONSIGHT_LAYERS,
    DEFAULT_COMMONSIGHT_RADIUS_KM,
    DEFAULT_COMMONSIGHT_SCOPE,
    DOMAIN,
)
from .context import ContextCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CommonSightSnapshot:
    """Current CommonSight integration state."""

    enabled: bool
    health: str
    layer_health: dict[str, dict[str, Any]]
    degraded_layers: list[str]
    partial_layers: list[str]
    versions: dict[str, str]
    nearby_event_count: int
    checked_at: datetime
    last_success: datetime | None
    last_error: str
    base_url: str
    scope: str
    home_region: str
    radius_km: float


class CommonSightCoordinator(DataUpdateCoordinator[CommonSightSnapshot]):
    """Poll CommonSight status/snapshots and feed abnormal items to context."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ContextCoordinator,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_commonsight",
            update_interval=timedelta(minutes=COMMONSIGHT_REFRESH_MINUTES),
        )
        self.entry = entry
        self.context = context
        self._session = async_get_clientsession(hass)
        self._versions: dict[str, str] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._last_success: datetime | None = None

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.get(
                CONF_COMMONSIGHT_ENABLED,
                DEFAULT_COMMONSIGHT_ENABLED,
            )
        )

    @property
    def base_url(self) -> str:
        value = str(
            self.settings.get(
                CONF_COMMONSIGHT_BASE_URL,
                DEFAULT_COMMONSIGHT_BASE_URL,
            )
        ).strip()
        return value.rstrip("/")

    @property
    def scope(self) -> str:
        value = str(
            self.settings.get(
                CONF_COMMONSIGHT_SCOPE,
                DEFAULT_COMMONSIGHT_SCOPE,
            )
        ).strip().upper()
        return value if value in {"DE", "AT", "CH"} else DEFAULT_COMMONSIGHT_SCOPE

    @property
    def home_region(self) -> str:
        value = str(
            self.settings.get(
                CONF_COMMONSIGHT_HOME_REGION,
                DEFAULT_COMMONSIGHT_HOME_REGION,
            )
        ).strip().upper()
        return value or DEFAULT_COMMONSIGHT_HOME_REGION

    @property
    def radius_km(self) -> float:
        try:
            value = float(
                self.settings.get(
                    CONF_COMMONSIGHT_RADIUS_KM,
                    DEFAULT_COMMONSIGHT_RADIUS_KM,
                )
            )
        except (TypeError, ValueError):
            return float(DEFAULT_COMMONSIGHT_RADIUS_KM)
        return max(1.0, min(300.0, value))

    @property
    def layers(self) -> list[str]:
        value = self.settings.get(
            CONF_COMMONSIGHT_LAYERS,
            DEFAULT_COMMONSIGHT_LAYERS,
        )
        if not isinstance(value, (list, tuple)):
            return list(DEFAULT_COMMONSIGHT_LAYERS)
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))

    async def _async_update_data(self) -> CommonSightSnapshot:
        now = dt_util.utcnow()
        if not self.enabled:
            return CommonSightSnapshot(
                enabled=False,
                health="disabled",
                layer_health={},
                degraded_layers=[],
                partial_layers=[],
                versions=dict(self._versions),
                nearby_event_count=0,
                checked_at=now,
                last_success=self._last_success,
                last_error="",
                base_url=self.base_url,
                scope=self.scope,
                home_region=self.home_region,
                radius_km=self.radius_km,
            )

        base_url = self.base_url
        if not self._valid_base_url(base_url):
            return self._error_snapshot(
                now,
                f"Invalid CommonSight base URL: {base_url!r}",
            )

        try:
            status_payload = await self._async_get_json(
                f"{base_url}/api/status.php?scope={self.scope}"
            )
        except (ClientError, TimeoutError, ValueError, TypeError) as err:
            _LOGGER.warning("CommonSight status request failed: %s", err)
            return self._error_snapshot(now, str(err))

        if not isinstance(status_payload, dict):
            return self._error_snapshot(now, "CommonSight status payload is not an object")

        status_layers = status_payload.get("layers")
        if not isinstance(status_layers, dict):
            return self._error_snapshot(now, "CommonSight status payload has no layers object")

        layer_health: dict[str, dict[str, Any]] = {}
        degraded_layers: list[str] = []
        partial_layers: list[str] = []
        nearby_event_count = 0

        for layer in self.layers:
            meta = status_layers.get(layer)
            if not isinstance(meta, dict):
                layer_health[layer] = {
                    "status": "pending",
                    "stale": True,
                    "snapshot_ok": False,
                    "issue": "layer_missing_from_status",
                }
                degraded_layers.append(layer)
                continue

            status = str(meta.get("status", "pending"))
            stale = bool(meta.get("stale", False))
            version = str(meta.get("version") or "")
            relative_url = str(meta.get("url") or "")
            issues = meta.get("issues") if isinstance(meta.get("issues"), list) else []

            health = {
                "status": status,
                "stale": stale,
                "snapshot_ok": False,
                "version": version,
                "checked_at": meta.get("checkedAt"),
                "generated_at": meta.get("generatedAt"),
                "source_updated_at": meta.get("sourceUpdatedAt"),
                "item_count": meta.get("itemCount", 0),
                "issues": issues,
                "last_error": meta.get("lastError"),
            }

            if status == "partial":
                partial_layers.append(layer)
            if status in {"error", "setup", "pending"} or stale:
                degraded_layers.append(layer)

            snapshot: dict[str, Any] | None = None
            snapshot_fresh_for_reconcile = False

            if version and relative_url and status not in {"setup", "pending"}:
                cached_version = self._versions.get(layer)
                snapshot = self._snapshots.get(layer)

                if cached_version != version or snapshot is None:
                    try:
                        snapshot_url = self._snapshot_url(base_url, relative_url)
                        candidate = await self._async_get_json(snapshot_url)
                        if not isinstance(candidate, dict):
                            raise ValueError("snapshot payload is not an object")
                        snapshot = candidate
                        self._snapshots[layer] = candidate
                        self._versions[layer] = version
                    except (ClientError, TimeoutError, ValueError, TypeError) as err:
                        health["snapshot_error"] = str(err)
                        if layer not in degraded_layers:
                            degraded_layers.append(layer)
                        _LOGGER.warning(
                            "CommonSight snapshot %s (%s) failed: %s",
                            layer,
                            version,
                            err,
                        )
                        snapshot = None
                else:
                    snapshot_fresh_for_reconcile = True

                if snapshot is not None:
                    health["snapshot_ok"] = True
                    snapshot_fresh_for_reconcile = True
                    events = self._events_from_snapshot(layer, snapshot)
                    nearby_event_count += len(events)

                    if snapshot_fresh_for_reconcile:
                        await self.context.async_sync_source(
                            f"commonsight:{layer}",
                            events,
                            now=now,
                        )

            layer_health[layer] = health

        if degraded_layers:
            overall = "degraded"
        elif partial_layers:
            overall = "partial"
        else:
            overall = "ok"

        self._last_success = now
        return CommonSightSnapshot(
            enabled=True,
            health=overall,
            layer_health=layer_health,
            degraded_layers=list(dict.fromkeys(degraded_layers)),
            partial_layers=list(dict.fromkeys(partial_layers)),
            versions=dict(self._versions),
            nearby_event_count=nearby_event_count,
            checked_at=now,
            last_success=self._last_success,
            last_error="",
            base_url=base_url,
            scope=self.scope,
            home_region=self.home_region,
            radius_km=self.radius_km,
        )

    def _error_snapshot(self, now: datetime, error: str) -> CommonSightSnapshot:
        return CommonSightSnapshot(
            enabled=True,
            health="error",
            layer_health={},
            degraded_layers=list(self.layers),
            partial_layers=[],
            versions=dict(self._versions),
            nearby_event_count=0,
            checked_at=now,
            last_success=self._last_success,
            last_error=error[:500],
            base_url=self.base_url,
            scope=self.scope,
            home_region=self.home_region,
            radius_km=self.radius_km,
        )

    async def _async_get_json(self, url: str) -> Any:
        timeout = ClientTimeout(total=COMMONSIGHT_REQUEST_TIMEOUT_SECONDS)
        async with self._session.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "DEFCON-Home/CommonSight",
            },
            timeout=timeout,
            allow_redirects=False,
        ) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"HTTP {response.status} for {url}")
            if (
                response.content_length is not None
                and response.content_length > COMMONSIGHT_MAX_RESPONSE_BYTES
            ):
                raise ValueError(
                    f"CommonSight response too large: {response.content_length} bytes"
                )
            raw = await response.read()
            if len(raw) > COMMONSIGHT_MAX_RESPONSE_BYTES:
                raise ValueError(f"CommonSight response too large: {len(raw)} bytes")
            return json.loads(raw)

    @staticmethod
    def _valid_base_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.netloc)

    @staticmethod
    def _snapshot_url(base_url: str, relative_url: str) -> str:
        base = urlparse(base_url)
        candidate = urlparse(relative_url)

        if candidate.scheme or candidate.netloc:
            if candidate.scheme != "https" or candidate.netloc != base.netloc:
                raise ValueError("CommonSight snapshot URL points outside configured origin")
            return relative_url

        url = urljoin(base_url.rstrip("/") + "/", relative_url.lstrip("/"))
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != base.netloc:
            raise ValueError("CommonSight snapshot URL points outside configured origin")
        return url

    def _events_from_snapshot(
        self,
        layer: str,
        snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        items = snapshot.get("items")
        if not isinstance(items, list):
            return []

        events: list[dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            event: dict[str, Any] | None
            if layer == "warnings":
                event = self._warning_event(raw)
            elif layer in {"water", "radiation"}:
                event = self._measurement_event(layer, raw)
            elif layer == "traffic":
                event = self._traffic_event(raw)
            elif layer == "nature":
                event = self._earthquake_event(raw)
            elif layer == "space":
                event = self._space_event(raw)
            else:
                # news/weather/air remain available through CommonSight health,
                # but are not injected to avoid duplicating the existing RSS and
                # deterministic Home Assistant pipelines.
                event = None

            if event is not None:
                events.append(event)
        return events

    def _base_event(
        self,
        layer: str,
        item: dict[str, Any],
        *,
        category: str,
        importance: int,
        direct_relevance: str,
        source_tier: str,
        summary: str,
        affected_area: str,
        protective_action: bool = False,
        valid_until: Any = "",
        event_start_at: Any = "",
    ) -> dict[str, Any]:
        item_id = str(item.get("id") or "")
        source = str(item.get("source") or "CommonSight")
        title = str(item.get("title") or item_id or layer)
        link = str(item.get("url") or "")
        return {
            "relevant": True,
            "lifecycle": "update",
            "event_key": f"commonsight-{layer}-{item_id or self._fallback_item_key(item)}",
            "source_system": f"commonsight:{layer}",
            "title": title,
            "original_title": title,
            "summary_fr": summary,
            "reason": (
                "Signal structuré CommonSight. Validation secondaire; "
                "les sources officielles directes restent prioritaires."
            ),
            "recommended_action": "Vérifier la source officielle liée à l'événement.",
            "category": category,
            "scope": self.scope.lower(),
            "affected_area": affected_area,
            "direct_relevance": direct_relevance,
            "protective_action": protective_action,
            "importance": max(1, min(3, importance)),
            "source_name": f"CommonSight · {source}",
            "source_tier": source_tier,
            "source_class": "aggregator",
            "feed_url": self.base_url,
            "link": link,
            "analysis_confidence": 95,
            "published_at": item.get("time") or "",
            "event_start_at": event_start_at or item.get("time") or "",
            "valid_until": valid_until or "",
        }

    def _warning_event(self, item: dict[str, Any]) -> dict[str, Any] | None:
        geo = self._geo(item)
        if not geo["include"]:
            return None

        severity = str(item.get("severity") or "unknown").lower()
        importance = {
            "extreme": 3,
            "severe": 3,
            "moderate": 2,
            "minor": 1,
            "unknown": 1,
        }.get(severity, 1)
        if geo["distance_km"] is not None and geo["distance_km"] > 25 and importance > 1:
            importance -= 1

        raw_category = str(item.get("category") or "").lower()
        category = {
            "weather": "weather",
            "flood": "water",
            "police": "security",
            "civilprotection": "security",
        }.get(raw_category, "security")

        sections = item.get("sections")
        section_texts: list[str] = []
        if isinstance(sections, list):
            for section in sections[:3]:
                if isinstance(section, dict):
                    text = str(section.get("text") or "").strip()
                    if text:
                        section_texts.append(text)

        area = str(item.get("area") or "").strip()
        summary_parts = [
            f"Sévérité CommonSight: {severity}.",
            f"Zone: {area}." if area else "",
            " ".join(section_texts),
            self._distance_text(geo),
        ]

        return self._base_event(
            "warnings",
            item,
            category=category,
            importance=importance,
            direct_relevance=geo["relevance"],
            source_tier="local" if geo["relevance"] == "direct" else "national",
            summary=" ".join(part for part in summary_parts if part).strip(),
            affected_area=area or str(item.get("title") or ""),
            protective_action=severity in {"extreme", "severe"}
            and raw_category in {"civilprotection", "police", "flood"},
            valid_until=item.get("expires") or "",
            event_start_at=item.get("onset") or item.get("time") or "",
        )

    def _measurement_event(
        self,
        layer: str,
        item: dict[str, Any],
    ) -> dict[str, Any] | None:
        geo = self._geo(item)
        if not geo["include"]:
            return None

        assessment = item.get("assessment")
        if not isinstance(assessment, dict):
            return None
        level = str(assessment.get("level") or "unknown").lower()
        if level not in {"elevated", "high"}:
            return None

        importance = 3 if level == "high" else 2
        if geo["distance_km"] is not None and geo["distance_km"] > 25 and importance > 1:
            importance -= 1

        value = item.get("value")
        unit = str(item.get("unit") or "")
        source_value = str(assessment.get("sourceValue") or "")
        summary = (
            f"{item.get('title') or layer}: {value} {unit}; "
            f"évaluation CommonSight={level}."
        )
        if source_value:
            summary += f" Source: {source_value}."
        distance = self._distance_text(geo)
        if distance:
            summary += f" {distance}"

        return self._base_event(
            layer,
            item,
            category="water" if layer == "water" else "radiation",
            importance=importance,
            direct_relevance=geo["relevance"],
            source_tier="local",
            summary=summary,
            affected_area=str(item.get("title") or ""),
            valid_until=assessment.get("validUntil") or "",
            event_start_at=item.get("time") or "",
        )

    def _traffic_event(self, item: dict[str, Any]) -> dict[str, Any] | None:
        geo = self._geo(item)
        if not geo["include"]:
            return None

        distance = geo["distance_km"]
        category = str(item.get("category") or "").lower()
        notice_type = str(item.get("noticeType") or "")
        important_category = category in {"closure", "accident", "hazard", "danger"}
        jam = category == "jam"

        if jam and (distance is None or distance > 25):
            return None
        if category in {"roadworks", "construction"} and (distance is None or distance > 10):
            return None
        if not important_category and not jam and category not in {"roadworks", "construction"}:
            return None

        importance = 2 if important_category and (distance is None or distance <= 25) else 1
        description = str(item.get("description") or "")
        road = str(item.get("road") or "")
        summary = " · ".join(part for part in (road, notice_type, description) if part)
        distance_text = self._distance_text(geo)
        if distance_text:
            summary = f"{summary} {distance_text}".strip()

        return self._base_event(
            "traffic",
            item,
            category="transport",
            importance=importance,
            direct_relevance=geo["relevance"],
            source_tier="local",
            summary=summary,
            affected_area=road or str(item.get("title") or ""),
            event_start_at=item.get("start") or item.get("time") or "",
        )

    def _earthquake_event(self, item: dict[str, Any]) -> dict[str, Any] | None:
        geo = self._geo(item)
        if not geo["include"]:
            return None
        try:
            magnitude = float(item.get("magnitude"))
        except (TypeError, ValueError):
            return None
        if magnitude < 2.0:
            return None

        importance = 3 if magnitude >= 5 else 2 if magnitude >= 3 else 1
        summary = (
            f"Séisme M{magnitude:.1f}, profondeur {item.get('depthKm', '?')} km. "
            f"{self._distance_text(geo)}"
        ).strip()

        return self._base_event(
            "nature",
            item,
            category="geological",
            importance=importance,
            direct_relevance=geo["relevance"],
            source_tier="national",
            summary=summary,
            affected_area=str(item.get("place") or item.get("title") or ""),
            event_start_at=item.get("time") or "",
        )

    def _space_event(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = str(item.get("title") or "").upper()
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            return None

        importance: int | None = None
        if title == "KP":
            if value >= 8:
                importance = 3
            elif value >= 7:
                importance = 2
            elif value >= 5:
                importance = 1
        elif title in {"G", "R", "S"}:
            if value >= 4:
                importance = 3
            elif value >= 3:
                importance = 2
            elif value >= 1:
                importance = 1

        if importance is None:
            return None

        return self._base_event(
            "space",
            item,
            category="space_weather",
            importance=importance,
            direct_relevance="potential",
            source_tier="strategic",
            summary=f"Indice NOAA {title}={value:g} via CommonSight.",
            affected_area="global",
            event_start_at=item.get("time") or "",
        )

    def _geo(self, item: dict[str, Any]) -> dict[str, Any]:
        distance = self._item_distance_km(item)
        if distance is not None:
            include = distance <= self.radius_km
            if distance <= 10:
                relevance = "direct"
                band = "0-10 km"
            elif distance <= 25:
                relevance = "direct"
                band = "10-25 km"
            else:
                relevance = "potential"
                band = f"25-{self.radius_km:g} km"
            return {
                "include": include,
                "distance_km": distance,
                "relevance": relevance,
                "band": band,
            }

        region_ids = item.get("regionIds")
        if isinstance(region_ids, list) and self.home_region in {
            str(value).upper() for value in region_ids
        }:
            return {
                "include": True,
                "distance_km": None,
                "relevance": "potential",
                "band": self.home_region,
            }

        return {
            "include": False,
            "distance_km": None,
            "relevance": "none",
            "band": "",
        }

    def _item_distance_km(self, item: dict[str, Any]) -> float | None:
        lat = self._float(item.get("lat"))
        lon = self._float(item.get("lon"))
        if lat is not None and lon is not None:
            return self._haversine_km(
                self.hass.config.latitude,
                self.hass.config.longitude,
                lat,
                lon,
            )

        geometry = item.get("geometry")
        if isinstance(geometry, dict):
            return self._geometry_distance_km(geometry)
        return None

    def _geometry_distance_km(self, geometry: dict[str, Any]) -> float | None:
        coords = geometry.get("coordinates")
        if coords is None:
            return None

        geometry_type = str(geometry.get("type") or "")
        if geometry_type == "Polygon" and isinstance(coords, list) and coords:
            ring = coords[0]
            if isinstance(ring, list) and self._point_in_ring(
                self.hass.config.longitude,
                self.hass.config.latitude,
                ring,
            ):
                return 0.0
        elif geometry_type == "MultiPolygon" and isinstance(coords, list):
            for polygon in coords:
                if (
                    isinstance(polygon, list)
                    and polygon
                    and isinstance(polygon[0], list)
                    and self._point_in_ring(
                        self.hass.config.longitude,
                        self.hass.config.latitude,
                        polygon[0],
                    )
                ):
                    return 0.0

        points = list(self._iter_lon_lat(coords))
        if not points:
            return None
        return min(
            self._haversine_km(
                self.hass.config.latitude,
                self.hass.config.longitude,
                lat,
                lon,
            )
            for lon, lat in points
        )

    @classmethod
    def _iter_lon_lat(cls, value: Any) -> Iterable[tuple[float, float]]:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            yield float(value[0]), float(value[1])
            return
        if isinstance(value, list):
            for child in value:
                yield from cls._iter_lon_lat(child)

    @staticmethod
    def _point_in_ring(lon: float, lat: float, ring: list[Any]) -> bool:
        points = [
            (float(point[0]), float(point[1]))
            for point in ring
            if isinstance(point, list)
            and len(point) >= 2
            and isinstance(point[0], (int, float))
            and isinstance(point[1], (int, float))
        ]
        if len(points) < 3:
            return False

        inside = False
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            crosses = (yi > lat) != (yj > lat)
            if crosses:
                x_intersection = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
                if lon < x_intersection:
                    inside = not inside
            j = i
        return inside

    @staticmethod
    def _haversine_km(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        radius = 6371.0088
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fallback_item_key(item: dict[str, Any]) -> str:
        value = "|".join(
            (
                str(item.get("kind") or ""),
                str(item.get("title") or ""),
                str(item.get("time") or ""),
            )
        )
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _distance_text(geo: dict[str, Any]) -> str:
        distance = geo.get("distance_km")
        if isinstance(distance, (int, float)):
            return f"Distance domicile: {distance:.1f} km ({geo.get('band', '')})."
        band = str(geo.get("band") or "")
        return f"Zone: {band}." if band else ""
