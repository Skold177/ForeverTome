# Organizing acquired client data

[Acquisition plan](README.md) · [Catalog](catalog.md)

**Status: proposed storage and processing design.** The directories and records below do not yet exist. This extends the gameplay [observation model](../03-data/observation-model.md) with catalogs acquired outside the addon.

## Keep source, interpretation, and observation separate

| Layer | Contents | Why it exists |
| --- | --- | --- |
| Source artifacts | Unmodified readable files, manifests, UI code, local cache snapshots where applicable | Reproduce extraction and revisit unknown formats |
| Decoded tables | Rows/columns as interpreted by a specific parser and schema revision | Audit parsing independently of our entity model |
| Normalized catalogs | Typed spell, talent, map, item, and other records | Search, compare, and import useful entities |
| Relationships | Explicit or inferred links with evidence and conditions | Avoid hiding assumptions inside a flattened entity |
| Runtime samples | Readable UI/API snapshots with character/context metadata | Check effective displayed values and availability |
| Gameplay observations | ForeverTome event records and their evidence | Establish actual encounters, sources, progress, and outcomes |
| Reports | Coverage, unresolved references, contradictions, and changes | Make each acquisition reviewable by a human |

An extracted spell definition and a player's spellbook entry are different records. Neither should overwrite the other.

## Proposed filesystem layout

Use a dedicated acquisition workspace outside this source repository. Keep documentation, schemas, importer code, and small synthetic fixtures in Git; keep real client artifacts and large exports in data storage.

```text
<acquisition-root>/wf/
  snapshots/
    <content-snapshot-id>/
      manifest.json
      inventory/
        artifacts.jsonl
        tables.jsonl
        locales.json
      raw/
        ui/
        tables/<locale>/
        cache-overlays/<locale>/
        assets/                 # selected referenced files, if needed
  processing/
    <processing-run-id>/
      run.json                  # input snapshot and tool/schema revisions
      decoded/<locale>/<table>.jsonl
      catalog/
        classes.jsonl
        races.jsonl
        spells.jsonl
        spell_effects.jsonl
        talent_trees.jsonl
        talent_nodes.jsonl
        talent_entries.jsonl
        talent_edges.jsonl
        maps.jsonl
        areas.jsonl
        ui_maps.jsonl
        items.jsonl
        ...                     # named outputs in the acquisition backlog
      localization/<locale>.jsonl
      relationships/<relationship-type>.jsonl
      reports/
        summary.md
        coverage.json
        unresolved-references.jsonl
        contradictions.jsonl
        validation.json
        changes-from-<prior-run-id>.jsonl
  runtime-samples/<sample-batch-id>/
  observations/<export-id>/
  import-batches/<batch-id>/
```

JSON Lines (`.jsonl`) means one JSON record per line, allowing streaming and partial-domain processing. Use UTF-8, deterministic ordering, explicit scalar types, and plain source text. A future database or columnar export can be derived from this canonical staging representation.

Do not create a production-sized Git directory to hold the client. Do not store account names, character-identifying installation paths, or machine-specific secrets in published manifests.

## Three identities to retain

1. **Client build:** measured version/build/product identity. Before login, label the value as installation-metadata evidence; after login, attach the matching `GetBuildInfo()` result.
2. **Content snapshot:** the precise source artifacts and relevant overlay state captured at a time, identified by a manifest and hashes.
3. **Processing run:** the parser/schema/normalizer versions used to interpret that snapshot.

The same build can acquire different readable cache/hotfix state over time. The same snapshot can be reprocessed with improved definitions. Keep those changes distinct from a new client build.

## Snapshot manifest

Record at least:

| Field | Meaning |
| --- | --- |
| `content_snapshot_id` | Stable identifier for this immutable acquisition |
| `product`, `channel` | Measured launcher/client product and test/live channel; unknown remains unknown |
| `client_version`, `client_build`, `interface_version` | Measured values, with evidence source and unresolved values retained |
| `captured_at_utc` | Time of the acquisition, not an invented release time |
| `content_identifiers` | Build/config/content hashes exposed by the installation, if present |
| `locales` | Locales actually inventoried; not all locales the game might support |
| `artifacts` | FileDataID/path/table identity, byte count, hash, and extraction outcome |
| `overlay_state` | Available cache/hotfix inputs, their timestamps/hashes, or explicit unknown coverage |
| `capture_scope` | Installation population, relevant filters and incomplete-download conditions |

Hash extracted readable files with a named algorithm such as SHA-256. Record the algorithm and digest; do not substitute timestamps or filenames for content identity. Preserve the archive/file identifier as well as a readable filename, because name-to-file mappings may be incomplete.

## Decode with matched schemas

Inventory first. Identify each table's format, build/layout metadata where present, and applicable definitions. [WoWDBDefs](../reference/sources.md#d-dbd) is a community schema source, not a guarantee that all column meanings are established. Its provisional field annotations must remain provisional in our decoded output. [DBCD](../reference/sources.md#d-dbcd) is a candidate reader; its declared format support and dependency on matching definitions must be checked for WF.

