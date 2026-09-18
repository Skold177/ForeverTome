# Implemented client profile and export

The addon profile targets **Forever Beta 1.60.1, build 69893**. It is derived from the installed client's extracted source. Live 0.2.2 saved data confirms ordinary quest acceptance, progress, turn-in, native quest-item receipts, loot capture, and persistence; the 0.2.3 item stats/tooltip addition still needs an in-game check. The existing reference handbook's Retail/Titan comparison is useful background; Titan is not the implementation target.

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
| Quest item receipt | `blizzard_apidocumentationgenerated/lootdocumentation.lua:316-326`: `QUEST_LOOT_RECEIVED(questID, itemLink, quantity)`; consumed by `blizzard_framexml/mainline/alertframes.lua:717-724` | Direct quest-to-item evidence, separately recorded from reward options, generic chat receipts, and inventory deltas; ordinary quest reward delivery verified in live 0.2.2 saved data |
| Quest text/rewards | `blizzard_uipanels_game/mainline/questinfo.lua` and `questframe.lua` | Capture dialogue text/reward choices while open; `GetQuestLogQuestText` takes a log index |
| Gossip | `blizzard_apidocumentationgenerated/gossipinfodocumentation.lua` | `C_GossipInfo` structured quest/option arrays and text |
| Loot | `blizzard_apidocumentationgenerated/lootdocumentation.lua`: `LOOT_OPENED(autoLoot, isFromItem)`; mainline `lootframe.lua:236` | Slot tuple: texture, name, quantity, currency ID, quality, locked, quest-item flag, quest ID, active flag, coin flag |
| Bags/items | `containerdocumentation.lua`, `itemdocumentation.lua` in the generated API directory | `C_Container` structured item results; `C_Item.GetItemInfo` and `GetItemInfoInstant` |
| Item stats | `blizzard_apidocumentationgenerated/itemdocumentation.lua:1004`: `GetItemStats(itemLink)` | String-link argument; result may be absent. Preserve readable stat tokens and finite numeric values with character/sample context |
| Item tooltip data | `blizzard_apidocumentationgenerated/tooltipinfodocumentation.lua:337`: `GetHyperlink(hyperlink)` | Read tooltip data without manipulating the visible `GameTooltip`; result may be absent |
| Tooltip line fields | `blizzard_sharedxmlgame/tooltip/tooltipdatahandler.lua:314,320,339,342` consumes `tooltipData.lines`, `lineData.type`, `leftText`, and `rightText` | Preserve bounded readable line text and numeric types; do not inspect unrelated tooltip structures |
| Position | Generated `mapdocumentation.lua` | `C_Map.GetBestMapForUnit` and `GetPlayerMapPosition` explicitly cover player/party; stored coordinates belong to the observer |
| Units | Generated `unitdocumentation.lua` | `UnitGUID` and `UnitName` can return secret identity values; check readability before inspecting fields |
| Spells | Generated `spellbookdocumentation.lua`, `spelldocumentation.lua`; Camelot uses the mainline spellbook | Read player/pet skill lines and entries, passive/future spells, flyouts, metadata and current character state; [spell contract](implementation-spells.md) |
| Talents | Generated `classtalentsdocumentation.lua`, `sharedtraitsdocumentation.lua` | Read the active config and accessible class trees through `C_ClassTalents`/`C_Traits`; [talent contract](implementation-talents.md) |
| Combat | Generated `combatlogsecuredocumentation.lua`: `C_CombatLogSecure` is `SecureOnly`; `combatlogdocumentation.lua` marks unfiltered event restricted | Direct combat-log/death capture remains disabled |
| Loot sources | No declaration or UI usage in the extraction; installed `WowB.exe` contains `GetLootSourceInfo` at byte 83,289,760 and `Usage: GetLootSourceInfo(slot)` at byte 83,290,792 | Guarded runtime probing retains readable source pairs with an unverified contract; targeted creatures remain candidates |
| Storage | Generated `bankdocumentation.lua`: `FetchViewableBankTypes`, `CanViewBank`, `FetchPurchasedBankTabIDs`; mainline `containerframe.lua`: `NumBagSlots` plus `NumReagentBagSlots`; Camelot `paperdollframe.lua`: equipment getters | Separate observed equipment/carried/open-bank snapshots; preserve access and completeness boundaries |
| Item relations | Generated `itemdocumentation.lua`: `GetItemSpell(itemInfo)` and `GetItemGem(hyperlink, index)`; `blizzard_framexmlbase/constants.lua`: `MAX_NUM_SOCKETS = 3` | Retain readable item-spell and socketed-gem references without inventing effect type or empty sockets |
| Recipe enumeration | Generated `tradeskilluidocumentation.lua`: `GetFilteredRecipeIDs` and recipe/schematic structures; executable symbol `GetAllRecipeIDs` at byte 83,577,216 | Guarded all-ID probe remains unverified; source-verified filtered fallback retains actual scope |
| Object tooltips | Generated `tooltipinfodocumentation.lua`: `GetWorldCursor`; `gametooltip.lua` uses it; tooltip Object type is 4 | Only copy readable object tooltip fields when its GUID exactly matches the GameObject loot source; no chest classification or position inference |

