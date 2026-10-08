# DEFCON Home for Home Assistant

## 0.4.9

- fixes `Custom element doesn't exist: defcon-context-events-card` after upgrading from an older release;
- the bundled frontend asset now uses a versioned URL (for example `/defcon-ha/defcon-ha-card-v0.4.9.js`) so Home Assistant/browser caches cannot keep serving the older JavaScript that only registered `defcon-ha-card`;
- no dashboard YAML change is required from v0.4.8;
- no Gemini/RSS automation change is required.


## 0.4.8

- adds a manual archive action for active contextual events;
- new service `defcon_ha.archive_context_event` moves a selected active/stale event to recent history without deleting its record;
- the Lagezentrum dashboard active-events card now shows an **Archiver** link beside the source link for every active event;
- archiving marks the item `resolved`, records `resolved_at`, `resolution_reason=manual_archive` and `archived_manually=true`, then removes it immediately from the active list;
- the operation is context-only and never changes the deterministic DEFCON engine;
- the Gemini/feedreader automation is unchanged in v0.4.8.


## 0.4.6

- adds Harburg Aktuell as a recommended local Harburg/Marmstorf context source;
- adds MOPO as a recommended rapid local-news source;
- the recommended source set now contains 15 sources: 14 Feedreader feeds plus Harburg Aktuell, which is polled directly by DEFCON Home every 5 minutes because the redesigned site no longer exposes a Feedreader-compatible RSS channel;
- Harburg Aktuell is classified as `established_media` with deterministic source baseline 80;
- MOPO is classified as `rapid_media` with deterministic source baseline 65;
- the Gemini prompt explicitly treats `rapid_media` as an early-warning lead: speed does not imply verification, uncertainty lowers `analysis_confidence`, and serious claims should not be presented as confirmed without explicit authority/corroboration;
- the current-RSS one-shot replay script includes MOPO; Harburg Aktuell is seeded and monitored by the internal poller;
- deterministic DEFCON rules remain unchanged.


## 0.4.5

- the 2026-10-04 RSS seed snapshot now contains verified direct article URLs for 104 of 107 replayed items;
- direct links were resolved for NDR, Presseportal/Polizei/Feuerwehr/Bundespolizei, Tagesschau, BBK, Bundesnetzagentur and BSI/BürgerCERT items;
- unresolved items deliberately keep an empty link instead of using a guessed or generic source URL;
- replayed items therefore keep their real article URL through Feedreader → Gemini → context → dashboard;
- deterministic DEFCON rules are unchanged.

The three intentionally unresolved seed items are the Bundespolizei Hauptbahnhof bag item, the Hamburg/Bahn punctuality item, and one generic energy/inflation headline whose exact source article could not be resolved confidently.


## 0.4.4

- Gemini now returns a French `title_fr`; the context dashboard shows the French title and retains the source-language title;
- operational dates, hours and closure windows must be preserved in `summary_fr` and in `event_timing_text`;
- relative dates are resolved from the publication timestamp when available, otherwise from Home Assistant current time;
- explicit event dates are extracted even when already past, so replaying an old scheduled article cannot restart it for a fresh category TTL;
- the context engine preserves `original_title`, `event_timing_text` and an existing article link across correlated updates;
- the dashboard shows the article URL when present and clearly labels the RSS-feed fallback when an article URL is absent;
- the 2026-10-04 seed snapshot restores source links and detailed timing for the Köhlbrandbrückenlauf and 7 October demonstration items.


## 0.4.3

- Gemini now extracts explicit future event dates as `event_start_at` and `valid_until`;
- scheduled events remain active until their explicit end/date instead of expiring only from the generic category TTL;
- if only a future calendar date is given, validity defaults to 23:59:59 on that date;
- events without an explicit future date continue to use the existing category TTL;
- the context sensor exposes `event_start_at`, `valid_until` and `validity_source`;
- the dashboard displays the explicit event date when available.

