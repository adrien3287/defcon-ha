"""Constants for DEFCON Home."""

from __future__ import annotations

DOMAIN = "defcon_ha"
NAME = "DEFCON Home"
VERSION = "0.3.0"

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

DEFAULT_NAME = "Home"
DEFAULT_OVERRIDE = "auto"

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
