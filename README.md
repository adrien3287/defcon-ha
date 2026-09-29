# DEFCON Home for Home Assistant

DEFCON Home combines **immediate local Home Assistant alerts** with a **private contextual situation feed** to produce one household DEFCON level from 5 (normal) to 1 (immediate danger).

## Architecture

```text
Immediate / local                         Context / hourly analysis
Home Assistant                           private GitHub repo
                                              adrien3287/defcon-json
NINA warning slots ─┐                         status/current.json
DWD warning levels ─┤                               │
HVV status ─────────┼─> Local DEFCON                  │ HTTPS + read-only token
Other HA alarms ────┘       │                         ▼
                            └──────────────┐   Context DEFCON
                                           ▼         │
                                      Aggregator <───┘
                                           │
                                  final = most severe
                                           │
                                  Manual override
                                           │
                                  DEFCON Home card
```

The contextual feed can **escalate** the result but can never hide a more severe local NINA/DWD/HVV/HA alert.

If the context feed is stale, unavailable or invalid, it is automatically excluded from the automatic level. Local monitoring continues normally.

## v0.2.0

- Immediate local evaluation of NINA, DWD, HVV and optional HA entities.
- Private GitHub JSON feed polled every 5 minutes.
- Feed freshness enforced with `valid_until`.
- Three sensors:
  - `Level` — final effective DEFCON.
  - `Local level` — only immediate HA sources.
  - `Context level` — hourly contextual analysis.
- Persistent manual override.
- Refresh button.
- Lovelace card showing Local / Context / Automatic / Final.
- Options UI to change source entities and GitHub credentials without recreating the integration.
- GitHub token is never exposed in entity attributes.

## Default Hamburg entities

New installations prefill:

```text
sensor.hamburg_harburg_niveau_d_alerte_actuel
sensor.hamburg_harburg_niveau_d_alerte_anticipee

binary_sensor.hamburg_freie_und_hansestadt_warning_1
binary_sensor.hamburg_freie_und_hansestadt_warning_2
binary_sensor.hamburg_freie_und_hansestadt_warning_3
binary_sensor.hamburg_freie_und_hansestadt_warning_4
binary_sensor.hamburg_freie_und_hansestadt_warning_5
```

Existing installations can set these under **Settings → Devices & services → DEFCON Home → Configure**.

## Private context feed

Default repository configuration:

```text
owner: adrien3287
repository: defcon-json
path: status/current.json
```

Because the repository is private, create a dedicated GitHub fine-grained personal access token with:

- Repository access: only `defcon-json`
- Repository permission: **Contents: Read**
- No write/admin permission

Enter the token in the DEFCON Home options screen. It is sent as an HTTP `Authorization: Bearer` header, never in the URL.

### Expected JSON

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-29T22:23:00+02:00",
  "valid_until": "2026-09-29T23:53:00+02:00",
  "context_defcon": 4,
  "confidence": "medium",
  "summary": "Short situation summary",
  "areas": {
    "marmstorf_harburg": {"level": 5, "summary": "..."},
    "hamburg": {"level": 4, "summary": "..."},
    "germany": {"level": 4, "summary": "..."},
    "europe": {"level": 4, "summary": "..."}
  },
  "reasons": [],
  "weak_signals": [],
  "checks": {},
  "source_count": 8
}
```

Only a feed with a valid DEFCON level and a future `valid_until` influences the automatic result.

## Decision rule

```text
automatic DEFCON = min(local DEFCON, fresh context DEFCON)
final DEFCON     = manual override if enabled, otherwise automatic DEFCON
```

Example:

```text
Local   = 5
Context = 4
Final   = 4

Local   = 3
Context = 5
Final   = 3

Local   = 3
Context = stale
Final   = 3
```

## Local default policy

| Source | Condition | Level |
| --- | --- | ---: |
| none | no active local reason | 5 |
| NINA Minor | selected official warning | 4 |
| NINA active | normal active official warning | 3 |
| NINA Extreme / Severe+Immediate | high-severity official warning | 2 |
| DWD current level 1-2 | weather watch | 4 |
| DWD current level 3 | serious weather | 3 |
| DWD current level 4+ | very severe weather | 2 |
| DWD advance level 1-3 | advance weather watch | 4 |
| DWD advance level 4+ | severe advance warning | 3 |
| HVV selected disruption | disruption/cancellation/closure/15+ min delay | 4 |
| Other selected HA problem | active alarm/problem | 4 |

## Card

```yaml
type: custom:defcon-ha-card
entity: sensor.defcon_home_level
title: DEFCON Maison
show_sources: true
```

The card is served and loaded automatically by the integration.

## Events

Every effective level change fires:

```text
defcon_ha_level_changed
```

with:

```yaml
old_level: 5
new_level: 4
automatic_level: 4
local_level: 5
context_level: 4
context_status: fresh
summary: ...
reasons: [...]
```

## Privacy and resilience

- The contextual repository is private.
- The feed contains no exact home address, Home Assistant entity IDs, tokens or secrets.
- The Home Assistant GitHub token is read-only and limited to one repository.
- A GitHub/Internet/ChatGPT outage cannot suppress an immediate local warning.
- An expired contextual report is never interpreted as proof that the situation is normal.

## License

MIT
