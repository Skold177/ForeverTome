# Build a website catalog

`tools/build_catalog.py` turns saved ForeverTome observations into one JSON file with searchable entity catalogs and an ordered event history. It reads a saved file, validates it with the existing restricted Lua data parser, and writes a separate output. It never executes Lua, changes SavedVariables, or connects to the website.

This is a staging format for a future website importer. ForeverTome's website does not currently have an upload endpoint or item/quest database importer.

## Quick start

Use `/reload` or normal logout to save, then copy the account's `SavedVariables/ForeverTome.lua` to an export directory. From this repository, run:

```powershell
py tools/build_catalog.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\website-catalog.json'
```

Add `--compact` to omit JSON indentation. The destination must not already exist; choose a new filename for each export. Identical source bytes produce identical output with the same formatting option. The tool does not upload anything.

Keep real recordings and generated files outside Git or under this repository's ignored `artifacts/` directory. Only synthetic fixtures belong in tests.

## Automatic conversion

Open [ForeverTome Exporter](desktop-exporter.md), choose the save and output folder, and click **Start watching** to convert new saves while its window is open. **Stop watching** pauses the checks; closing the window exits after any current conversion finishes. It does not run in the tray or start with Windows.

For scripts, the same conversion is available through a command-line watcher:

```powershell
py tools/watch_catalog.py 'D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua' --output-dir 'C:\Exports\ForeverTome'
```

It checks the saved file every two seconds. Each new save appends evidence to the existing category JSON files and replaces `latest.json` with the complete current save. Identical source content is skipped, including after restarting the watcher. The category files retain previously exported history when the addon is cleared or SavedVariables is replaced with a newer recording. Export successfully before clearing the addon, and keep using the same output folder. The watcher no longer creates dated `catalog-*.json` snapshots.

The same folder contains separate `items.json`, `spells.json`, `talents.json`, `quests.json`, `npcs.json`, `monsters.json`, and `gathering.json`. Each uses `format: "forevertome.catalog-category"` with a `category`, cumulative `entries`, supporting `records`, and the relevant `sessions` and `contexts`. New evidence is merged by stable IDs; repeated observations are kept once, and conflicting content under the same observation ID is rejected. Records include every referenced observation and its related-record dependencies, preserving locations, capture times, variants, and partial reads. Entity links may point into another category; resolve them by stable entity keys. The [category schema](../schemas/catalog-category-v1.schema.json) describes the envelope.

The watcher writes all JSON files with two-space indentation and line breaks. On the first export with generator version 0.2.5, it backfills category history from existing dated snapshots and `latest.json`, even when the saved recording is unchanged. Original snapshots remain untouched. Later exports append new evidence to the categories.

Each file publishes atomically. The categories share `exportId` and `generatorVersion` with `latest.json`; an importer reading multiple files must check that their export IDs agree. These values and the category's `source` identify the latest processed save and generator, not the complete accumulated history. `latest.json` and the desktop summary describe only the current save. A partial multi-file update is retried on the next check.

Treat generated files as read-only and keep backups of the category files. They may contain historical evidence that is no longer present in SavedVariables or `latest.json`; deleting a category can lose that history.

`npcs.json` contains all recorded creature identities. `monsters.json` is a view of those observed with a hostile or neutral reaction (1 through 4) to the player. It is not a universal creature classification, and a creature can appear in both files with the same stable identity.

`gathering.json` contains successful player herbalism, mining, and skinning cast observations recognized for build 69893. Each occurrence retains its spell, timestamp and available player position. These are gathering activity points, not confirmed resource-node coordinates or spawn locations; neither resource names nor received items are inferred. Training spells, skill books and generic Opening casts are excluded. The allowlist in `tools/catalog_gathering.py` was checked against the installed `SpellName`, `SpellEffect`, `SkillLineAbility`, and `LockType` tables. New builds need a reviewed rule. Cast success is already recorded by the addon, so matching historical casts can appear in this view.

WoW still has to flush its file through `/reload` or logout. The watcher cannot read unsaved game memory. An incomplete or invalid save leaves the last good JSON intact, and the watcher retries on later checks. It refuses to replace an unrelated `latest.json`. File paths and account folder names are not embedded in the export. Nothing is uploaded.

Use `--once` for a single synchronization or `--interval 5` to check less frequently. Press Ctrl+C to stop a foreground watcher. A background instance runs until stopped or Windows exits; this tool does not install a startup service. Use only one watcher per output directory.

The machine-readable format is [website-catalog-v1.schema.json](../schemas/website-catalog-v1.schema.json). The converter also validates IDs, provenance, context boundaries, source counts and all observation references before writing.

## Read the JSON

The envelope identifies `format: "forevertome.website-catalog"` and `schemaVersion: 1`. Its sections are:

| Section | Contents |
| --- | --- |
| `source` | Input SHA-256, source schema version, synthetic-data flag, and source observation count |
| `contexts` | Product, client version/build, and locale scopes used by records and entities |
| `sessions` | Recording session context |
| `catalog` | `items`, `quests`, `npcs`, `spells`, `talents`, `recipes`, `maps`, `professions`, and `currencies` |
| `transactions` | Recorded events, actions, and progress changes |
| `observations` | Metadata, snapshots, coverage, lifecycle, and other remaining records |
| `summary` | `kindCounts`, `catalogCounts`, `transactionCounts`, and `observationCount` |

