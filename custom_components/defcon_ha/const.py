"""Constants for DEFCON Home."""

from __future__ import annotations

DOMAIN = "defcon_ha"
NAME = "DEFCON Home"
VERSION = "0.4.6-beta.1"

CONF_NINA_ENTITIES = "nina_entities"
CONF_DWD_ENTITIES = "dwd_entities"  # legacy v0.2 key
CONF_DWD_CURRENT_ENTITIES = "dwd_current_entities"
CONF_DWD_ADVANCE_ENTITIES = "dwd_advance_entities"
CONF_FLOOD_ENTITIES = "flood_entities"
CONF_PEGEL_STAGE_ENTITIES = "pegel_stage_entities"
CONF_UBA_LQI_ENTITIES = "uba_lqi_entities"
CONF_BFS_ASSESSMENT_ENTITIES = "bfs_assessment_entities"
CONF_LIGHTNING_COUNT_ENTITIES = "lightning_count_entities"
CONF_LIGHTNING_DISTANCE_ENTITIES = "lightning_distance_entities"
CONF_NOAA_ENTITIES = "noaa_entities"

CONF_FIRE_HEAT_ENTITIES = "fire_heat_entities"
CONF_FIRE_SMOKE_ENTITIES = "fire_smoke_entities"
CONF_GRID_VOLTAGE_ENTITIES = "grid_voltage_entities"
CONF_GRID_ALARM_ENTITIES = "grid_alarm_entities"
CONF_BATTERY_SOC_ENTITIES = "battery_soc_entities"
CONF_WAN_TELEKOM_ENTITIES = "wan_telekom_entities"
CONF_WAN_VODAFONE_ENTITIES = "wan_vodafone_entities"
CONF_OTHER_ENTITIES = "other_entities"
CONF_MANUAL_OVERRIDE = "manual_override"

CONF_COMMONSIGHT_ENABLED = "commonsight_enabled"
CONF_COMMONSIGHT_BASE_URL = "commonsight_base_url"
CONF_COMMONSIGHT_SCOPE = "commonsight_scope"
CONF_COMMONSIGHT_HOME_REGION = "commonsight_home_region"
CONF_COMMONSIGHT_RADIUS_KM = "commonsight_radius_km"
CONF_COMMONSIGHT_LAYERS = "commonsight_layers"

DEFAULT_NAME = "Home"
DEFAULT_OVERRIDE = "auto"

DEFAULT_COMMONSIGHT_ENABLED = True
DEFAULT_COMMONSIGHT_BASE_URL = "https://lagezentrum.previval.org"
DEFAULT_COMMONSIGHT_SCOPE = "DE"
DEFAULT_COMMONSIGHT_HOME_REGION = "DE-HH"
DEFAULT_COMMONSIGHT_RADIUS_KM = 50.0
COMMONSIGHT_SUPPORTED_LAYERS = (
    "warnings",
    "water",
    "radiation",
    "traffic",
    "nature",
    "space",
    "news",
    "weather",
    "air",
)
DEFAULT_COMMONSIGHT_LAYERS = [
    "warnings",
    "water",
    "radiation",
    "traffic",
    "nature",
    "space",
    "news",
]
COMMONSIGHT_REFRESH_MINUTES = 2
COMMONSIGHT_REQUEST_TIMEOUT_SECONDS = 20
COMMONSIGHT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024

DEFAULT_NINA_ENTITIES = [
    "binary_sensor.hamburg_freie_und_hansestadt_warning_1",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_2",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_3",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_4",
    "binary_sensor.hamburg_freie_und_hansestadt_warning_5",
]

DEFAULT_DWD_CURRENT_ENTITIES = [
    "sensor.hamburg_harburg_niveau_d_alerte_actuel",
]
DEFAULT_DWD_ADVANCE_ENTITIES = [
    "sensor.hamburg_harburg_niveau_d_alerte_anticipee",
]

DEFAULT_FLOOD_ENTITIES: list[str] = []
DEFAULT_PEGEL_STAGE_ENTITIES = [
    "sensor.hamburg_st_pauli_elbe_stage",
]

DEFAULT_UBA_LQI_ENTITIES = [
    "sensor.hamburg_neugraben_hamburg_dehh050_lqi_numerisch",
    "sensor.hamburg_wilhelmsburg_hamburg_dehh059_lqi_numerisch",
    "sensor.hamburg_veddel_hamburg_dehh015_lqi_numerisch",
]

DEFAULT_BFS_ASSESSMENT_ENTITIES = [
    "sensor.rosengarten_21224_033530292_measurement_assessment",
    "sensor.hamburg_wilhelmsburg_21109_020000006_measurement_assessment",
    "sensor.stelle_harburg_21435_033530321_measurement_assessment",
]

DEFAULT_LIGHTNING_COUNT_ENTITIES = [
    "sensor.maison_compteur_de_foudre",
]
DEFAULT_LIGHTNING_DISTANCE_ENTITIES = [
    "sensor.maison_distance_de_foudre",
]

DEFAULT_NOAA_ENTITIES = [
    "sensor.planetary_k_index",
    "sensor.a_index",
    "sensor.polar_cap_absorption",
]

DEFAULT_FIRE_HEAT_ENTITIES = [
    "binary_sensor.chaufferie_detection_incendie_entree_1",
]
DEFAULT_FIRE_SMOKE_ENTITIES = [
    "binary_sensor.chaufferie_detection_incendie_entree_0",
]

