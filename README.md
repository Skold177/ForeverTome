# ForeverTome

ForeverTome records gameplay observations for the World of Warcraft: Forever item, creature, quest, spell, and talent database. Play normally; the addon keeps an ordered history with IDs, timestamps, locations, client build, and evidence for external tools to reconstruct later.

**Version 0.2.3 targets Forever Beta 1.60.1, build 69893.** Its API profile comes from the installed client's extracted source. Live saved data confirms quest acceptance links, objective progress, turn-in dialogue links, native quest-item receipts, loot capture, and persistence in this build. Item stats and tooltip capture have offline regression coverage and still need an in-game test. Unknown builds preserve saved data and restrict collection to lifecycle information until a profile is reviewed.

## Install and record

Copy the `ForeverTome` directory into the selected client's `Interface/AddOns` directory, or run from this repository:

```powershell
py tools/package.py --install 'D:\World of Warcraft\_classic_beta_'
```

This also builds `dist/ForeverTome-0.2.3.zip`. It copies addon files without changing SavedVariables or game settings. Restart the client if the addon was installed while it was running, enable ForeverTome in the AddOns list, and log in. Recording starts automatically.

The TOC interface value `16001` matches the live client's recorded `GetBuildInfo()` result. For a different measured interface, package with `--interface <measured-number>`; changing the manifest does not admit a different client build. [Client evidence](docs/implementation-client.md) explains the distinction.

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
| Quests | Existing-log baseline, actual acceptance, distinct repeatable runs, text, objective snapshots/changes, ready state, reward dialogue/choices, explicit turn-in, native quest-item receipts, removal with unknown reason |
| NPC interactions | Gossip text/options, offered/active quests, quest greetings, readable interacting creature identity |
| Loot | Separate loot interactions, item/money/currency slots, slot changes/clearing, target and mouseover candidates, explicit unknown-source status |
| Items | Observed links/variants, IDs, quantities, icon references, basic metadata, available stat tokens/values and readable tooltip lines, localized self-receipt messages without social payloads |
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

## Export a website catalog

To organize saved observations into item, quest, NPC, spell, talent, and other catalogs with linked event records:

```powershell
py tools/build_catalog.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\website-catalog.json'
```

Use a new destination filename; add `--compact` for smaller JSON. The output preserves source evidence and item variants, with separate `transactions` and `observations` lists. It does not infer loot sources, combine overlapping acquisition channels, or supply uncaptured item stats. This is a local staging file for a future website importer; nothing is uploaded. See the [catalog format and examples](docs/website-catalog.md).

To convert every new save automatically while playing:

```powershell
py tools/watch_catalog.py 'D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua' --output-dir 'C:\Exports\ForeverTome'
```

The watcher checks every two seconds and maintains `spells.json`, `talents.json`, `items.json`, `quests.json`, `monsters.json`, `npcs.json`, and `gathering.json`, plus the full `latest.json` and dated snapshots. Each category retains detailed captured fields and supporting records. Shared export IDs identify files from the same save. Gathering records supported successful harvesting, mining, and skinning casts with the player's observed location; resource identities and exact node positions remain unknown.

It waits for WoW to save through `/reload` or logout, retries incomplete saves, and stops with Ctrl+C. Individual files are replaced atomically; consumers reading several files should require matching export IDs. Nothing is installed to run at Windows startup.

## Development

Python 3.10+ and Lua 5.1 or compatible LuaJIT are required:

```powershell
py tools/test.py
py tools/package.py
```

Tests load production files in TOC order through a deterministic fake game host, exercise errors/reload/export, and verify that deliberate recording defects fail the gate. Synthetic tests are not proof of native client permissions or persistence.

[Implementation contract](docs/implementation.md) · [Client evidence/export](docs/implementation-client.md) · [Quest collector](docs/implementation-quests.md) · [Spell collector](docs/implementation-spells.md) · [Talent collector](docs/implementation-talents.md) · [API research handbook](docs/README.md)
