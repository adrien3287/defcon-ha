# Lagezentrum source plan (v0.4)

The context layer is intentionally broader than the deterministic DEFCON engine.
These sources are consumed by Home Assistant Feedreader, classified by Gemini,
then sent to DEFCON Home through the `lagezentrum_rss_analyzed` event.

The AI/context path is informational. It does **not** directly change the
deterministic DEFCON level.

## Tier 1 - Local / Hamburg

Add these first:

- NDR Hamburg  
  `https://www.ndr.de/nachrichten/hamburg/index~rss2.xml`
- Polizei Hamburg  
  `https://www.presseportal.de/rss/dienststelle_6337.rss2`
- Feuerwehr Hamburg  
  `https://www.presseportal.de/rss/dienststelle_82522.rss2`
- Bundespolizeiinspektion Hamburg  
  `https://www.presseportal.de/rss/dienststelle_70254.rss2`
- Tagesschau Hamburg  
  `https://www.tagesschau.de/inland/regional/hamburg/index~rss2.xml`

Typical use: fire/smoke, evacuation, police operations, rail disruption,
local infrastructure failure and other events with a short path to Marmstorf.

## Tier 2 - Germany / national infrastructure

- Tagesschau Inland  
  `https://www.tagesschau.de/inland/index~rss2.xml`
- BBK current news  
  `https://www.bbk.bund.de/DE/Infothek/Unsere-Meldungen/RSSNewsfeed/_functions/rssnewsfeed-bbk.xml`
- Bundesnetzagentur press releases  
  `https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_Pressemitteilungen.xml?nn=265324`
- Bundesnetzagentur - current gas supply  
  `https://www.bundesnetzagentur.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed_GAS.xml?nn=654666`
- BSI BürgerCERT  
  `https://wid.cert-bund.de/content/public/buergercert/rss`

Typical use: national cyber incidents, civil protection, energy/gas,
telecommunications and major infrastructure disruption.

### Optional high-volume cyber feed

CERT-Bund WID:

`https://wid.cert-bund.de/content/public/securityAdvisory/rss`

This feed publishes many ordinary vulnerability advisories. It is intentionally
**not** in the recommended default set because sending every advisory to Gemini
adds noise and AI usage. If enabled, the v0.4 prompt is deliberately conservative:
a normal software vulnerability should be rejected unless there is active,
large-scale exploitation or a concrete critical-infrastructure/service impact.

## Tier 3 - Strategic / Europe and world

- Tagesschau Ausland  
  `https://www.tagesschau.de/ausland/index~rss2.xml`
- Tagesschau Europa  
  `https://www.tagesschau.de/ausland/europa/index~rss2.xml`
- Tagesschau Wirtschaft  
  `https://www.tagesschau.de/wirtschaft/index~rss2.xml`

These feeds are deliberately filtered aggressively by Gemini. Ordinary foreign
news is irrelevant. The intended signals are events such as major cyberattacks,
sabotage of energy/data infrastructure, severe supply/logistics disruption,
major security incidents or geopolitical developments with a plausible
short-term impact on Germany/Hamburg.

## Trust model

The automation attaches source metadata before the AI call:

- `official`: authorities such as Polizei, Feuerwehr, BBK, BNetzA and BSI.
- `public_media`: NDR / Tagesschau.
- `established_media`: reserved for additional curated media feeds.
- `other`: unknown/unclassified sources.

DEFCON Home combines this deterministic source class with the AI's
`analysis_confidence` and corroboration by additional independent sources.
The result is a contextual `confidence_score`; it is not a truth score.

## Event lifecycle

Gemini returns `new`, `update` or `resolved`.

- `new`: create a new event.
- `update`: refresh/correlate an existing event using `event_key`.
- `resolved`: close an event only when the article explicitly reports the
  all-clear, restoration, lifted warning or end of the incident.

Without an explicit resolution, the integration expires events by category.
They first become `stale`, then are archived after the stale grace period.
