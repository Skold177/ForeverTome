# Launch acquisition checklist

[Acquisition plan](README.md) · [Catalog](catalog.md) · [Storage design](storage-and-import.md)

**Current state: awaiting client availability.** All collection checkboxes are intentionally unchecked. This is the proposed work order; no download, extraction, addon execution, or import has been performed.

## Before download

- [ ] Select a primary installed locale; record the choice instead of assuming all locales are present.
- [ ] Choose an isolated acquisition directory outside the Git repository and an artifact retention location.
- [ ] Prepare candidate archive/table tools, recording their versions and source commits. Treat support for WF as untested.
- [ ] Implement the manifest, inventory, schema-matching, and reporting steps in a later tooling change; follow the [storage contract](storage-and-import.md).
- [ ] Keep API/gameplay collectors disabled until their ordinary-addon capability checks pass.

The source documentation and backlog are ready now. Tool installation, extractor implementation, and real data collection remain separate work to execute when requested or when the client is supplied for the acquisition task.

## Gate 1: the client can be downloaded

### Preserve the input

- [ ] Identify the actual WF launcher product/channel and installation. Do not assume the existing `classic_titan` reference is the target.
- [ ] Record installation version/build/content identifiers and locale inventory.
- [ ] Confirm whether the download is complete or streaming/partial; preserve that distinction in coverage.
- [ ] Create an immutable input snapshot or isolated copies of the readable relevant artifacts before an update replaces them.
- [ ] Generate artifact hashes and a manifest; verify files did not change during capture.

**Deliverable:** a reproducible snapshot with known scope. A partly readable client is still useful, provided the missing portion is reported.

### Inspect the surface

- [ ] Inventory readable UI code, generated API files, table names/FileDataIDs, format/layout metadata, locales, and referenced assets.
- [ ] Compare API declarations with the handbook's R/T references; record new, removed, changed, and restricted candidates.
- [ ] Match candidate archive/table readers against the actual format using small representative files first.
- [ ] Record unsupported layouts, unreadable/encrypted files, missing file-name mappings, and provisional column meanings as separate outcomes.

**Deliverable:** `artifacts`, `tables`, API inventory, and a domain coverage report. A failure in one table family does not stop independent supported domains.

### Produce P0 catalogs

- [ ] Decode class/race/skill definitions and explicit links.
- [ ] Decode spell definitions and all available associated effects/costs/text/links.
- [ ] Identify the actual talent representation; preserve rank, choice, edge, and condition structures.
- [ ] Decode map/UI-map/area hierarchy and available floor/art/assignment data.
- [ ] Decode item definitions, effects, sets, requirements, and appearance references.
- [ ] Normalize each successfully decoded domain and generate unresolved-reference reports.
- [ ] Produce a short human summary listing entities found, scope, uncertain fields, and the next validation targets.

**Deliverable:** a first searchable static catalog, which may precede server login. Do not mark catalog entries as playable or obtainable merely because parsing succeeded.

## Gate 2: character login is available

- [ ] Record full `GetBuildInfo()`, project ID, locale, and addon permission results; reconcile them with installation metadata.
- [ ] Match the running build to the preserved input snapshot. Capture any changed source/cache inputs as another snapshot.
- [ ] Validate selected spellbook and spell metadata APIs, including asynchronous text readiness and readable outputs.
- [ ] Inspect a talent configuration/tree if exposed at the character's level; record locked/unavailable trees explicitly.
- [ ] Compare selected maps and player coordinates with the UI using known map identities.
- [ ] Compare representative item metadata/links and contextual tooltips against decoded definitions.
- [ ] Confirm that runtime samples retain character context without exporting personal identifiers.

**Deliverable:** a runtime comparison report with matches, contradictions, and untested contexts. Use the [WF validation plan](../04-validation/wf-test-plan.md) for addon lifecycle, restrictions, persistence, and domain behavior.

### Track coverage across characters and views

Maintain a coverage matrix with one row per tested context, including opaque test-character label, class, race, faction, specialization if present, level/unlock stage, relevant profession/rank, locale, build, UI view/filters, and scenario. These fields explain visibility; they are not a roster to publish.

Begin with one accessible representative context, then schedule missing classes/talent systems and faction-specific content. Do not require a character for every combination before extracting the independent static catalog. Do not report a system absent because one low-level character cannot see it.

## Gate 3: gameplay content is accessible

- [ ] Capture profession/recipe views, learning, and craft outcomes using the actual WF interface.
- [ ] Capture quest offers, objective snapshots, readiness, turn-in, and follow-up offers separately.
- [ ] Record NPC and world-object sightings with observer-location semantics.
- [ ] Record vendor/trainer offers, requirements, prices, currencies, stock, and interaction context.
- [ ] Test loot visibility, source mapping, and receipt separately, including automatic and multi-source looting if supported.
- [ ] Inspect travel services and instance/journal views for their actual scope; record route availability and observed timings separately.
- [ ] Process P1/P2 domains whose local definitions were available, retaining unsupported/missing-system results.
- [ ] Create specific investigations for new WF UI modules/table families rather than guessing their purpose.

**Deliverable:** observations linked to the static catalog, plus a prioritized list of missing acquisition sources, prerequisites, locations, and system meanings.

## Gate 4: a reviewable database import exists

- [ ] Manifest, hashes, parser/schema/normalizer revisions, and source references are complete.
- [ ] IDs remain scoped by product and entity namespace; all relevant multi-row/array/graph structure is preserved.
- [ ] Each output domain has a coverage report; missing/unreadable data is not represented as an empty complete dataset.
- [ ] Unresolved links and contradictory values are visible and retain source evidence.
- [ ] Representative spell, talent, world, item, and available profession/quest records have validation notes.
- [ ] Localized text and symbolic descriptions are preserved; derived display values are labeled.
- [ ] Import retries are idempotent; malformed input cannot execute code.
- [ ] The batch includes a human-readable summary and machine-readable inventory/change reports.

**Exit criterion:** a traceable import batch with truthful per-domain scope. This does not require every server-side relationship to be known, and does not automatically publish guides.

## Every subsequent build or observed hotfix change

- [ ] Capture new artifact/overlay state before replacing the prior snapshot.
- [ ] Reuse the extraction pipeline with pinned dependencies; record changed tool/schema revisions.
- [ ] Compare equivalent source scope, locale, and domain populations.
- [ ] Separate source-data changes from parser interpretation changes.
- [ ] Recheck affected ability, talent, map, item, or API examples in the game when accessible.
- [ ] Prioritize gameplay collection around changed/newly cataloged content.
- [ ] Preserve prior snapshots and evidence; do not silently rewrite the historical dataset.

## Triage when something is missing

| Result | Next action |
| --- | --- |
| Client not available | Keep the plan ready; no acquisition result is claimed |
| Partial download or missing file | Record scope, finish authorized installation/update, then inventory again |
| File readable but unknown layout | Preserve source/header/hash; add a schema investigation; continue other domains |
| Column meaning provisional | Retain native field and provisional status; do not populate a falsely precise normalized field |
| API absent, denied, or secret | Mark that runtime path unavailable; keep supported file/observation paths separate |
| Data only visible in an interaction | Add the relevant gameplay collection scenario |
| No explicit relationship | Preserve entities and unresolved link; gather evidence rather than inventing an edge |
| Table/UI disagree | Keep both with snapshot and character context; investigate before resolving |

The immediate objective is coverage we can measure and explain. The checklist should advance by evidence, not by filling every cell with a guessed value.
