# ForeverTome

ForeverTome records gameplay observations for the World of Warcraft: Forever item, creature, quest, spell, and talent database. Play normally; the addon keeps an ordered history with IDs, timestamps, locations, client build, and evidence for external tools to reconstruct later.

**Version 0.2.0 targets Forever Beta 1.60.1, build 69893.** Its API profile comes from the installed client's extracted source. Offline replay and export tests are implemented; loading, permissions, event timing, performance, and native saving still need validation in game. Unknown builds preserve saved data and restrict collection to lifecycle information until a profile is reviewed.

## Install and record

Copy the `ForeverTome` directory into the selected client's `Interface/AddOns` directory, or run from this repository:

```powershell
py tools/package.py --install 'D:\World of Warcraft\_classic_beta_'
```

This also builds `dist/ForeverTome-0.2.0.zip`. It copies addon files without changing SavedVariables or game settings. Restart the client if the addon was installed while it was running, enable ForeverTome in the AddOns list, and log in. Recording starts automatically.

The TOC interface value `16001` is derived from version 1.60.1 and is **provisional**. Check `/dump GetBuildInfo()` in game. If its fourth result differs, package with `--interface <measured-number>`; changing the manifest does not admit a different client build. [Client evidence](docs/implementation-client.md) explains the distinction.

| Command | Effect |
| --- | --- |
| `/ft` or `/ft status` | Show recording state, profile, observation count, storage, catalog progress, and pending spell reads |
| `/ft dump` | Scan accessible player/pet spells and talent trees into the recording |
| `/ft pause`, `/ft resume` | Pause/resume with a coverage gap and fresh state baselines |
| `/ft save`, `/ft export` | Show save/export instructions |
| `/ft clear confirm` | Explicitly delete local history and start a new recording session |

Use **`/reload` or normal logout** to save observations to disk. Recording in memory is not a disk flush; a crash can lose unsaved play. Export before clearing. The addon never automatically evicts unexported observations.

## What it records

| Stream | Observations |
| --- | --- |
| Quests | Existing-log baseline, actual acceptance, distinct repeatable runs, text, objective snapshots/changes, ready state, reward dialogue/choices, explicit turn-in, removal with unknown reason |
| NPC interactions | Gossip text/options, offered/active quests, quest greetings, readable interacting creature identity |
| Loot | Separate loot interactions, item/money/currency slots, slot changes/clearing, target and mouseover candidates, explicit unknown-source status |
| Items | Observed links/variants, IDs, quantities, asynchronously loaded metadata, localized self-receipt messages without social payloads |
| Inventory | Carried bags 0–4, aggregated item counts/changes; bag movement does not become acquisition |
| Creatures | Target, mouseover, and nameplate sightings; readable IDs, names, level, type, classification, dead state, native entity position when available |
| Travel/world | Player location at each observation, map/zone/subzone/instance context, periodic route samples and stationary heartbeats |
| Vendors | NPC context, offers, prices, bundle size, stock, readable extended costs |
| Player activity | Level/XP/money/group-size snapshots, death/alive/combat-state events, readable successful player spells and spell metadata |
| Spells | Player/pet spellbooks including passive and future entries, readable flyouts, known/override state, IDs, names, descriptions, icons, cast times, range, and separately labeled current costs/cooldowns |
| Talents | Accessible class tree structure, node layout, connections, choices, conditions, costs, rank descriptions, linked spells, and selected build snapshots |
| Professions | Viewed profession state, reported newly learned recipes with readable schematics/reagents, reported crafting results |

Locations identify their subject: player map coordinates are an observer location, not an exact monster spawn. Native unit positions are separately labeled. Quest deltas link before/after snapshots without claiming that a nearby creature caused progress. Loot visibility, cleared slots, inventory gains, and personal receipt remain separate facts.

The current client restricts the combat-log feed, and no supported loot-source mapping contract was found in its extracted UI. Direct kill tracking and confirmed creature-to-drop attribution therefore remain unavailable. Loot target/mouseover snapshots are explicitly **candidates**. The addon does not infer drop rates, quest prerequisites, or causality from timing alone.

This records exposed gameplay evidence, not every server action. It excludes private conversations, player names/GUIDs, Battle.net identifiers, arbitrary raw event payloads, and inaccessible values. Recipe capture covers the viewed profession and newly learned recipe IDs; it is not a complete catalog scan. See [coverage and schema](docs/implementation.md) for limits.

Spellbooks and talents are sampled automatically on entering the world and relevant changes. To explicitly dump them, run `/ft dump`, then `/ft status`. Wait until both scans are idle and pending spell reads reach zero, then `/reload`. The scan status reports complete or partial coverage; missing information remains labeled in the export. This captures trees and spells exposed to the current character, including readable unselected talents. Collect on other classes to expand coverage; the addon does not switch your specialization or fetch a server-wide spell catalog.

## Export for tooling

After saving, copy the account file from the actual client path, expected to be:

```text
D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua
```

Confirm that the client creates it on the first save. Then:

```powershell
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.json'
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.jsonl' --format jsonl --sqlite 'C:\Exports\evidence.sqlite'
```

The exporter uses a restricted data parser; it never executes saved Lua. JSON retains complete evidence, and JSONL supplies export/session/observation records. Optional SQLite import is transactional and idempotent: identical IDs are ignored, conflicting content is rejected. Outputs do not overwrite existing exports. No data is uploaded automatically.

## Development

Python 3.10+ and Lua 5.1 or compatible LuaJIT are required:

```powershell
py tools/test.py
py tools/package.py
```

Tests load production files in TOC order through a deterministic fake game host, exercise errors/reload/export, and verify that deliberate recording defects fail the gate. Synthetic tests are not proof of native client permissions or persistence.

[Implementation contract](docs/implementation.md) · [Client evidence/export](docs/implementation-client.md) · [Quest collector](docs/implementation-quests.md) · [Spell collector](docs/implementation-spells.md) · [Talent collector](docs/implementation-talents.md) · [API research handbook](docs/README.md)
