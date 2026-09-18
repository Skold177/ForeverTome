# ForeverTome

ForeverTome records gameplay observations for the World of Warcraft: Forever item, creature, quest, spell, and talent database. Play normally; the addon keeps an ordered history with IDs, timestamps, locations, client build, and evidence for external tools to reconstruct later.

**Version 0.3.0 targets Forever Beta 1.60.1, build 69893.** Its API profile comes from the installed client's extracted source. Live saved data confirms quest acceptance links, objective progress, turn-in dialogue links, native quest-item receipts, loot capture, and persistence in this build. New storage, recipe, NPC spell, gathering, and item-detail reads have offline regression coverage and still need in-game validation. Unknown builds preserve saved data and restrict collection to lifecycle information until a profile is reviewed.

## Install and record

Run **ForeverTomeSetup.exe** to install the desktop companion. Open its **Install / update addon** tab, select the detected WoW Forever folder, and click **Install / update addon** to install the latest merged addon from GitHub. You can browse to the game folder if detection misses it. The installer creates a Start menu shortcut and offers an optional desktop shortcut. See [desktop installation and usage](docs/desktop-exporter.md).

Keep the installed companion for future addon updates: every click fetches the current addon from `main`, including versions published after your installer was built. You do not need to download another installer to update the addon. The window reports the installed addon's own version.

The new observation kinds and database exports in this release require companion **0.3.0**. Update the companion once to use these export features; its addon update button installs addon files and does not upgrade the companion itself.

For a manual installation, copy the `ForeverTome` directory into the selected client's `Interface/AddOns` directory, or run from this repository:

```powershell
py tools/package.py --install 'D:\World of Warcraft\_classic_beta_'
```

This also builds `dist/ForeverTome-0.3.0.zip`; the filename follows the version in `ForeverTome/ForeverTome.toc`. It copies addon files without changing SavedVariables or game settings. Restart the client if the addon was installed while it was running, enable ForeverTome in the AddOns list, and log in. Recording starts automatically.

The TOC interface value `16001` matches the live client's recorded `GetBuildInfo()` result. For a different measured interface, package with `--interface <measured-number>`; changing the manifest does not admit a different client build. [Client evidence](docs/implementation-client.md) explains the distinction.

| Command | Effect |
| --- | --- |
| `/ft` or `/ft status` | Show recording state, profile, observation count, storage, catalog progress, and pending spell reads |
| `/ft dump` | Scan accessible spells, talents, storage, and the currently viewed profession |
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
| Items | Observed links/variants, IDs, quantities, icons, metadata, stats, readable tooltips, item-linked spells and socketed gems, localized self-receipts |
| Inventory | Carried bag count changes plus separate equipment, reagent-bag, and accessible open-bank snapshots; storage presence does not become acquisition |
| Creatures | Target, mouseover, and nameplate sightings; readable descriptors/positions, observed NPC spellcasts, and opened trainer/bank/flight services |
| Travel/world | Player location at each observation, map/zone/subzone/instance context, periodic route samples and stationary heartbeats |
| Vendors | NPC context, offers, prices, bundle size, stock, readable extended costs |
| Player activity | Level/XP/money/group-size snapshots, death/alive/combat-state events, readable successful player spells and spell metadata |
| Spells | Player/pet spellbooks including passive and future entries, readable flyouts, known/override state, IDs, names, descriptions, icons, cast times, range, and separately labeled current costs/cooldowns |
| Talents | Accessible class tree structure, node layout, connections, choices, conditions, costs, rank descriptions, linked spells, and selected build snapshots |
| Professions | Viewed profession state, bounded recipe enumeration and schematics/reagents, reported newly learned recipes and crafting results |
| Gathering | Recognized herbalism, mining, skinning, and fishing cast starts/outcomes; readable attempt links, observed player locations |
| Objects | Readable GameObject loot-source identities and candidate loot links; generic world objects remain unclassified |

Locations identify their subject: player map coordinates are an observer location, not an exact monster spawn. Native unit positions are separately labeled. Quest deltas link before/after snapshots without claiming that a nearby creature caused progress. Loot visibility, cleared slots, inventory gains, and personal receipt remain separate facts.

