# Database export and coverage

Version 0.3.0 publishes 16 JSON files. `history.json` retains all available evidence; `database.json` is the cumulative database projection; 13 category files are convenient views; `latest.json` represents the current SavedVariables save. Export before clearing the addon and continue using the same destination folder.

## Files and structure

| File | What it tracks | Structure and coverage boundary |
| --- | --- | --- |
| `history.json` | Every imported observation, including player/world/location state, lifecycle, diagnostics, quest-log scope, and coverage gaps | `contexts`, `sessions`, ordered `records`, migration `imports`, `retention`, `summary`, and `historyId`. Raw evidence is preserved even when it creates no catalog entity. |
| `database.json` | Cumulative entities, observed relationships, field coverage, and loot-window evidence | `catalog`, `relationships`, `coverage`, `lootStatistics`, plus all `records`, sessions, contexts and matching `historyId`. |
| `items.json` | Base items, exact link variants, metadata, stats/tooltips, item spells, socketed gems, vendor/recipe/loot references and storage discoveries | `entries` contain descriptive facts and field evidence; `records` preserve individual quantities and variants. Inventory presence, loot visibility and receipts are separate channels. |
| `quests.json` | Observed quest definitions, narrative, objectives, rewards, interactions and runs | Catalog entries reference snapshots and events. Current-log baselines are not acceptances; removed quests are not automatically abandoned; prerequisites and objective target IDs remain unknown unless directly exposed. |
| `creatures.json` | Canonical creature identities and their observed descriptors, reactions, roles, services, casts and interactions | One scoped entity `key` per native creature ID. Facts preserve conflicting/contextual values. Native position and observer position remain separate. |
| `npcs.json` | Compatibility view of all canonical creatures | Same entity keys as `creatures.json`; `canonicalCategory: "creatures"`. Do not import a second creature table. |
| `monsters.json` | Creatures observed with player reaction 1–4 | Same entity keys; `selection` describes the observed-reaction rule. Membership does not establish a permanent monster classification. |
| `objects.json` | GameObject identities exposed by readable loot-source GUIDs | Separate from creatures. Exact GUID-matched object tooltips can supply an observed label and text. Generic objects are not automatically classified as chests or gathering nodes. |
| `spells.json` | Player/pet spellbook entries, observed player/NPC spells, descriptions, tooltips, costs and cooldown state | Each spell has source facts; current character costs/cooldowns are contextual. Descriptions do not become invented damage coefficients. |
| `talents.json` | Accessible trees, nodes, entries, definitions, conditions, costs and observed selections | Configuration IDs are scoped to their recording session to prevent collisions between characters. Tree/node native IDs retain their content identity. |
| `recipes.json` | Enumerated/learned recipes, available schematics, output and reagent alternatives | Scans report scope and completion. Reagent alternatives and optional slots retain their conditions; they are not all mandatory ingredients. |
| `professions.json` | Readable profession identities and viewed profession information | Referenced profession IDs may have incomplete descriptions. Recipe scans cover the profession the player opened. |
| `maps.json` | Maps referenced by recorded positions and readable map metadata | Observations retain zone/subzone and position context. Unknown terrain, transitions and unvisited maps are not filled in. |
| `currencies.json` | Currency identities and readable metadata referenced in loot, rewards or costs | Referenced IDs can remain without a known name; observations retain amounts and context. |
| `gathering.json` | Recognized herbalism, mining, skinning and fishing cast outcomes | Entries retain profession, spell, outcome, attempt ID when present, source IDs and player location. Start records remain in history and linked evidence. Success means a successful cast, not a confirmed resource yield. |
| `latest.json` | Complete current save projected into catalogs, transactions and observations | Contains only that save; use history/database for cumulative coverage. Its legacy catalog retains the `npcs` bucket. |

Category envelopes use `format: "forevertome.catalog-category"`, `schemaVersion`, `category`, `entries`, supporting `records`, `sessions`, and `contexts`. Records include the closure of explicit related-observation links. An entity reference can point into another category, so resolve references using the complete database. Standalone records without a category entity still live in history and database.

Schemas: [history](../schemas/catalog-history-v1.schema.json), [database](../schemas/database-v1.schema.json), [categories](../schemas/catalog-category-v1.schema.json), [current-save catalog](../schemas/website-catalog-v1.schema.json).

## Import identities and evidence