Preserve row IDs, relationship keys, array elements, record copies/aliases, sections, localized values, and format metadata where supported. Do not assume contiguous IDs, one physical row per logical entity, or identical layouts across adjacent builds.

If no trustworthy layout is available, keep the source artifact and header information with `decode_status = unsupported_layout`. Do not pick a nearby Retail schema because the column count looks similar. A decoder producing rows is only the beginning: type, count, index, string, and relationship checks must also pass.

If supported cache overlays are readable, decode them as separate inputs with their own provenance. Preserve base values, updates, and explicit deletion markers; construct an effective view only when the application semantics are established. No accessible cache proves coverage of all server hotfixes.

## Entity identity and localization

Use a logical content key `(product, entity_type, native_id)`. A versioned catalog row adds `content_snapshot_id` and `processing_run_id`. Keep the original table/row key even when our entity combines several source rows.

Different namespaces stay distinct: `spell:123` is not `item:123`; `ui_map:123` is not `area:123`. A talent node, talent entry, and spell each retain their own identities. A creature template, entity GUID, display ID, and model ID are different things.

Represent localized fields using `(snapshot, entity_type, native_id, locale, field_name)`. Preserve original strings/tokens and an optional derived search/display representation separately. A fallback English label must not be marked as a native translation.

Within an export, include enough build and processing context to interpret the row. Never merge WF content into a Classic/Retail entity just because a name or numeric ID matches. Cross-product resemblance can be an explicitly labeled comparison, not identity.

## Provenance for fields and relationships

Every normalized record needs source artifact IDs and table/row references. A field assembled from several sources needs field-level provenance or a link to a reproducible derivation rule. Useful fields include `source_kind`, `source_refs`, `rule_id`, `rule_version`, `context`, and `meaning_status`.

| Source kind | Meaning |
| --- | --- |
| `client_table` | Value decoded from a readable client table |
| `client_ui_source` | API declaration or UI constant/call-site evidence |
| `runtime_api` | Readable value observed through an ordinary addon/API in a stated context |
| `gameplay_observation` | Permitted event/state record captured during play |
| `derived` | Computation or association based on referenced inputs |

Separate extraction state from gameplay availability. For example, `decode_status = decoded` can coexist with `availability_status = unobserved`. Proposed availability values are `unobserved`, `observed_in_context`, and `explicitly_unavailable_in_context`; no single character's failure makes an item globally unavailable.

Store a relationship's source and destination entity keys, relationship type, direction, rank/order if applicable, conditions, and evidence. An unresolved destination is an unresolved reference, not a reason to discard its source row or join to an entity with a similar name.

## Special handling for the main catalogs

| Catalog | Structure to preserve |
| --- | --- |
| Spells | Multiple ordered effects/costs; explicit associations; symbolic text distinct from context-dependent UI values |
| Talents | Trees, nodes, choices/entries, ranks, typed edges, costs, conditions and spell definitions; separate purchased-rank/configuration samples |
| World | Internal maps, UI maps, areas/subareas and floors; named coordinate systems and verified transforms |
| Items | Item definitions, effects, sets and variants; dynamic tooltip stats and acquisition evidence separately |
| Recipes | Reagent groups/alternatives, output variants/quantities and requirements; craft attempts/results separately |
| Quests | Partial definition fragments and stable native objective IDs if supplied; runtime array indices and observed runs separately |

Conditions should retain their native representation when semantics are unknown. Do not simplify an AND/OR prerequisite, choice gate, or rank requirement into a plain untyped arrow.

## Coverage and validation reports

For each domain/table, report found artifacts, readable artifacts, decode successes/failures, decoded row count, unique native IDs, normalized entity count, localized-field coverage, unresolved references, and UI/gameplay sample coverage. These counts describe different populations and need not be equal.

Validate representative records by source category and complexity: a passive and active spell; a multi-effect ability; a multi-rank and choice talent; an outdoor map and floor; a consumable and equipment item; a recipe with multiple requirements. Include new/changed candidates, not only familiar legacy records.

When runtime values disagree with tables, retain both with context. Investigate character scaling, overrides, localization, stale cache, hotfix state, decoding, and field meaning. Do not automatically prefer a tooltip over base data or a table over observed effective behavior.

## Build changes and imports

Compare equivalent domains/locales/scopes. Emit `added`, `field_changed`, `relationship_changed`, `text_changed`, and `missing_from_snapshot` results, with old/new values and provenance. Missing from an incomplete snapshot is not a deletion. Reserve removal claims for explicit evidence, or a clearly scoped complete comparison that supports them.

Do not label a first-seen ID “new to WF” without an appropriate prior WF baseline. In the initial import it is simply first cataloged. Parser/schema corrections should be reported as interpretation changes, separately from changed source bytes.

An import batch references the snapshot, processing run, schema version, data hashes, coverage report, and validation result. Import by stable versioned keys so retries are idempotent. Reject conflicting rows under the same identity, unknown incompatible schemas, and missing required provenance. Keep unresolved references importable as explicit unresolved relationships where the schema allows them.

Produce human summaries before generating guide-facing claims. The catalog can publish a definition with unknown availability; a guide's asserted source, prerequisite, or location requires the appropriate evidence from the [correlation rules](../03-data/correlation.md).
