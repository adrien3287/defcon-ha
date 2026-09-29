"""Constants for DEFCON Home."""

from __future__ import annotations

DOMAIN = "defcon_ha"
NAME = "DEFCON Home"
VERSION = "0.2.1"

CONF_NINA_ENTITIES = "nina_entities"
CONF_DWD_ENTITIES = "dwd_entities"
CONF_HVV_ENTITIES = "hvv_entities"
CONF_OTHER_ENTITIES = "other_entities"
CONF_MANUAL_OVERRIDE = "manual_override"

CONF_CONTEXT_ENABLED = "context_enabled"
CONF_GITHUB_OWNER = "github_owner"
CONF_GITHUB_REPO = "github_repo"
CONF_GITHUB_PATH = "github_path"
CONF_GITHUB_TOKEN = "github_token"

DEFAULT_NAME = "Home"
DEFAULT_OVERRIDE = "auto"
DEFAULT_CONTEXT_ENABLED = True
DEFAULT_GITHUB_OWNER = "adrien3287"
DEFAULT_GITHUB_REPO = "defcon-json"
DEFAULT_GITHUB_PATH = "status/current.json"

DEFAULT_DWD_ENTITIES = [
    "sensor.hamburg_harburg_niveau_d_alerte_actuel",
    "sensor.hamburg_harburg_niveau_d_alerte_anticipee",
]

DEFAULT_NINA_ENTITIES = [
    "binary_sensor.hamburg_freie_und_hansestadt_warning_1",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_2",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_3",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_4",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_5",
]

CONTEXT_POLL_MINUTES = 5

PLATFORMS = ["sensor", "select", "button"]

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
