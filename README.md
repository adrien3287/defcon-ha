# DEFCON Home for Home Assistant

## 0.3.2

- adds an optional event-driven RSS/Gemini context sensor;
- listens for `lagezentrum_rss_analyzed` and stores the latest relevant item;
- restores the latest context after Home Assistant restart;
- context remains informational and never changes DEFCON directly;
- adds a ready-to-use Feedreader → Gemini automation example and dashboard context view.

## 0.3.1

- corrected fire input mapping: input 0 = smoke, input 1 = heat;
- fire detection now explicitly represents the whole house;
- refined UBA LQI corroboration logic;
- dashboard labels corrected accordingly.

DEFCON Home is a **local deterministic situation engine** for Home Assistant.

Version 0.3 removes the private GitHub JSON/context feed completely. The automatic DEFCON level is calculated only from Home Assistant entities already available in the installation. No ChatGPT/AI call is required at runtime.

## Architecture

Home Assistant entities are grouped into two domains:

- **External situation**: NINA, DWD current + advance, flood warning levels, PEGELONLINE, UBA LQI, BfS ODL assessments, Blitzortung and NOAA Space Weather.
- **House infrastructure**: whole-house fire detection (smoke/heat loop), three-phase grid voltage, Victron grid-loss alarm, battery SOC and the two Internet WAN links.

NASA FIRMS remains useful for the situation map but is **explicitly excluded from the DEFCON calculation**.

## Levels

| DEFCON | Meaning |
| ---: | --- |
| 5 | Normal |
| 4 | Watch |
| 3 | Alert |
| 2 | Severe |
| 1 | Critical |

The final level is the most severe active deterministic rule, unless a manual override is selected.

## Default Hamburg/Marmstorf sources

### Official / external

- NINA: five Hamburg warning slots.
- DWD current: `sensor.hamburg_harburg_niveau_d_alerte_actuel`
- DWD advance: `sensor.hamburg_harburg_niveau_d_alerte_anticipee`
- PEGELONLINE: `sensor.hamburg_st_pauli_elbe_stage`
- UBA LQI: Neugraben, Wilhelmsburg and Veddel numeric LQI sensors.
- BfS ODL assessment: Rosengarten, Hamburg-Wilhelmsburg and Stelle/Harburg.
- Blitzortung: local lightning count and nearest-distance sensors.
- NOAA: planetary K index, A index and polar-cap absorption.

Flood-warning entities are configurable but intentionally have no hard-coded default until an authoritative flood-warning entity is selected.

### House infrastructure

- Smoke: `binary_sensor.chaufferie_detection_incendie_entree_0`
- Heat: `binary_sensor.chaufferie_detection_incendie_entree_1`

The entity IDs still contain `chaufferie`, but the two inputs represent the fire-detection loop for the whole house.
- Grid voltage: Shelly Pro 3EM L1/L2/L3 voltage sensors.
- Victron: MultiPlus grid-lost alarm.
- Battery: Victron battery SOC.
- WAN 1: Telekom.
- WAN 2: Vodafone.
- UPS: intentionally not used.
- Water pressure: not used until local monitoring exists.

## Main rules

### NINA

- Minor -> DEFCON 4
- Moderate -> DEFCON 3
- Severe -> DEFCON 2
- Extreme -> DEFCON 1

### DWD

Current warning:
- levels 1-2 -> DEFCON 4
- level 3 -> DEFCON 3
- level 4+ -> DEFCON 2

Advance warning:
- levels 1-3 -> DEFCON 4
- level 4+ -> DEFCON 3

### Hydrology

For configured official/stage sensors:
- 0 -> normal
- 1 -> DEFCON 4
- 2 -> DEFCON 3
- 3 -> DEFCON 2
- 4+ -> DEFCON 1

Raw centimetre values are not used as universal thresholds.

### UBA LQI

Air quality is deliberately weighted conservatively and requires corroboration across the configured nearby stations:

- LQI 0-2 -> normal
- one isolated LQI 3 -> no DEFCON change
- at least two configured stations at LQI 3+ -> DEFCON 4
- at least one configured station at LQI 4+ -> DEFCON 4
- at least three configured nearby stations at LQI 4+ -> DEFCON 3

Ambient air quality alone never drives DEFCON 1 or 2. "Nearby" means the UBA stations selected in the integration options.

### BfS ODL

The integration uses the BfS **measurement assessment** entity, not a single fixed µSv/h threshold. `within_natural_range` is normal; abnormal assessments create an alert.

### Blitzortung

When lightning is detected:
- nearest strike <= 5 km -> DEFCON 3
- nearest strike <= 15 km -> DEFCON 4

### NOAA Space Weather

- Kp >= 5 -> DEFCON 4
- Kp >= 7 -> DEFCON 3
- Kp >= 8 -> DEFCON 2

### Fire

- heat OR smoke -> DEFCON 2
- heat AND smoke -> DEFCON 1

### Electrical grid

- one abnormal phase -> DEFCON 4
- multi-phase fault or Victron grid-loss alarm -> DEFCON 3
- during a significant grid fault: battery SOC < 35% -> DEFCON 2
- during a significant grid fault: battery SOC < 20% -> DEFCON 1

Unavailable source entities are reported separately as degraded monitoring and are not silently interpreted as normal.

### Internet

- one WAN down -> DEFCON 4
- Telekom + Vodafone down -> DEFCON 3
- both WAN down together with a significant grid fault -> DEFCON 2

## Entities created

- `sensor.defcon_home_level`
- `sensor.defcon_home_local_level`
- `sensor.defcon_home_external_level`
- `sensor.defcon_home_infrastructure_level`
- `sensor.defcon_home_source_health`
- `sensor.defcon_home_lagezentrum_news_context` (optional RSS/Gemini context)
- manual override select
- refresh button

`Local level` is retained for compatibility and now represents the combined deterministic HA level before manual override.

## Lovelace card

```yaml
type: custom:defcon-ha-card
entity: sensor.defcon_home_level
title: DEFCON Maison
show_sources: true
```

The card shows External / Infrastructure / Automatic levels, active reasons and degraded sources.

## Event

Every effective level change fires:

```text
defcon_ha_level_changed
```

with the old/new level, external level, infrastructure level, summary and active reasons.

## Optional RSS / Gemini context

The integration can listen for the Home Assistant event:

```text
lagezentrum_rss_analyzed
```

and stores the latest relevant item in:

```text
sensor.defcon_home_lagezentrum_news_context
```

Expected event fields include `relevant`, `importance`, `category`, `scope`,
`protective_action`, `summary_fr`, `reason`, `recommended_action`,
`title`, `link` and `feed_url`.

See `examples/lagezentrum_rss_context.yaml` for a Feedreader → Google AI Task
automation. The AI context layer is deliberately separate from the deterministic
DEFCON calculation.

## Resilience

- No runtime GitHub dependency.
- No runtime AI dependency.
- Internet loss does not stop local fire/grid/battery evaluation.
- Missing/unavailable source entities are visible through Source health.
- Manual override remains available.

## License

MIT