Every source observation appears exactly once across `transactions` and `observations`. Here, a transaction means a classified event record, such as quest progress; it is not necessarily a purchase or a newly acquired item. Catalog entries reference these records instead of replacing them.

For example, inspect catalogued items and native quest rewards in PowerShell:

```powershell
$packet = Get-Content -Raw -LiteralPath 'C:\Exports\website-catalog.json' | ConvertFrom-Json
$items  = $packet.catalog.items
$quests = $packet.catalog.quests

$items | Select-Object key, nativeId, display
$quests | Select-Object key, nativeId, display
$packet.transactions | Where-Object type -eq 'quest.reward_received' | Select-Object id, sessionId, data, entities
$packet.summary | ConvertTo-Json -Depth 10
```

## Entity and record fields

Each entity has a stable `key`, `contextId`, `kind`, and `nativeId`. Product/build/locale context and entity kind distinguish identities; a spell ID is not an item ID. Catalog entities provide a display value, the full `details` from that same representative source fragment, its `displaySourceId`, and `sourceIds` linking back to the evidence. Reference-only entries have empty details until descriptive metadata is observed.

`facts` retain observed entity information as `{id, type, path, data, sourceIds}`. Their paths identify the source data fragment. Repeated observations can support the same fact; conflicting or contextual facts remain available for review. A display value is a convenience for listing an entity, not a claim that every captured fact is a universal definition.

Item `variants` use `{key, link, sourceIds}`. Exact item links remain separate variants; do not merge them solely because their base item IDs match.

Event and observation rows use these fields:

| Field | Meaning |
| --- | --- |
| `id`, `type` | Original observation identity and kind |
| `sessionId`, `contextId`, `sequence` | Recording scope and order |
| `elapsedSeconds` | Elapsed time within the recording session |
| `observedAt`, `observedAtUnix` | Server timestamp representations when the source supplied one |
| `location` | Original location context, when present, with derived `mapX`/`mapY` percentages where coordinates are available |
| `data` | Original observation payload; its field names and values remain intact |
| `capture`, `evidence`, `missingFields` | Capture method, evidence classification, and identified gaps |
| `relatedIds` | Explicit links to related observations |
| `entities` | Entity references as `{key, role, path}` |

An entity reference associates a data field with a catalog entry. Its role and path preserve how that entity occurred; an association alone does not prove a drop source, quest requirement, or cause of progress.

Generator 0.2.6 retains `loot.provenance` facts on items and identified creatures. These contain per-observation loot-session/slot IDs, source GUIDs and quantities, mapping status/method, and contextual candidates. Validated mapped sources use the `loot_source` entity role; unverified, partial, mismatched, and contextual associations use `loot_candidate`. A base item can have many sources, so provenance belongs to observations rather than a single permanent `looted_from` ID. Item and creature category files retain their shared loot records and related opening/slot evidence. Old recordings without these associations remain unknown; exporting cannot recover an uncaptured source.

## Interpretation limits

Native quest-item rewards, chat receipts, and inventory gains can describe the same acquisition. Keep their channels separate; summing them would double-count items. Explicit quest reward attribution comes from the native quest reward event. Nearby events and related NPCs do not supply missing attribution.

Locations preserve the observed subject. Player map coordinates, including derived percentages, locate the observer and are not monster spawn coordinates. Native entity positions remain separately labeled in the source data.

Older 0.2.2 recordings lack structured item stats and item tooltip text. Version 0.2.3 requests those fields for observed items and records readability status. The catalog cannot reconstruct missing fields from item IDs; they require a new capture. Item `display.stats`, `display.statLabels`, and `display.tooltipLines` expose recorded details from the referenced representative metadata snapshot; its exact item link and capture context remain available. Missing stats never become zeros. All exact variant facts remain available separately. Captured icon IDs and readable game paths remain references; a future website asset resolver must map them to image files or URLs.

Snapshots can be partial, and readable API values can depend on the character, selected variant, or sampling time. Preserve their scope, evidence, and missing fields when building website displays. Absence from an export does not mean that an entity was removed or is unavailable in the game.

Spell display fields include `castTimeMs`, `minRange`, `maxRange`, `description`, typed `currentState.power_costs`, current cooldowns/charges and readable tooltip lines when present. Power types and costs remain labeled; not every spell uses mana. Damage and effect text stays in the description/tooltip rather than becoming guessed numeric coefficients. Negative cast-time sentinels remain raw evidence but do not become displayed durations. Trait graph/rank details, quest narratives/objectives/reward choices, NPC descriptions, and item metadata remain available in details, facts, and supporting records.

## Future imports

The format version belongs to this catalog projection and is separate from the recorder's schema version in `source`. `source.sha256` identifies the exact input bytes. `generatorVersion` identifies the processing implementation and participates in `exportId`; bump it when a release changes projection behavior. A future importer should check versions, retain context and source references, and use stable observation and entity IDs for repeat imports. Re-importing an observation must not append a duplicate; conflicting content under the same observation ID should be rejected. Entity facts and sources can be merged by their identities without discarding earlier evidence.

Render captured names, descriptions, and links as untrusted text. Importing and publishing are separate steps from generating this local file.
