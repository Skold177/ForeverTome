# What ForeverTome can aim to observe

[Documentation index](../README.md)

**Status:** feasibility assessment from reference APIs; every WF capture path remains unverified. The linked domain chapters carry the source evidence and validation requirements.

| Player question | Candidate observation | What it can establish | What it cannot establish alone | Reference |
| --- | --- | --- | --- | --- |
| What creature did I encounter? | Readable GUID, name, classification, unit token at a sighting | This client observed this entity | Every creature nearby; its full spawn area | [Units](../02-api/units-and-combat.md) |
| Did a monster die? | Supported death event, or a readable dead-state sighting | Death notification or observed dead state, respectively | That this player killed it | [Combat](../02-api/units-and-combat.md) |
| Did I get credit for a kill? | Supported credit event or quest-objective delta | The specific credit reported by that source | A universal death/credit relationship | [Combat](../02-api/units-and-combat.md), [quests](../02-api/quests.md) |
| Where was it? | Map context and player position at observation time | Where the observer was | Exact monster/node coordinates | [Location](../02-api/maps-and-location.md) |
| What did it drop? | Loot slot with a validated source mapping | Items exposed by that loot source in this session | Full loot table, guaranteed drop rate, or personal receipt | [Loot](../02-api/loot-and-items.md) |
| What did I receive? | Supported receipt evidence and inventory delta | An item gain with stated evidence | Its source solely from a bag increase | [Items](../02-api/loot-and-items.md) |
| Which quest did I accept? | `QUEST_ACCEPTED` plus readable quest snapshot | An acceptance observed during recording | Earlier acceptance time for a quest present at login | [Quests](../02-api/quests.md) |
| Which objective advanced? | Comparable before/after objective snapshots | Counter or completion-state change | Which exact action caused it | [Quests](../02-api/quests.md) |
| Is the quest ready? | Quest completion/readiness state | The client reports readiness in this snapshot | Successful reward collection | [Quests](../02-api/quests.md) |
| Did I turn it in? | Validated `QUEST_TURNED_IN` | A reported turn-in with its quest ID | Every reward choice or the next quest in a chain | [Quests](../02-api/quests.md) |
| What steps lead to completion? | Ordered dialogue, objective, location, and turn-in observations | A route a player actually observed | Mandatory steps, shortest route, or all alternatives | [Correlation](../03-data/correlation.md) |
| Which quest comes next? | Subsequent offer and acceptance | Observed sequence/availability | A required prerequisite edge without more evidence | [Quests](../02-api/quests.md) |
| How is an item crafted? | Recipe snapshot and supported craft-result event | Recipe requirements or a specific result | WF support for Retail quality/recrafting systems | [Professions](../02-api/professions-and-world.md) |
| Where was a resource gathered? | Readable cast/interaction, loot, observer location | A gathering observation with stated attribution | All node positions or respawn timers | [Professions](../02-api/professions-and-world.md) |
| Who sells an item? | Open merchant inventory plus readable NPC context | An offered item and price at that time | Permanent stock, universal prices, or purchase outcome | [World interactions](../02-api/professions-and-world.md) |
| Can records be uploaded? | SavedVariables or user-copied export | Data available to an external importer | Direct addon HTTP access or guaranteed immediate disk durability | [Persistence](../03-data/persistence-and-export.md) |

## Initial implementation priority

**Proposed design:** validate startup/persistence first, then location, quests, loot visibility, and item metadata. Validate source attribution and professions next. Enable combat-derived records only if ordinary-addon access and payload meaning are demonstrated on WF.

This ordering gives us useful records even if direct kill capture is unavailable. It also makes the biggest uncertainty visible before building a database that assumes every loot item has a known killer and position.

## Coverage is part of the data

A recorder sees a player's partial view. It misses events during downtime, out of range, while disabled, or behind restrictions. Quest prerequisites and loot eligibility can depend on player state. Every export must preserve build, locale, capability status, and known recording gaps.

“No record” is not evidence of “never happens.” “Zero observed items” is not a failed drop roll unless the capture scope establishes that a complete eligible loot opportunity was observed.