DEFAULT_GRID_VOLTAGE_ENTITIES = [
    "sensor.shellypro3em_fce8c0d97e64_phase_a_tension",
    "sensor.shellypro3em_fce8c0d97e64_phase_b_tension",
    "sensor.shellypro3em_fce8c0d97e64_phase_c_tension",
]
DEFAULT_GRID_ALARM_ENTITIES = [
    "sensor.multiplus_48_2000_25_32_id_289_grid_lost_alarm",
]
DEFAULT_BATTERY_SOC_ENTITIES = [
    "sensor.victron_over_mqtt_battery_soc",
]
DEFAULT_WAN_TELEKOM_ENTITIES = [
    "binary_sensor.b0_19_21_50_7d_5b_port_1_internet_link",
]
DEFAULT_WAN_VODAFONE_ENTITIES = [
    "binary_sensor.b0_19_21_50_7d_5b_port_2_internet_link",
]

REFRESH_MINUTES = 5

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
EVENT_RSS_ANALYZED = "lagezentrum_rss_analyzed"

# Context engine. This layer never changes deterministic DEFCON by itself.
CONTEXT_REFRESH_MINUTES = 5
CONTEXT_ACTIVE_LIMIT = 12
CONTEXT_HISTORY_LIMIT = 30
CONTEXT_STALE_GRACE_HOURS = 24

# Default validity window for a contextual event. A new report for the same
# event refreshes the expiry time; an explicit lifecycle=resolved closes it.
CONTEXT_TTL_HOURS = {
    "transport": 4,
    "fire": 8,
    "weather": 8,
    "security": 12,
    "electricity": 12,
    "telecom": 12,
    "pollution": 12,
    "water": 24,
    "infrastructure": 24,
    "energy": 24,
    "cyber": 24,
    "sabotage": 24,
    "supply": 24,
    "logistics": 24,
    "health": 24,
    "geopolitical": 36,
    "radiation": 12,
    "geological": 24,
    "space_weather": 12,
    "other": 12,
}


# Curated Feedreader sources for the optional AI-assisted context layer.
# These are installed only when the user presses the bulk-install button.
RSS_RECOMMENDED_SOURCES = [
    {
        "name": "NDR Hamburg",
        "url": "https://www.ndr.de/nachrichten/hamburg/index~rss2.xml",
        "tier": "local",
        "source_class": "public_media",
    },
    {
        "name": "Polizei Hamburg",
        "url": "https://www.presseportal.de/rss/dienststelle_6337.rss2",
        "tier": "local",
        "source_class": "official",
    },
    {
        "name": "Feuerwehr Hamburg",
        "url": "https://www.presseportal.de/rss/dienststelle_82522.rss2",
        "tier": "local",
        "source_class": "official",
    },
    {
        "name": "Bundespolizei Hamburg",
        "url": "https://www.presseportal.de/rss/dienststelle_70254.rss2",
        "tier": "local",
        "source_class": "official",
    },
    {
        "name": "Tagesschau Hamburg",
        "url": "https://www.tagesschau.de/inland/regional/hamburg/index~rss2.xml",
        "tier": "local",
        "source_class": "public_media",
    },
    {
        "name": "Tagesschau Inland",
        "url": "https://www.tagesschau.de/inland/index~rss2.xml",
        "tier": "national",
        "source_class": "public_media",
    },
    {
        "name": "BBK",
        "url": "https://www.bbk.bund.de/DE/Infothek/Unsere-Meldungen/RSSNewsfeed/_functions/rssnewsfeed-bbk.xml?nn=20130",
        "tier": "national",
        "source_class": "official",
        "aliases": [
            "https://www.bbk.bund.de/DE/Infothek/Unsere-Meldungen/RSSNewsfeed/_functions/rssnewsfeed-bbk.xml"
        ],
    },
    {
        "name": "Bundesnetzagentur Presse",
        "url": "https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_Pressemitteilungen.xml?nn=265324",
        "tier": "national",
        "source_class": "official",
        "aliases": [
            "https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_Pressemitteilungen.xml"
        ],
    },
    {
        "name": "Bundesnetzagentur Gas",
        "url": "https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_GAS.xml?nn=654666",
        "tier": "national",
        "source_class": "official",
        "aliases": [
            "https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_GAS.xml"
        ],
    },
    {
        "name": "BSI BürgerCERT",
        "url": "https://wid.cert-bund.de/content/public/buergercert/rss",
        "tier": "national",
        "source_class": "official",
    },
    {
        "name": "Tagesschau Ausland",
        "url": "https://www.tagesschau.de/ausland/index~rss2.xml",
        "tier": "strategic",
        "source_class": "public_media",
    },
    {
        "name": "Tagesschau Europa",
        "url": "https://www.tagesschau.de/ausland/europa/index~rss2.xml",
        "tier": "strategic",
        "source_class": "public_media",
    },
    {
        "name": "Tagesschau Wirtschaft",
        "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
        "tier": "strategic",
        "source_class": "public_media",
    },
]

# Deliberately excluded from automatic installation because it is very noisy.
RSS_OPTIONAL_HIGH_VOLUME_SOURCES = [
    {
        "name": "CERT-Bund Security Advisories",
        "url": "https://wid.cert-bund.de/content/public/securityAdvisory/rss",
        "tier": "national",
        "source_class": "official",
    },
]