Example: an article published on 4 October about a demonstration on 7 October can
remain active through 7 October instead of expiring after the 12-hour security TTL.


## 0.4.2

- adds `button.defcon_home_install_rss_sources` for one-click bulk installation of the curated Feedreader set;
- installs only missing sources and skips existing Feedreader entries;
- recognizes known legacy URL aliases for BBK and Bundesnetzagentur feeds;
- reports configured/missing/failed sources as button attributes;
- keeps the high-volume CERT-Bund security-advisory feed opt-in only;
- adds RSS installation status and the install button to the Context dashboard.

The installer creates normal Home Assistant `feedreader` config entries through
Home Assistant's config-flow API. It does not edit `.storage` files directly.


## 0.4.1

- shows the advisory Context DEFCON directly on the main DEFCON card;
- keeps the real deterministic DEFCON visually primary;
- emphasizes the context pill when its recommendation is more severe;
- clicking the context pill opens the advisory context entity;
- dashboard binds `sensor.defcon_home_context_recommended_defcon` explicitly.


## 0.4.0

Version 0.4 adds a persistent **contextual situation layer** alongside the
deterministic DEFCON engine.

- keeps several contextual events active simultaneously instead of only the last article;
- persists active/stale/resolved events through Home Assistant restarts;
- expires information by category and archives it after a stale grace period;
- correlates repeated reports through a stable `event_key` and counts independent sources;
- separates source tiers (`local`, `national`, `strategic`) and source classes;
- combines deterministic source trust, AI classification confidence and corroboration into a contextual confidence score;
- adds categories for cyberattack, sabotage, energy, logistics, supply, health and geopolitics;
- exposes an **indicative context DEFCON recommendation** without ever changing the real deterministic DEFCON;
- adds a three-tier Feedreader/Gemini pipeline and a multi-event dashboard;
- preserves the existing `sensor.defcon_home_lagezentrum_news_context` entity for compatibility.

The deterministic engine remains fully local and AI-free. Gemini is optional and
is used only by the external context pipeline.


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

Since version 0.3 the private GitHub JSON/context feed is removed. The automatic DEFCON level is calculated only from Home Assistant entities already available in the installation. Version 0.4 adds an optional, separate AI-assisted context layer; no AI call is required for the deterministic DEFCON engine.

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
- `sensor.defcon_home_context_status`
- `sensor.defcon_home_context_active_events`
- `sensor.defcon_home_context_recommended_defcon` (advisory only)
- `sensor.defcon_home_lagezentrum_news_context` (detail/compatibility context sensor)
- `button.defcon_home_install_rss_sources` (bulk Feedreader installer)
- manual override select
- refresh button

`Local level` is retained for compatibility and now represents the combined deterministic HA level before manual override.

## Lovelace card