The current client restricts the combat-log feed, so direct kill tracking remains unavailable. Loot slots retain source GUIDs when a guarded native API read supplies readable pairs, with its undocumented return contract labeled **unverified**. Target/mouseover snapshots and matching receipt links remain **candidates**. Items and creatures share this source evidence in the export; confirmed drop attribution still needs in-game validation. The addon does not infer drop rates, quest prerequisites, or causality from timing alone.

This records exposed gameplay evidence, not every server action. It excludes private conversations, player names/GUIDs, Battle.net identifiers, arbitrary raw event payloads, and inaccessible values. Recipe scans report their actual enumeration scope, including filtered fallback and unavailable fields; they do not establish a complete server recipe catalog. See [database coverage](docs/database-coverage.md) and [recording limits](docs/implementation.md).

Spellbooks and talents are sampled automatically on entering the world and relevant changes. To explicitly dump them, run `/ft dump`, then `/ft status`. Wait until both scans are idle and pending spell reads reach zero, then `/reload`. The scan status reports complete or partial coverage; missing information remains labeled in the export. This captures trees and spells exposed to the current character, including readable unselected talents. Collect on other classes to expand coverage; the addon does not switch your specialization or fetch a server-wide spell catalog.

## Desktop exporter

Open **ForeverTome Exporter** from the Start menu, or run **ForeverTomeExporter.exe** directly. Its **Install / update addon** tab finds the game and installs or updates the latest merged addon. In **Export recordings**, select your account's `SavedVariables/ForeverTome.lua` and an output folder, then click **Export now** or **Start watching**. The application retains every exported observation in `history.json`, builds `database.json` with entities, relationships and coverage, and publishes 13 category views. `latest.json` contains the complete current save. Use `/reload` or normal logout in WoW to save new observations first.

The window shows status, provides **Stop** and **Open export folder**, and remembers your selected paths. Closing it stops watching and exits after any current conversion finishes. It does not run in the tray, start with Windows, or upload data. The packaged executable does not require Python to be installed. See [desktop exporter instructions and build steps](docs/desktop-exporter.md).

For development, launch the window with `py tools/exporter_app.py`. The command-line tools below remain available for scripts and other export formats.

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

Use the [desktop exporter](docs/desktop-exporter.md) to control automatic conversion from a window. For a command-line watcher instead:

```powershell
py tools/watch_catalog.py 'D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua' --output-dir 'C:\Exports\ForeverTome'
```

The watcher checks every two seconds and merges every observation into `history.json` by ID before publishing derived files. Repeated observations are kept once; conflicting content under the same ID is rejected. Existing category files, dated snapshots and `latest.json` are imported on upgrade. Previously discarded evidence cannot be reconstructed. Keep using the same export folder and export successfully before clearing the addon.

`creatures.json` provides canonical creature records. `npcs.json` is a compatibility alias and `monsters.json` is an observed-reaction subset; import each creature key once. Additional categories include recipes, maps, professions, currencies, objects and gathering. The [file-by-file guide](docs/database-coverage.md) explains their structure, coverage and remaining gaps.

It waits for WoW to save through `/reload` or logout, retries incomplete saves, and stops with Ctrl+C. Individual files are replaced atomically; consumers should require matching export IDs and matching `historyId` values across cumulative files. The archive allows interrupted publication and deleted projections to recover on the next export. Nothing is installed to run at Windows startup.

## Development

Python 3.10+ and Lua 5.1 or compatible LuaJIT are required:

```powershell
py tools/test.py
py tools/package.py
```

Tests load production files in TOC order through a deterministic fake game host, exercise errors/reload/export, and verify that deliberate recording defects fail the gate. Synthetic tests are not proof of native client permissions or persistence.

[Implementation contract](docs/implementation.md) · [Client evidence/export](docs/implementation-client.md) · [Quest collector](docs/implementation-quests.md) · [Spell collector](docs/implementation-spells.md) · [Talent collector](docs/implementation-talents.md) · [API research handbook](docs/README.md)