Version 0.3.0 adds storage, recipe scanning, NPC cast/service observations, gathering attempts and object/item details. These source-backed paths have offline regressions but still require native validation. `GetWorldLootObject` takes a unit token, so the addon does not pass a loot-source GUID to it. Fishing IDs 7620, 7731, 7732 and 18248 were checked against the extracted `SpellName` and `SpellEffect` tables; skill-bonus and training spells are excluded.

The live recording session header establishes `GetBuildInfo()` interface version **16001**, matching the packaged TOC. This is runtime evidence; extracted Blizzard TOCs and executable versions alone did not establish it. Broader event/readability coverage, coordinate semantics, and the new 0.2.3 item details still need the relevant cases in the [WF test plan](04-validation/wf-test-plan.md).

Item stats and tooltip reads use the profile's `item_stats` and `item_tooltips` gates. The collector retains basic item metadata immediately, limits each sample to 64 stat entries and 64 tooltip lines, and retries unavailable details at most twice after the initial read. Status and missing-field reasons distinguish unavailable, unsupported, partial, and readable empty results. See the [item field contract](implementation.md#item-stats-and-tooltips) for the payload shape and character-context boundary.

## External export

After a normal `/reload` or logout, make a stable copy of the account SavedVariables file. The expected beta path is `D:\World of Warcraft\_classic_beta_\WTF\Account\<account>\SavedVariables\ForeverTome.lua`; the actual path must be confirmed after the client first saves it. Unsaved play can be lost on a crash.

From the addon repository, with Python 3.10 or newer:

```powershell
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.json'
py tools/export_saved_variables.py 'C:\Exports\ForeverTome.lua' --output 'C:\Exports\session.jsonl' --format jsonl --sqlite 'C:\Exports\evidence.sqlite'
py -m unittest discover -s tests -p 'test_export.py'
```

The parser accepts one `ForeverTomeDB` data assignment and never executes Lua. It rejects functions, calls, expressions, trailing statements, duplicate keys, invalid encodings/numbers, oversized data, schema mismatches, unknown record kinds, broken record identities, and invalid normalized locations. Input defaults are bounded to 128 MiB, 65,536 bytes per string, depth 24, 512 sessions, and 60,000 observations. It checks file identity/size/mtime around reading; use a saved copy rather than relying on this as a filesystem lock.

JSON preserves the complete database envelope, session headers, observations, diagnostics, and recording settings. Known array fields become arrays, including empty `observations`, `objectives`, `sources`, `tooltip_lines`, and reward lists. Empty maps such as `stats`, `stat_labels`, `missing_fields`, `capabilities`, and diagnostic `counts` remain objects. Unknown empty tables default to objects; a new collector adding an array field must extend the export schema.

JSONL starts with a `type: export` metadata line and input SHA-256, followed by `type: session` headers/diagnostics and `type: observation` lines. Lua-only storage details are normalized into JSON, but gameplay records and evidence are retained. Consumers must treat strings as data and escape them when rendering.

The optional SQLite output stores canonical session headers in `ft_sessions` and observations in `ft_observations`. Reimporting identical IDs is idempotent; conflicting content fails the transaction instead of overwriting evidence. A conflict leaves any newly written JSON export available for review. SQLite is an evidence store, not an inferred item, monster, quest, or drop-rate database. The tool never uploads data, edits the input, clears the addon, or replaces an existing JSON output.
