# WF client acquisition plan

[Documentation index](../README.md)

**Status: planned, awaiting the WF client download.** No WF files or gameplay data have been collected. Reviewed on 2026-09-16.

The first acquisition goal is a **build-specific catalog of abilities, talent trees, zones, items, and related definitions**, followed by gameplay evidence that establishes how those definitions are used. We should preserve the first downloadable build before updates change it, then make each later build comparable.

## What to read

| Document | Purpose |
| --- | --- |
| [Acquisition catalog](catalog.md) | What to collect in each domain, likely sources, output fields, and limits |
| [Storage and import design](storage-and-import.md) | How raw files, normalized catalogs, relationships, observations, and build changes fit together |
| [Launch checklist](launch-checklist.md) | Executable work order and acceptance criteria once the client is available |
| [Acquisition backlog](acquisition-backlog.json) | Machine-readable priorities, dependencies, source candidates, and expected outputs |

The existing [API handbook](../README.md) covers the addon side. This plan adds an external client-data inspection workflow. It does not assume an addon can read the installation archives or call arbitrary network services.

## Three collection stages

| Stage | Unlock condition | What we can attempt immediately | What still needs evidence |
| --- | --- | --- | --- |
| **Download** | An installed/downloaded WF build is available | Identify build; inventory readable archives and files; inspect UI/API code; extract accessible database tables, strings, and asset references | Whether each definition is enabled, obtainable, or used on the server |
| **Login** | A character can enter the game and addon access is established | Capture readable spellbook, talent UI, map, quest-log and other exposed state; compare displayed values with extracted definitions | Unseen classes, locked systems, unavailable areas, and character-specific conditions |
| **Gameplay** | The relevant content/interaction is accessible | Observe quests, loot sources, NPCs, nodes, trainers, vendors, routes, learning requirements, and world changes | Exhaustive coverage, drop probabilities, mandatory prerequisites, and hidden server rules |

These are access gates, not dates or guaranteed turnaround estimates. A preload may unlock the first stage before login is possible. Some packaged files may remain unavailable or undecodable after download; record that per artifact and continue with readable domains.

## Collection priorities

**P0: preserve the build and establish the core catalog.**

- Client identity, accessible file/table inventory, UI/API surface, and extraction provenance.
- Classes, races, available specialization/skill identities, and their explicit relationships.
- Spells and abilities: names, descriptions, effects, costs, ranges, durations, and links to classes/skills where present.
- Talent trees: nodes, entries, ranks, spell links, prerequisites, costs, conditions, and layout.
- World structure: maps, zones, subzones, floors, map artwork references, and supported coordinate relationships.
- Items: identity, names, categories, requirements, effects, equipment attributes, sets, and appearance references.

**P1: make those catalogs useful for guides.** Collect profession/recipe definitions; available quest definitions; creature/object metadata; factions; travel and instance definitions; localized text and useful icons; and every newly discovered WF system. Begin observational collection of vendors, trainers, loot relationships, objectives, and locations as soon as gameplay allows.

**P2: extend breadth.** Collect currencies, achievements, mounts, pets, and other collections if WF exposes them. A missing system is a recorded coverage result. We should not assume that a feature present in Retail exists in WF.

The [catalog](catalog.md) specifies the exact desired fields and likely method for each category. The [backlog](acquisition-backlog.json) records the same priority ordering for execution.

## Work sequence and deliverables

| Pass | Work | Deliverable / exit condition |
| --- | --- | --- |
| 0. Prepare now | Agree on directories, identifiers, manifests, priorities, and missing-data reasons | This plan and backlog; no fake WF records |
| 1. Preserve and inventory | Record the actual build, copy readable source artifacts into an isolated workspace, hash them, inventory tables and UI files | Build manifest, artifact inventory, extraction coverage report |
| 2. Decode P0 definitions | Match supported file formats/layouts; export readable rows; normalize IDs/text/relationships | Versioned spell, talent, map, item, and character-taxonomy catalogs, with unresolved fields retained |
| 3. Cross-check after login | Validate addon permission and signatures; compare selected catalog records with readable UI | Runtime sample report; contradictions and context-dependent values kept separately |
| 4. Expand P1/P2 | Process additional tables; perform targeted permitted reads and normal gameplay observations | Broader catalog plus a concrete list of missing relationships/content |
| 5. Publish a reviewable import batch | Validate references, coverage, localization, and evidence; generate human summaries | Import-ready data and review reports; publication is a separate workflow |
| 6. Repeat on patch/hotfix | Preserve another snapshot, rerun deterministically, compare like-for-like scopes | Added/changed/missing-from-snapshot report and new validation targets |

Parsing one unknown talent layout must not block a supported map or spell extraction. Each domain advances independently once its own dependencies are satisfied.

## Tools to evaluate when the build arrives

For CASC archives, [CascLib](../reference/sources.md#d-casc) is a candidate reader. For DBC/DB2 tables, [DBCD](../reference/sources.md#d-dbcd) and [WoWDBDefs](../reference/sources.md#d-dbd) provide candidate parsing/schema support. Their support for WF's eventual format and layouts has **not** been tested. Record exact versions/commits of the tools actually used.

Use the installed client's readable content as input. Preserve files that cannot yet be decoded, along with their identity and failure reason. If access is unavailable, report it; this plan does not depend on bypassing encryption, altering the client, inspecting process memory, or reconstructing secret addon values.

## What “complete” will mean

We can report **complete extraction of a named readable table in a named snapshot** when row counts and parser checks support it. We cannot turn that into “all playable WF spells” or “every obtainable item.” A client can contain shared, unused, deprecated, hidden, or future definitions.

Each domain report must state:

1. What source population was inspected: files/tables, UI views, or gameplay sessions.
2. What was extracted, skipped, unavailable, or undecodable.
3. Which fields/relationships have confirmed meanings and which remain provisional.
4. Which records were observed in WF gameplay and under what conditions.
5. What the next collection action should be.

The first useful result is a searchable, traceable catalog with honest coverage, even while gameplay relationships are still incomplete.
