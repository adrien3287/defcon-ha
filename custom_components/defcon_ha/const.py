"""Constants for DEFCON Home."""

from __future__ import annotations

DOMAIN = "defcon_ha"
NAME = "DEFCON Home"
VERSION = "0.1.0"

CONF_NINA_ENTITIES = "nina_entities"
CONF_DWD_ENTITIES = "dwd_entities"
CONF_HVV_ENTITIES = "hvv_entities"
CONF_OTHER_ENTITIES = "other_entities"
CONF_MANUAL_OVERRIDE = "manual_override"

DEFAULT_NAME = "Home"
DEFAULT_OVERRIDE = "auto"

PLATFORMS = ["sensor", "select"]

CARD_URL = "/defcon-ha/defcon-ha-card.js"
CARD_FILE = "frontend/defcon-ha-card.js"

LEVEL_NAMES = {
    1: "Critical",
    2: "Severe",
    3: "Alert",
    4: "Watch",
    5: "Normal",
}

LEVEL_COLORS = {
    1: "#6a1b9a",
    2: "#c62828",
    3: "#ef6c00",
    4: "#f9a825",
    5: "#2e7d32",
}

EVENT_LEVEL_CHANGED = "defcon_ha_level_changed"
