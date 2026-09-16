# ForeverTome documentation

This handbook explains how the WoW addon API works and how ForeverTome can use it to record useful gameplay observations. **WF** means World of Warcraft: Forever throughout.

It also includes a [client acquisition plan](05-acquisition/README.md) for inspecting the downloaded game and building catalogs of abilities, talents, zones, items, and other content. The client is not yet downloadable at the time of planning, as reported by the project owner; acquisition has not started.

The intended readers are addon developers, database and guide authors, testers, and people reviewing the project for the first time. No prior knowledge of WoW addon development is assumed in the foundations.

## Read this first

Research was performed on **2026-09-16**. There are **no WF runtime-verified capabilities yet**. We inspected pinned snapshots of Blizzard-authored UI source distributed through the community-maintained `Gethe/wow-ui-source` mirror. Those snapshots are reference evidence, not proof that WF exposes the same APIs to ordinary addons.

In particular, Retail and the mirror's `classic_titan` branch differ in event arguments, professions, and combat-log access. The latter branch's name alone does not establish that it is the WF client. See [client and evidence rules](01-foundations/client-and-evidence.md).

## Reading paths

| Your task | Start here | Then read |
| --- | --- | --- |
| Understand what we are building | [Runtime](01-foundations/addon-runtime.md) | [Capabilities](01-foundations/capability-matrix.md), [observation model](03-data/observation-model.md) |
| Implement a collector | [Event model](01-foundations/event-model.md) | [Restrictions](01-foundations/restrictions.md), [event catalog](02-api/event-catalog.md), relevant API chapter |
| Turn records into guides | [Quests](02-api/quests.md) | [Correlation](03-data/correlation.md), [worked example](examples/README.md) |
| Test a WF build | [Client identity](01-foundations/client-and-evidence.md) | [WF test plan](04-validation/wf-test-plan.md), [open questions](04-validation/open-questions.md) |
| Acquire data when the client arrives | [Acquisition plan](05-acquisition/README.md) | [Catalog](05-acquisition/catalog.md), [storage design](05-acquisition/storage-and-import.md), [launch checklist](05-acquisition/launch-checklist.md) |
| Develop without breaking recorded data | [Test harness strategy](06-testing/README.md) | [Invariants](06-testing/recording-invariants.md), [replay fixtures](06-testing/fixtures-and-replay.md), [PR workflow](06-testing/pr-workflow.md) |
| Maintain this handbook | [Sources](reference/sources.md) | [Maintenance rules](reference/maintenance.md) |

## Contents

### 1. Foundations

- [Client compatibility and evidence](01-foundations/client-and-evidence.md): builds, branches, and what “verified” means.
- [Addon runtime](01-foundations/addon-runtime.md): Lua, manifests, frames, startup, and the sandbox.
- [Event model](01-foundations/event-model.md): subscriptions, payloads, snapshots, timing, and asynchronous data.
- [Restrictions](01-foundations/restrictions.md): protected actions, taint, secret values, and restricted events.
- [Capability matrix](01-foundations/capability-matrix.md): what observations could answer the project's questions.

### 2. API reference by recording task

- [Event catalog](02-api/event-catalog.md): event names, reference arguments, and capture responsibilities.
- [Quests](02-api/quests.md): acceptance, objectives, dialogue, readiness, turn-in, and follow-ups.
- [Loot and items](02-api/loot-and-items.md): loot windows, source attribution, receipt, and item metadata.
- [Units and combat](02-api/units-and-combat.md): creature identity, sightings, death, and kill attribution.
- [Maps and location](02-api/maps-and-location.md): map IDs, coordinates, observer position, and missing locations.
- [Professions and world interactions](02-api/professions-and-world.md): recipes, crafting, gathering, gossip, and vendors.

### 3. Recording and export design

- [Observation model](03-data/observation-model.md): a proposed record contract and evidence vocabulary.
- [Correlation](03-data/correlation.md): joining observations without inventing causality.
- [Persistence and export](03-data/persistence-and-export.md): SavedVariables, data loss, upload boundaries, and retention.

### 4. Validation

- [WF test plan](04-validation/wf-test-plan.md): reproducible client checks and acceptance criteria.
- [Open questions](04-validation/open-questions.md): unresolved facts and what would resolve them.

### 5. Client data acquisition

- [Acquisition plan](05-acquisition/README.md): collection stages, priorities, work sequence, and deliverables.
- [Acquisition catalog](05-acquisition/catalog.md): 20 domains, desired fields, source candidates, and coverage limits.
- [Storage and import design](05-acquisition/storage-and-import.md): snapshots, decoded tables, normalized catalogs, provenance, and build changes.
- [Launch checklist](05-acquisition/launch-checklist.md): work to execute at download, login, gameplay, and import readiness.
- [Machine-readable acquisition backlog](05-acquisition/acquisition-backlog.json): prioritized collection targets and outputs; all remain planned.

### 6. Test harness and regression protection

- [Testing strategy](06-testing/README.md): what qualifies as protected behavior and the limits of offline confidence.
- [Harness design](06-testing/harness-design.md): production-code execution, strict fake APIs, clocks, scheduler, and test layers.
- [Fixtures and replay](06-testing/fixtures-and-replay.md): input traces, independently reviewed expected results, and reproducible failures.
- [Recording invariants](06-testing/recording-invariants.md): 16 rules protecting meaning, identity, ownership, history, and recovery.
- [Persistence and recovery tests](06-testing/persistence-and-recovery.md): save boundaries, serialization, migrations, imports, and capacity.
- [PR workflow and rollout](06-testing/pr-workflow.md): test-first implementation, required checks, intentional contract changes, and milestones.
- [Machine-readable regression matrix](06-testing/regression-matrix.json): 34 planned scenarios mapped to invariants, suites, and client validation cases.

### Reference and examples

- [Sources](reference/sources.md) and [machine-readable source manifest](reference/source-manifest.json).
- [Glossary](reference/glossary.md).
- [Documentation maintenance](reference/maintenance.md).
- [Worked example](examples/README.md) and [synthetic observation data](examples/quest-and-loot-session.json).

## How to interpret the pages

**Reference** means a fact found in the named source snapshot. **WF unverified** means we have not demonstrated it on WF. **Proposed design** means a ForeverTome engineering decision, not a Blizzard API guarantee. **Historical candidate** means an older interface or observed behavior that needs fresh verification.

API identifiers use their exact spelling. Source IDs such as `R-QUEST` link to immutable source files in the [source register](reference/sources.md). The glossary explains terms such as *unit token*, *GUID*, and *snapshot*.

For automated readers: start here, preserve those evidence labels, follow source links, and do not turn proposed record fields into claims about API return values. The source manifest and examples complement the prose; they do not override it.
