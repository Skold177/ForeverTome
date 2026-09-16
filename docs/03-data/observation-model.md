# Proposed observation model

[Documentation index](../README.md) · [Worked example](../examples/README.md)

**Status:** proposed ForeverTome design, not an implemented storage format or Blizzard API. The example JSON illustrates this proposal. Schema changes remain possible before implementation.

## Record an observation before interpreting it

One record should describe one meaningful observation: a quest acceptance, an objective snapshot, a visible loot slot, or an item metadata response. Keep observations even when a desired relationship is unknown.

Separate three data layers:

| Layer | Purpose | Example |
| --- | --- | --- |
| Observation | What a permitted client API revealed at a time | A quest objective changed from 0/2 to 1/2 |
| Entity metadata | Descriptive information attached by ID/build/locale | Item name, quest text, NPC label |
| Derived relationship | A conclusion supported by linked observations and a named rule | A candidate creature-to-objective association |

A later conclusion or metadata load must not rewrite the original observation's time, location, or evidence. Add an enrichment or relationship record referring to it.

## Export and session envelope

The proposed export contains `schema_version`, `synthetic`, `session`, and `observations`. A real exporter must set `synthetic = false`; documentation fixtures set it to true. The schema version describes ForeverTome's format, independently of client or addon versions.

| Session field | Type | Purpose |
| --- | --- | --- |
| `session_id` | String | Opaque recording-session identity, unique within the dataset |
| `product` | String | `WF`; prevents accidental merging with other game products |
| `client.version`, `client.build` | Strings | Exact observed build identity; fixture values may explicitly say `SYNTHETIC` |
| `client.interface_version`, `client.project_id` | Number or null | Measured compatibility identifiers, never guessed |
| `client.locale` | String | Locale for names, descriptions, and any message parsing |
| `addon_version` | String | Collector implementation version |
| `adapter_id` | String | Exact payload/API adapter used |
| `capabilities` | Object | Per-feature evidence status, available contexts and restrictions |

A future implementation must define a collision-resistant session-ID strategy that does not expose a character name/GUID. The importer should namespace uploaded IDs by a private installation/export identity, or reject a conflicting session header; never silently merge two sessions just because their IDs match.

## Common observation fields

| Field | Type | Rule |
| --- | --- | --- |
| `observation_id` | String | Unique record identity; example uses `session_id:sequence` |
| `session_id` | String | References the session header |
| `sequence` | Positive integer | Strictly increases in capture order within the session |
| `kind` | String | Semantic record type from the catalog below |
| `observed_at_server_s` | Number or null | Reference wall-clock time when captured; name specifies seconds |
| `elapsed_s` | Number | Session-relative monotonic time; not comparable across sessions |
| `capture` | Object | Actual event/read/derivation and relevant sampling times |
| `location` | Object or null | Position sample and its subject/method; optional when irrelevant |
| `data` | Object | Allowlisted fields for this record kind |
| `evidence` | Object | Evidence method; never a universal numeric confidence score |
| `related_observation_ids` | Array of strings | Specific supporting records, possibly empty |
| `missing_fields` | Object | Field path mapped to a controlled missing-data reason |

`capture.event` is a WoW event name only when one actually triggered capture. An externally derived relationship uses `capture.method = external_derivation`, not a fabricated game event. A deferred read should include `trigger_elapsed_s` and `sampled_elapsed_s` so its actual observation time is clear.

## Proposed record kinds