```yaml
type: custom:defcon-ha-card
entity: sensor.defcon_home_level
context_entity: sensor.defcon_home_context_recommended_defcon
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

## Context engine (v0.4)

The integration listens for:

```text
lagezentrum_rss_analyzed
```

This event can be produced by the example Feedreader → Google AI Task
automation in `examples/lagezentrum_rss_context.yaml`.

### Separation from DEFCON

The context engine is deliberately independent from the deterministic DEFCON
calculation.

`sensor.defcon_home_context_recommended_defcon` is **advisory only**. It can
help the operator decide whether to investigate or use the manual override, but
its state is never injected into `sensor.defcon_home_level`.

This prevents one misclassified article or AI hallucination from automatically
changing the household alert level.

### Active events and lifecycle

Relevant reports are stored as contextual events. Several incidents can coexist.

Each event carries, among other fields:

- stable `event_key`;
- `importance` 0–3;
- category and geographic scope;
- direct/potential/no relevance for Marmstorf;
- affected area;
- protective-action flag;
- source tier and source class;
- AI classification confidence;
- combined contextual confidence;
- source/corroboration count;
- first/last seen timestamps and expiry;
- optional explicit `event_start_at` / `valid_until` for scheduled events;
- French display title, source-language title and compact operational timing text;
- `new`, `update` or `resolved` lifecycle;
- French summary, relevance explanation and recommended action.

An explicit all-clear, service restoration or warning cancellation can close an
event immediately with `lifecycle=resolved`.

Without an explicit resolution, events age automatically. When Gemini extracts
an explicit event validity date, that date takes precedence over the generic
category TTL, including a past date when an old article is replayed. Otherwise the category TTL below is used:

| Category | Active validity |
| --- | ---: |
| transport | 4 h |
| fire, weather | 8 h |
| security, electricity, telecom, pollution | 12 h |
| water, infrastructure, energy, cyber, sabotage, supply, logistics, health | 24 h |
| geopolitical | 36 h |
| other | 12 h |

After expiry an event becomes `stale`. It remains visible for a 24-hour grace
period, then moves to the recent-event history. A new correlated report refreshes
its expiry.

### Correlation and confidence

Reports with the same `event_key` are merged. The same article link is also
deduplicated. Cross-source semantic correlation therefore depends on the AI
producing a stable event key for the same incident.

Source classes have deterministic trust baselines:

- official: 95;
- public media: 85;
- established media: 80;
- rapid media: 65;
- other: 60.

The context engine combines the source baseline with
`analysis_confidence`, then adds a small corroboration bonus for additional
independent sources. The resulting `confidence_score` is a prioritization aid,
not a guarantee that the report is true.

### One-click RSS installation

Version 0.4.2 exposes:

```text
button.defcon_home_install_rss_sources
```

Press it once to create all missing recommended Feedreader config entries.
Already configured URLs are skipped. If a feed cannot be added, installation
continues with the remaining sources and the failure is exposed in the button
attributes.

The button reports 15 recommended sources across local, national and strategic
tiers. Fourteen are normal Feedreader entries. Harburg Aktuell is provided by
DEFCON Home's internal 5-minute web poller and therefore counts as configured
without creating a Feedreader entry. The high-volume CERT-Bund
security-advisory feed remains excluded by design.

### Source tiers

The example source plan in `examples/lagezentrum_sources.md` uses three tiers:

1. **Local/Hamburg** — NDR Hamburg, Polizei Hamburg, Feuerwehr Hamburg,
   Bundespolizei Hamburg, Tagesschau Hamburg, Harburg Aktuell and MOPO.
2. **Germany / critical infrastructure** — Tagesschau Inland, BBK,
   Bundesnetzagentur and BSI/BürgerCERT.
3. **Strategic Europe/world** — Tagesschau Europa, Ausland and Wirtschaft,
   aggressively filtered for concrete short-term relevance to Germany/Hamburg.

A high-volume CERT-Bund vulnerability feed is documented as optional because
ordinary vulnerability advisories would otherwise generate unnecessary AI calls
and noise.

### Context sensors

`sensor.defcon_home_context_status` reports `idle`, `information`,
`watch`, `important` or `stale`.

`sensor.defcon_home_context_active_events` reports the number of active
context events.

`sensor.defcon_home_context_recommended_defcon` reports the advisory context
level (5, 4 or 3 in v0.4).

`sensor.defcon_home_lagezentrum_news_context` keeps the 0.3.x entity identity
and exposes the highest-priority event plus `active_events`, `stale_events`
and `recent_events` attributes for dashboards.

See:

- `examples/lagezentrum_rss_context.yaml`
- `examples/lagezentrum_sources.md`
- `examples/lagezentrum_dashboard.yaml`

## Resilience

- No runtime GitHub dependency.
- No runtime AI dependency.
- Internet loss does not stop local fire/grid/battery evaluation.
- Missing/unavailable source entities are visible through Source health.
- Manual override remains available.

## License

MIT
