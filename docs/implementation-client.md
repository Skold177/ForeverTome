# Implemented client profile and export

The initial addon profile targets **Forever Beta 1.60.1, build 69893**. It is derived from the installed client's extracted source. Ordinary-addon behavior in game remains unverified. The existing reference handbook's Retail/Titan comparison is useful background; Titan is not the implementation target.

## Installed evidence

Read-only inspection on September 17, 2026 established:

| Evidence | Result |
| --- | --- |
| `D:\World of Warcraft\.build.info` | Active `wow_classic_beta` version `1.60.1.69893`, build key `70dc75547c16ac2a381fde65945a0e85` |
| `D:\World of Warcraft\_classic_beta_\.flavor.info` | `wow_classic_beta` |
| `D:\World of Warcraft\_classic_beta_\WowB.exe` version resource | File/product version `1.60.1.69893` |
| `D:\World of Warcraft\Data\config\70\dc\70dc75547c16ac2a381fde65945a0e85`, line 16 | `build-name = WOW-69893patch1.60.1_ForeverBeta` |

The adjacent `ForeverTome` repository already contains a local extraction at `artifacts/datamining/1.60.1.69893/`. Its `extraction-manifest.json` records file identities and hashes; `client-identity.json` records executable identity. The matching build report is `ForeverTome/docs/datamining/1.60.1.69893.md`. These large, local game artifacts are not copied into this addon repository.

The API paths below are relative to that extraction's `raw/interface/addons/` directory. Both mainline and Classic files occur in the archive; `blizzard_uipanels_game/blizzard_uipanels_game.toc` routes Camelot through mainline family UI plus Camelot overrides.

| Area | Installed source evidence | Implementation implication |
| --- | --- | --- |
| Quests | `blizzard_apidocumentationgenerated/questlogdocumentation.lua`: `GetNumQuestLogEntries`, `GetInfo(index)`, `GetQuestObjectives(questID)`; `QUEST_ACCEPTED(questId)` at line 1312 | Modern `C_QuestLog` profile; acceptance argument 1 is the quest ID |
| Quest outcome | Same source: `QUEST_TURNED_IN(questID, xpReward, moneyReward)`, `QUEST_REMOVED(questID, wasReplayQuest)` | Preserve turn-in separately from removal, readiness, or dialogue closure |
| Quest text/rewards | `blizzard_uipanels_game/mainline/questinfo.lua` and `questframe.lua` | Capture dialogue text/reward choices while open; `GetQuestLogQuestText` takes a log index |
| Gossip | `blizzard_apidocumentationgenerated/gossipinfodocumentation.lua` | `C_GossipInfo` structured quest/option arrays and text |
| Loot | `blizzard_apidocumentationgenerated/lootdocumentation.lua`: `LOOT_OPENED(autoLoot, isFromItem)`; mainline `lootframe.lua:236` | Slot tuple: texture, name, quantity, currency ID, quality, locked, quest-item flag, quest ID, active flag, coin flag |
| Bags/items | `containerdocumentation.lua`, `itemdocumentation.lua` in the generated API directory | `C_Container` structured item results; `C_Item.GetItemInfo` and `GetItemInfoInstant` |
| Position | Generated `mapdocumentation.lua` | `C_Map.GetBestMapForUnit` and `GetPlayerMapPosition` explicitly cover player/party; stored coordinates belong to the observer |
| Units | Generated `unitdocumentation.lua` | `UnitGUID` and `UnitName` can return secret identity values; check readability before inspecting fields |
| Spells | Generated `spellbookdocumentation.lua`, `spelldocumentation.lua`; Camelot uses the mainline spellbook | Read player/pet skill lines and entries, passive/future spells, flyouts, metadata and current character state; [spell contract](implementation-spells.md) |
| Talents | Generated `classtalentsdocumentation.lua`, `sharedtraitsdocumentation.lua` | Read the active config and accessible class trees through `C_ClassTalents`/`C_Traits`; [talent contract](implementation-talents.md) |
| Combat | Generated `combatlogsecuredocumentation.lua`: `C_CombatLogSecure` is `SecureOnly`; `combatlogdocumentation.lua` marks unfiltered event restricted | Direct combat-log/death capture remains disabled |
| Loot sources | No declaration or UI usage for `GetLootSourceInfo` found in this extraction | Source-pair decoding remains disabled; targeted creatures are not promoted to drop sources |

The exact interface number was not established by static inspection. Extracted Blizzard TOCs generally omit it, and an executable version alone does not measure `GetBuildInfo()`'s interface result. The packaged TOC value is provisional until checked in game; runtime client identity records the actual return. Event registration, readability, delivery, coordinate semantics, and native SavedVariables durability still require the [WF test plan](04-validation/wf-test-plan.md).

## External export

After a normal `/reload` or logout, make a stable copy of the account SavedVariables file. The expected beta path is `D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua`; the actual path must be confirmed after the client first saves it. Unsaved play can be lost on a crash.

From the addon repository, with Python 3.10 or newer:

```powershell
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.json'
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.jsonl' --format jsonl --sqlite 'C:\Exports\evidence.sqlite'
py -m unittest discover -s tests -p 'test_export.py'
```

The parser accepts one `ForeverTomeDB` data assignment and never executes Lua. It rejects functions, calls, expressions, trailing statements, duplicate keys, invalid encodings/numbers, oversized data, schema mismatches, unknown record kinds, broken record identities, and invalid normalized locations. Input defaults are bounded to 128 MiB, 65,536 bytes per string, depth 24, 512 sessions, and 60,000 observations. It checks file identity/size/mtime around reading; use a saved copy rather than relying on this as a filesystem lock.

JSON preserves the complete database envelope, session headers, observations, diagnostics, and recording settings. Known array fields become arrays, including empty `observations`, `objectives`, `sources`, and reward lists. Empty maps such as `missing_fields`, `capabilities`, and diagnostic `counts` remain objects. Unknown empty tables default to objects; a new collector adding an array field must extend the export schema.

JSONL starts with a `type: export` metadata line and input SHA-256, followed by `type: session` headers/diagnostics and `type: observation` lines. Lua-only storage details are normalized into JSON, but gameplay records and evidence are retained. Consumers must treat strings as data and escape them when rendering.

The optional SQLite output stores canonical session headers in `ft_sessions` and observations in `ft_observations`. Reimporting identical IDs is idempotent; conflicting content fails the transaction instead of overwriting evidence. A conflict leaves any newly written JSON export available for review. SQLite is an evidence store, not an inferred item, monster, quest, or drop-rate database. The tool never uploads data, edits the input, clears the addon, or replaces an existing JSON output.