| Kind | Essential domain fields | Evidence boundary |
| --- | --- | --- |
| `quest.accepted` | Quest ID, quest-run ID | Acceptance event observed, not merely present at login |
| `quest.snapshot` | Quest ID/run, layout revision, objective array, completeness | Readable state at sampling time |
| `quest.objective_delta` | Quest ID/run/layout, objective index, before/after | Derived from two comparable snapshots; not causal attribution |
| `quest.ready` | Quest ID/run and reported state | Ready/completion flag, not turn-in |
| `quest.turned_in` | Quest ID/run if known, observed rewards | Explicit turn-in evidence |
| `quest.removed` | Quest ID/run, reason if supported | Removal can have unknown cause |
| `unit.sighting` | Readable entity identity/kind/name, token context | Encountered entity; observer position |
| `unit.dead_state` | Entity identity and observed state | A dead sighting, not necessarily a newly witnessed death |
| `unit.death` | Validated death source and entity | Enabled only with a tested supported death feed |
| `loot.visible` | Loot session, slot/revision, slot kind, item/currency/money data, source entries | Visibility and explicit mappings only |
| `item.received` | Item/variant, quantity, validated recipient classification | Receipt, with source possibly unknown |
| `item.metadata` | Item ID/link, build/locale and resolved fields | Later enrichment, not a new acquisition |
| `profession.recipe` | Recipe/profession identity and observed requirements | View scope and learned state must be explicit |
| `profession.result` | Result item/quantity and supported crafting context | Do not invent a recipe ID absent from evidence |
| `interaction.snapshot` | Interaction ID, context/type, readable dialogue/offers | Options shown are distinct from actions taken |
| `coverage.gap` | Affected collectors, interval or sequence bounds, reason/count | Explains missing observations |
| `relationship.candidate` | Relationship type, evidence IDs, rule/version, unresolved alternatives | A proposed association, not a promoted content fact |

This is an extensible vocabulary. A new kind requires documented fields and examples; it does not require inventing a corresponding game event.

## Location representation

An available map sample contains `status`, `subject`, `coordinate_system`, `ui_map_id`, `x`, `y`, `method`, and `sampled_elapsed_s`. The sample's subject is normally `player`. Other identity/instance context can be added when verified.

An unavailable sample uses `status = unavailable` and a reason; retain independently known map context if useful. Use no fake numeric coordinates. See [location rules](../02-api/maps-and-location.md).

## Missing data and evidence

Use a consistent missing-data vocabulary:

| Reason | Meaning |
| --- | --- |
| `not_observed` | Recording did not see the relevant fact |
| `not_ready` | State/metadata was not yet available |
| `not_applicable` | The field does not apply to this observation |
| `unsupported` | No supported capture API/adapter is available |
| `restricted` | The client denies access or returns unreadable data |
| `unknown_source` | The observation exists but source attribution is unavailable |
| `transition` | World/context changed during the observation |
| `no_map` / `no_position` | Specific location failures |
| `invalid_result` | Result failed structural validation |
| `capacity_limit` | Recorder limits prevented capture |

Keep `null`, zero, false, and empty collections distinct. In Lua, assigning nil removes a table field; the exporter must explicitly represent null/omission and missing reasons. An empty source list with `unknown_source` is not evidence that there was no source.

Evidence methods include `direct_event`, `api_snapshot`, `snapshot_diff`, and `temporal_candidate`. “Direct” describes the source of that particular fact. It does not make the entire record or a nearby association direct evidence.

## Identity, localization, and serialization

Preserve numeric content IDs without using localized names as keys. Scope IDs by product and relevant build/content revision. Keep item variants and entity instances distinct from template IDs. Never merge WF records with another product solely because numeric IDs match.

Persist only ordinary scalars and plain tables with explicitly supported keys. Exclude functions, userdata, frames, vectors, metatables, cycles, secrets, and unbounded raw payloads. Convert permitted API objects into allowlisted scalar fields at capture time.

Descriptions may contain localized UTF-8 text, line breaks, and WoW hyperlink/color markup. Preserve original text as data; escape it when rendering on a website. A normalized/searchable representation can be generated separately. Do not execute saved text as code.

The [persistence chapter](persistence-and-export.md) defines durability and export boundaries; [correlation](correlation.md) defines how to derive relationships.

The [recording invariants](../06-testing/recording-invariants.md) turn this model into regression requirements. The harness must assert full records and immutable historical prefixes, then repeat those checks after later events, enrichment, restore, and export.
