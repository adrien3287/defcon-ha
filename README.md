# DEFCON Home for Home Assistant

A local Home Assistant integration that converts existing warning and transport entities into a single household situation level (`DEFCON 5` to `DEFCON 1`) and explains **why** the level is active.

The integration does **not** call DWD or HVV itself. It consumes entities that already exist in Home Assistant. For NINA it can additionally call the official `nina.get_details` Home Assistant action to enrich an active warning with its headline, description and severity.

## What v0.1.0 includes

- One calculated sensor for the current household DEFCON level.
- Separate `automatic_level` so manual decisions never hide what the engine calculated.
- Persistent manual override: `Auto`, `DEFCON 5`, `4`, `3`, `2`, `1`.
- Current reasons stored as structured sensor attributes: source, entity, headline, detail, severity and proposed level.
- Event `defcon_ha_level_changed` whenever the effective level changes.
- Bundled Lovelace card `custom:defcon-ha-card`, loaded automatically by the integration.
- UI configuration flow for NINA, DWD, HVV and optional generic Home Assistant entities.
- No external Python dependency and no additional cloud API.

## Default decision policy

The first version deliberately uses simple, auditable rules. They can later be made editable from the UI.

| Source | Condition | Automatic level |
| --- | --- | ---: |
| NINA | active selected official warning | DEFCON 3 |
| NINA | severity `Extreme`, or `Severe` + urgency `Immediate` | DEFCON 2 |
| NINA | severity `Minor` | DEFCON 4 |
| DWD current | level 1-2 | DEFCON 4 |
| DWD current | level 3 | DEFCON 3 |
| DWD current | level 4+ | DEFCON 2 |
| DWD advance | level 1-3 | DEFCON 4 |
| DWD advance | level 4+ | DEFCON 3 |
| HVV | selected entity contains a disruption/cancellation/closure/delay signal | DEFCON 4 |
| Other | selected alarm/status entity is active or contains warning/problem keywords | DEFCON 4 |
| None | no active reason | DEFCON 5 |

The most severe active reason wins. A manual override changes the effective level but leaves `automatic_level` untouched.

## Installation

### HACS custom repository

1. In HACS, add `https://github.com/adrien3287/defcon-ha` as a custom **Integration** repository.
2. Install **DEFCON Home**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → DEFCON Home**.
5. Select the existing entities you want the engine to monitor.

### Manual

Copy `custom_components/defcon_ha` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Recommended source configuration

### NINA

Select the NINA warning slots for the area relevant to the house. The built-in NINA integration creates warning slots and exposes details through `nina.get_details` when a warning is active.

### DWD

Select the DWD weather-warning level sensors, typically the current and optionally advance warning sensors, for example:

```text
sensor.dwd_weather_warnings_current_warning_level
sensor.dwd_weather_warnings_advance_warning_level
```

The engine reads the `warning_N_level`, `warning_N_headline`, `warning_N_description` and related attributes when available.

### HVV

Select only entities that matter for household mobility, such as status/disruption entities for the relevant S-Bahn/bus routes. DEFCON Home intentionally does not treat every HVV entity as a risk source.

## Dashboard card

The integration serves and injects the card automatically. Add a manual card to a dashboard:

```yaml
type: custom:defcon-ha-card
entity: sensor.defcon_home_level
title: DEFCON Maison
show_sources: true
```

The actual entity ID can differ depending on the Home Assistant entity registry. Pick the `Level` sensor created under the **DEFCON Home** device.

The card shows:

- effective DEFCON level;
- automatic level;
- manual override, when active;
- short summary;
- every active reason with its source and proposed level;
- configured source entity IDs;
- last evaluation time.

Click the colored header to open the normal Home Assistant more-info dialog.

## Automations

Every effective level change fires:

```text
defcon_ha_level_changed
```

Event data example:

```yaml
old_level: 5
new_level: 3
automatic_level: 3
summary: "Official warning ..."
reasons:
  - source: NINA
    entity_id: binary_sensor.example_warning_1
    title: Official warning
    detail: ...
    level: 3
    severity: Moderate
```

This event is intended for household reactions such as notifications, ventilation shutdown, emergency lighting or a dedicated DEFCON dashboard. Safety-critical actions should still include their own checks rather than relying on one aggregate level alone.

## Architecture

```text
Existing HA integrations/entities
  ├─ NINA warning slots ───┐
  ├─ DWD warning levels ───┤
  ├─ HVV status ───────────┼─> DEFCON coordinator ─> sensor (level + reasons)
  └─ other alarm sensors ──┘                     ├─> manual override select
                                                  ├─> level_changed event
                                                  └─> Lovelace card
```

The coordinator is event-driven: changes to selected Home Assistant entities trigger a reevaluation. Recorder/history can therefore track the calculated level like any other sensor.

## Next useful increments

- UI-editable rules and thresholds instead of hard-coded defaults.
- Dedicated source adapters for the exact HVV entity schema used in the target installation.
- Additional household signals: power/grid, water, Internet, BSI/security, smoke/CO, battery autonomy and local infrastructure.
- Reason acknowledgement/snooze without suppressing the underlying warning.
- Timeline/history view and per-source freshness/health checks.
- Optional escalation hysteresis to prevent brief source glitches from changing level.

## License

MIT