Use each entity's `key` as the scoped database identity. Keys preserve product/build/locale boundaries. `canonicalKind` maps the historical `npc` key kind to `creature` without breaking existing references. `contentKey` groups compatible native IDs for comparison across contexts; it is not permission to overwrite build-specific or localized facts. Talent configuration content keys retain their session scope.

Entities contain `firstObserved`, `lastObserved`, `observationOrder`, `sourceCount`, descriptive `facts`, and `fieldCoverage`. Each field retains candidate values with supporting `sourceIds` and `factIds`, explicit missing reasons, and statuses such as `captured`, `not_scanned`, `unavailable`, or `restricted`. `hasMultipleValues` signals alternatives requiring context or review; no later sample erases earlier values. Ordering uses server timestamps when all sources supply them, otherwise archive session order. These field lists are practical coverage expectations, not a universal game-data schema.

Relationships contain `subject`, `predicate`, `object`, `contextId`, `status`, attributes and supporting source paths. Examples include vendor offers/costs, quest rewards, recipe outputs/reagent options, talent/spell links, NPC spellcasts and candidate loot sources. Temporal proximity alone does not produce an edge. Item-linked spell APIs do not establish whether an effect is an on-use, equip or proc effect.

`coverage` retains record/entity counts, missing reasons, explicit scan scopes, recording boundaries and session diagnostics. `gameDatabaseCompleteness` is null because the complete game-content denominator is unknown. A completed scan only means its stated scope was read successfully.

## Expanded collection

- Storage snapshots include equipped slots, carried/reagent containers, and bank tabs only while the bank is open and the client permits viewing. Quantities are observed storage, not acquisitions. Existing bag count-change records remain a separate stream.
- Recipe scans process a bounded number per callback and retain a final `recipe.scan` manifest. The guarded `GetAllRecipeIDs` probe has an unverified runtime contract; the source-verified filtered fallback reports filtered scope and leaves the player's filters unchanged. Schematics preserve quality variants, optional slots, quantities and recipe links when exposed. Craft results preserve operation IDs without inventing missing recipe attribution.
- Readable target/mouseover/nameplate NPC cast events produce NPC-to-spell links. Readable cast GUIDs deduplicate observations of the same cast across unit tokens. Missing cast identity remains explicit. Opened trainer, bank and flight interactions record observed services.
- Gathering records starts, failures and interruptions as well as successful casts. Readable cast identity can connect an outcome to its start; unreadable IDs never establish a match. Fishing cast success does not prove a caught fish. Generic Opening spells and training/skill-bonus spells are excluded from the build-specific gathering allowlist.

All new native collectors require validation in the supported client. Offline tests establish data-handling behavior, not live API availability.

## Chests and loot rates

Readable `GameObject` source GUIDs can establish a world-object identity in the export. Loot-source mapping remains an unverified candidate on the current profile. When a readable Object tooltip GUID exactly matches that source GUID, its observed label and bounded lines are retained; missing or mismatched tooltips do not supply a name. This does not establish chest classification, exact object coordinates, unopened chest discovery, respawn timing, or lock requirements.

`lootStatistics` organizes loot windows, slots and revisions without summing overlapping receipts. It deliberately leaves `dropRate` and `eligibleDenominator` null. Reliable rates still need validated source mapping, complete snapshots, explicit player eligibility, stable identity across reopened windows, and observations of eligible opportunities even when the desired item did not drop. More observed loot alone cannot supply that denominator.

## Retention and recovery

The exporter validates existing inputs and writes the merged archive before computing/publishing derived files. A projection error or interrupted publication leaves the newly retained evidence available for retry. Missing projections can be rebuilt; a missing archive can be recovered from the complete database projection and remaining evidence files. Conflicting observation IDs fail without silently replacing evidence.

Upgrades import available legacy categories, dated snapshots and the prior latest save. `retention.priorCoverage` remains `unknown`: records discarded before this upgrade cannot be recovered. Diagnostic counters merge monotonically so replaying an older save does not reduce reported gaps.

Individual file replacements are atomic, but the whole folder is not one transaction. Require matching `exportId` across the current publication and matching `historyId` across cumulative files before importing them together. Back up the export folder; generated files are evidence, not a substitute for backups. Files above the current 512 MiB per-file input ceiling fail explicitly rather than truncating history. Large collections will eventually need a partitioned archive or database backend.
