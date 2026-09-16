# Source register

[Documentation index](../README.md)

**Reviewed:** 2026-09-16. The [source manifest](source-manifest.json) carries the same identifiers and immutable file links in JSON.

## Authority and limitations

Blizzard-authored generated declarations and shipped UI call sites are the primary technical evidence. They were read from local checkouts of the community-maintained [Gethe/wow-ui-source mirror](https://github.com/Gethe/wow-ui-source). The mirror is a distribution mechanism, not an official Blizzard repository or evidence of ordinary-addon permission.

`R` identifies Retail `12.1.0.69814`; `T` identifies the `classic_titan` mirror snapshot `3.80.2.69815`. Neither has been matched to a running WF client. The commits, rather than moving branch names, define this handbook's reference contracts.

`TEST` identifies language, testing-tool, and CI documentation. These sources support the proposed harness design; they do not establish WF compatibility or mean that tooling has been installed.

Product announcements do not establish API behavior. Forum posts by players on Blizzard's domain are not Blizzard statements. Search-result summaries, community compatibility lists, and generated addon guides were not used to establish API contracts. The historical loot trace is explicitly limited to the original author's dated observation.

A source declaration supports names, argument order, types and flags. It does not establish all native behavior. General runtime conventions and proposed recording policies are distinguished in their chapters and must pass the WF test plan.

## Reference source files

### R-BUILD

**Retail build identity** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Version pin and GetBuildInfo return contract.

- [version.txt](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/version.txt)
- [BuildDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/BuildDocumentation.lua)

### T-BUILD

**Comparison build identity** — 3.80.2.69815, commit `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8`.

Version pin only; the relationship of this branch to WF is unconfirmed.

- [version.txt](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/version.txt)
- [ProjectConstants.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_SharedXML/ProjectConstants.lua)

### R-TOC

**Manifest examples** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Blizzard addon metadata, dependencies, load-on-demand and per-character saved-variable declarations. Native save timing is a separate runtime validation item.

- [Blizzard_APIDocumentationGenerated.toc](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/Blizzard_APIDocumentationGenerated.toc)
- [Blizzard_ClientSavedVariables.toc](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_ClientSavedVariables/Blizzard_ClientSavedVariables.toc)

### R-LIFECYCLE

**Addon and world lifecycle** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

ADDON_LOADED and login, world transition, and logout payloads.

- [AddOnsDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/AddOnsDocumentation.lua)
- [SystemDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SystemDocumentation.lua)

### R-EVENT

**Event subscription APIs** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Event validity, frame event registration, unit-event registration, and unregistration.

- [EventUtilsDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/EventUtilsDocumentation.lua)
- [SimpleFrameAPIDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SimpleFrameAPIDocumentation.lua)

### R-SECRET

**Value-access and secrecy APIs** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

issecretvalue, canaccessvalue, canaccesstable and their declared access rules.

- [FrameScriptDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/FrameScriptDocumentation.lua)

### R-COMBAT

**Retail combat-log restrictions** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Restricted combat-log events and the secure-only current-event reader.

- [CombatLogDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/CombatLogDocumentation.lua)
- [CombatLogSecureDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/CombatLogSecureDocumentation.lua)

### T-COMBAT

**Comparison combat-log interface** — 3.80.2.69815, commit `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8`.

Restricted namespaced reader, historical alias, and death/credit subevent handling. Built-in UI access is not ordinary-addon permission.

- [CombatLogDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_APIDocumentationGenerated/CombatLogDocumentation.lua)
- [Deprecated_CombatLog.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_DeprecatedCombatLog/Deprecated_CombatLog.lua)
- [Blizzard_CombatLog.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_CombatLog/Classic/Blizzard_CombatLog.lua)

### R-QUEST

**Retail quest log** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Quest functions, objective structures and event payloads.

- [QuestLogDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/QuestLogDocumentation.lua)

### T-QUEST

**Comparison quest log** — 3.80.2.69815, commit `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8`.

Two-argument QUEST_ACCEPTED and legacy quest-log call sites.

- [QuestLogDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_APIDocumentationGenerated/QuestLogDocumentation.lua)
- [QuestInfo.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_UIPanels_Game/Vanilla/QuestInfo.lua)

### R-OFFER

**Quest interaction lifecycle** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

QUEST_PROGRESS, QUEST_FINISHED and related dialogue events.

- [QuestOfferDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/QuestOfferDocumentation.lua)

### R-UI

**Quest and loot UI call sites** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Actual use of quest dialogue functions and global loot slot readers. Call sites are not exhaustive native API declarations.

- [QuestFrame.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_UIPanels_Game/Mainline/QuestFrame.lua)
- [QuestInfo.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_UIPanels_Game/Mainline/QuestInfo.lua)
- [LootFrame.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_UIPanels_Game/Mainline/LootFrame.lua)

### R-LOOT

**Retail loot events** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Loot session, slot, receipt/toast and encounter events.

- [LootDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/LootDocumentation.lua)

### T-LOOT

**Comparison loot events** — 3.80.2.69815, commit `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8`.

LOOT_OPENED has one declared argument in this snapshot.

- [LootDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_APIDocumentationGenerated/LootDocumentation.lua)

### R-ITEM

**Item metadata and loading** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

C_Item readers, nullable metadata, load requests and result events.

- [ItemDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/ItemDocumentation.lua)

### R-BAGS

**Container state** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

C_Container.GetContainerItemInfo and BAG_UPDATE_DELAYED.

- [ContainerDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/ContainerDocumentation.lua)

### R-CHAT

**Loot chat event** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

CHAT_MSG_LOOT uses a generic multi-field chat payload; do not assume text is a creature-source record.

- [ChatInfoDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/ChatInfoDocumentation.lua)

### R-MAP

**Maps and instance context** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

C_Map player/group position limits, map identity and GetInstanceInfo returns.

- [MapDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/MapDocumentation.lua)
- [InstanceDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/InstanceDocumentation.lua)

### R-UNIT

**Unit identity and spellcasts** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Unit getters, identity restrictions, target/mouseover/nameplate events and spellcast payloads.

- [UnitDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/UnitDocumentation.lua)
- [NamePlateManagerDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/NamePlateManagerDocumentation.lua)

### R-TIME

**Observation clocks** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

GetServerTime, GetTime and GetTimePreciseSec declarations; epoch/clock behavior must be checked when interpreting durations.

- [SystemTimeDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SystemTimeDocumentation.lua)
- [OsDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/OsDocumentation.lua)

### R-PROFESSION

**Retail professions** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Recipe info/schematic APIs, craft-result structures, recipe and profession events.

- [TradeSkillUIDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/TradeSkillUIDocumentation.lua)
- [TradeSkillUITypesDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/TradeSkillUITypesDocumentation.lua)
- [SkillInfoDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SkillInfoDocumentation.lua)

### T-PROFESSION

**Comparison professions** — 3.80.2.69815, commit `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8`.

Smaller C_TradeSkillUI surface and legacy trade/craft UI readers.

- [TradeSkillUIDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_APIDocumentationGenerated/TradeSkillUIDocumentation.lua)
- [Blizzard_TradeSkillUI.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_TradeSkillUI/Vanilla/Blizzard_TradeSkillUI.lua)
- [Blizzard_TradeSkillUI.xml](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_TradeSkillUI/Vanilla/Blizzard_TradeSkillUI.xml)
- [Blizzard_CraftUI.lua](https://github.com/Gethe/wow-ui-source/blob/1303c9bdbb7f320fa45db1eaee73acaae3b71fe8/Interface/AddOns/Blizzard_CraftUI/Vanilla/Blizzard_CraftUI.lua)

### R-GOSSIP

**Gossip and quest offers** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Readable dialogue, offered/active quest lists and interaction events.

- [GossipInfoDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/GossipInfoDocumentation.lua)

### R-MERCHANT

**Merchant inventory** — 12.1.0.69814, commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

C_MerchantFrame.GetItemInfo and merchant interaction events.

- [MerchantFrameDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/MerchantFrameDocumentation.lua)

## External primary sources

### B-WF

[Blizzard WF announcement](https://worldofwarcraft.blizzard.com/en-gb/news/24302093).

Product context and announced beta start; no API compatibility claim. Search-index text was available; direct English page retrieval failed during research.

### B-COMBAT

[Blizzard combat philosophy and addon disarmament](https://worldofwarcraft.blizzard.com/fr-fr/news/24246290).

Retail combat information and secret-value design. French official article was retrieved; it is not a WF API specification.

### B-POLICY

[Blizzard UI Add-On Development Policy](https://us.forums.blizzard.com/en/wow/t/ui-add-on-development-policy/24534/4).

Policy text attributed to Blizzard staff; distribution and performance requirements.

### H-LOOT-SOURCE

[Original developer trace of GetLootSourceInfo](https://www.wowinterface.com/forums/archive/index.php/t-43091.html).

Ketho's 2012 beta trace shows alternating GUID/quantity returns for area loot. Historical evidence only; it is not a current native declaration or WF compatibility test.

## Reproducing the inspection

Check out the recorded commits, inspect `version.txt`, then find a function's `Name` or an event's `LiteralName` in `Interface/AddOns/Blizzard_APIDocumentationGenerated/`. Include the enclosing namespace, environment, restrictions, arguments/returns or payload, and referenced structure definitions. For a global absent from generated declarations, locate an actual UI call site and record the resulting evidence limit.

Do not update a source revision without revisiting the affected API statements. Follow the [maintenance procedure](maintenance.md) and record WF testing separately from source inspection.

## Acquisition planning sources

The following extend the API research with spell/talent/travel reference declarations and candidate external file readers. Tool/schema projects are primary evidence for their own interfaces and definition inventories, not official WF documentation. No installed WF archive or table has been parsed.

### R-SPELL

**Spell and spellbook reference APIs** — commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Spell metadata, asynchronous text/data loading, spellbook enumeration and item/skill-line structures. Reference client only.

- [SpellDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SpellDocumentation.lua)
- [SpellBookDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SpellBookDocumentation.lua)

### R-TALENT

**Trait and class talent reference APIs** — commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

Configuration, tree, node, entry, definition, cost and condition readers. Does not establish which talent system WF uses.

- [SharedTraitsDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/SharedTraitsDocumentation.lua)
- [ClassTalentsDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/ClassTalentsDocumentation.lua)

### R-TRAVEL

**Taxi map reference API** — commit `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59`.

GetAllTaxiNodes is documented in the context of the current flight master; not a guarantee of global route enumeration.

- [TaxiMapDocumentation.lua](https://github.com/Gethe/wow-ui-source/blob/4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59/Interface/AddOns/Blizzard_APIDocumentationGenerated/TaxiMapDocumentation.lua)

### D-DBD

**Community client database definitions** — commit `a5d9a7286eb185726e3cfcf10177b41d91613fc6`.

Candidate table-name inventory and build/layout-aware schema format. Definition directory names were checked against this revision; WF files were not inspected. Community interpretations and provisional columns are not Blizzard guarantees.

- [README.md](https://github.com/wowdev/WoWDBDefs/blob/a5d9a7286eb185726e3cfcf10177b41d91613fc6/README.md)
- [manifest.json](https://github.com/wowdev/WoWDBDefs/blob/a5d9a7286eb185726e3cfcf10177b41d91613fc6/manifest.json)
- [Pinned definition directory](https://github.com/wowdev/WoWDBDefs/tree/a5d9a7286eb185726e3cfcf10177b41d91613fc6/definitions)

### D-DBCD

**DBCD table reader documentation** — commit `2d50ae2633166ff5dd57e802e960f5e9e558177f`.

Candidate DBC/DB2 reader with definition and cache/hotfix support described by its maintainers. WF format compatibility has not been tested.

- [README.md](https://github.com/wowdev/DBCD/blob/2d50ae2633166ff5dd57e802e960f5e9e558177f/README.md)

### D-CASC

**CascLib archive reader documentation** — commit `2a280f5a231966dc5d1b534978dd9f9f04a374cd`.

Candidate CASC archive reader. No WF extraction or compatibility test has been performed.

- [README.md](https://github.com/ladislav-zezula/CascLib/blob/2a280f5a231966dc5d1b534978dd9f9f04a374cd/README.md)

## Test harness sources

### TEST-LUA

[Official Lua 5.1 reference manual](https://www.lua.org/manual/5.1/manual.html).

Language baseline for table references, nil fields, multiple returns, and metatable behavior. The proposed harness must pin its actual interpreter; this manual does not identify WF's embedded runtime or native extensions.

### TEST-LUAUNIT

[LuaUnit upstream project and documentation](https://github.com/bluebird75/luaunit).

Maintainer documentation for the proposed Lua assertion/reporting dependency. A specific dependency revision must be selected and pinned in the implementation PR; none is installed or claimed tested here.

### TEST-GITHUB-CHECKS

[GitHub: troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

Official behavior of required checks, latest commit status, skipped checks, workflow filters, and merge queue triggers. Supports the aggregate-gate design; does not imply repository rules are configured.

### TEST-GITHUB-WORKFLOWS

[GitHub: triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

Official workflow event/filter configuration. Future CI configuration must be checked against these rules when implemented.
