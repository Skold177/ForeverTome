# Event catalog for a gameplay recorder

[Documentation index](../README.md)

**Status:** signatures below are from **R: Retail 12.1.0.69814**, unless explicitly marked T. **All WF payloads and permissions are unverified.** This is a task-focused catalog, not the entire WoW event API.

Arguments listed here follow the event name in `OnEvent(self, event, ...)`. `—` means the reference declaration lists no payload. An event identifies a capture opportunity; the last column states the proposed response, not a guarantee of available data.

## Lifecycle and world context

Sources: [R-LIFECYCLE](../reference/sources.md#r-lifecycle), [R-MAP](../reference/sources.md#r-map).

| Event | R payload | Capture/use |
| --- | --- | --- |
| `ADDON_LOADED` | `addOnName, containsBindings` | Initialize only when the named addon is ForeverTome |
| `PLAYER_LOGIN` | — | Start normal-login baseline work |
| `PLAYER_ENTERING_WORLD` | `isInitialLogin, isReloadingUi` | Refresh world, map and snapshot context |
| `PLAYER_LEAVING_WORLD` | — | Invalidate transient context; mark a transition |
| `PLAYER_LOGOUT` | — | Final small bookkeeping |
| `ZONE_CHANGED` | — | Refresh zone/subzone metadata |
| `ZONE_CHANGED_INDOORS` | — | Refresh indoor/subzone context |
| `ZONE_CHANGED_NEW_AREA` | — | Refresh map/zone/instance context |

Zone events do not contain coordinates. Sample the player position at each observation that needs a location.

## Quests and dialogue

Sources: [R-QUEST](../reference/sources.md#r-quest), [T-QUEST](../reference/sources.md#t-quest), [R-OFFER](../reference/sources.md#r-offer), [R-GOSSIP](../reference/sources.md#r-gossip), [R-UI](../reference/sources.md#r-ui).

| Event | R payload | Capture/use |
| --- | --- | --- |
| `QUEST_ACCEPTED` | `questId` | Record acceptance; schedule a quest snapshot. **T:** `questIndex, questId` |
| `QUEST_LOG_UPDATE` | — | Coalesce into a snapshot/diff pass; no quest ID is supplied |
| `QUEST_WATCH_UPDATE` | `questID` | Refresh affected quest; do not assume only watched quests can change |
| `QUEST_POI_UPDATE` | — | Optional map-marker refresh; not objective completion evidence |
| `QUEST_DETAIL` | `questStartItemID` (nullable) | Read the offered quest and dialogue immediately; this argument is not the quest ID |
| `QUEST_PROGRESS` | — | Read progress-dialogue state; not the generic objective-progress event |
| `QUEST_COMPLETE` | — | Reward/turn-in dialogue shown; not proof of turn-in |
| `QUEST_TURNED_IN` | `questID, xpReward, moneyReward` | Record reported turn-in and reference reward values |
| `QUEST_REMOVED` | `questID, wasReplayQuest` | Record removal; do not classify as abandoned without evidence |
| `QUEST_FINISHED` | — | Quest interaction ended; not proof of completion |
| `QUEST_GREETING` | — | Read offered/active quest interaction context if supported |
| `QUEST_DATA_LOAD_RESULT` | `questID, success` | Resolve matching pending quest metadata |
| `GOSSIP_SHOW` | `uiTextureKit` (nullable) | Snapshot dialogue and quest offers while open |
| `GOSSIP_CLOSED` | `interactionIsContinuing` | Close or advance interaction context |

## Loot, item data, and inventory

Sources: [R-LOOT](../reference/sources.md#r-loot), [T-LOOT](../reference/sources.md#t-loot), [R-ITEM](../reference/sources.md#r-item), [R-BAGS](../reference/sources.md#r-bags), [R-CHAT](../reference/sources.md#r-chat).

| Event | R payload | Capture/use |
| --- | --- | --- |
| `LOOT_READY` | `autoloot` | Candidate early slot snapshot; validate readiness and repetition on WF |
| `LOOT_OPENED` | `autoLoot, isFromItem` | Snapshot readable slots before auto-loot clears them. **T:** `autoLoot` only |
| `LOOT_SLOT_CHANGED` | `lootSlot` | Refresh the affected slot within its loot session |
| `LOOT_SLOT_CLEARED` | `lootSlot` | Relate removal to the saved slot snapshot; not independent receipt proof |
| `LOOT_CLOSED` | — | Close session; keep unresolved observations |
| `ITEM_DATA_LOAD_RESULT` | `itemID, success` | Resolve item metadata requests |
| `GET_ITEM_INFO_RECEIVED` | `itemID, success` | Alternative metadata notification; deduplicate by pending item ID |
| `BAG_UPDATE_DELAYED` | — | Coalesce inventory snapshot comparison; does not identify the cause |
| `CHAT_MSG_LOOT` | Generic chat tuple; see below | Optional localized receipt evidence; avoid saving the entire payload |

The R `CHAT_MSG_LOOT` tuple is `text, playerName, languageName, channelName, playerName2, specialFlags, zoneChannelID, channelIndex, channelBaseName, languageID, lineID, guid, bnSenderID, isMobile, isSubtitle, hideSenderInLetterbox, suppressRaidIcons, discordInfo`. The chat GUID is not a creature loot-source GUID. Read only validated fields needed to classify the local player's receipt; discard unrelated social identifiers.

## Spell metadata enrichment

Source: [R-SPELL](../reference/sources.md#r-spell). These support the planned [ability catalog](../05-acquisition/catalog.md#a03-spells-and-abilities); they are not cast, learning, or acquisition notifications.

| Event | R payload | Capture/use |
| --- | --- | --- |
| `SPELL_DATA_LOAD_RESULT` | `spellID, success` | Resolve a bounded pending request for a known spell ID; re-read supported fields |
| `SPELL_TEXT_UPDATE` | `spellID` | Refresh unresolved or changed description text; data-load completion need not imply final text readiness |

## Units and combat candidates

Sources: [R-UNIT](../reference/sources.md#r-unit), [R-COMBAT](../reference/sources.md#r-combat).

| Event | R payload | Capture/use |
| --- | --- | --- |
| `PLAYER_TARGET_CHANGED` | — | Read permitted target identity immediately |
| `UPDATE_MOUSEOVER_UNIT` | — | Read permitted mouseover identity immediately |
| `NAME_PLATE_UNIT_ADDED` | `unitToken` | Cache a sighting for this temporary token |
| `NAME_PLATE_UNIT_REMOVED` | `unitToken` | Retire the token mapping; removal is not death |
| `UNIT_FLAGS` | `unitTarget` | Candidate readable state refresh; not a universal death notification |
| `UNIT_SPELLCAST_SUCCEEDED` | `unitTarget, castGUID, spellID, castBarID` (last nullable) | Optional player crafting/gathering context; payload can be secret |
| `COMBAT_LOG_EVENT_UNFILTERED` | Restricted callback; no ordinary payload contract here | Disabled until WF demonstrates a supported third-party capture path |

`UNIT_DIED` and `PARTY_KILL` are historical combat-log **subevents**, not frame events to register individually. See [combat](units-and-combat.md).

## Professions and merchants

Sources: [R-PROFESSION](../reference/sources.md#r-profession), [T-PROFESSION](../reference/sources.md#t-profession), [R-MERCHANT](../reference/sources.md#r-merchant).

| Event | R payload | Capture/use |
| --- | --- | --- |
| `SKILL_LINES_CHANGED` | — | Refresh readable profession/skill state |
| `TRADE_SKILL_SHOW` | — | Begin profession UI snapshot |
| `TRADE_SKILL_LIST_UPDATE` | — | Refresh/diff available recipe state |
| `TRADE_SKILL_DATA_SOURCE_CHANGED` | — | Reset context; viewed recipes may not be the player's own |
| `TRADE_SKILL_CLOSE` | — | End profession interaction |
| `NEW_RECIPE_LEARNED` | `recipeID, recipeLevel, baseRecipeID` (last two nullable) | Record the reported learned recipe; confirm WF arguments |
| `TRADE_SKILL_ITEM_CRAFTED_RESULT` | `data: CraftingItemResultData` | Candidate result record; Retail-specific until verified |
| `MERCHANT_SHOW` | — | Snapshot readable merchant context and inventory |
| `MERCHANT_UPDATE` | — | Refresh prices, quantities, or stock |
| `MERCHANT_CLOSED` | — | End merchant interaction |

T also declares `TRADE_SKILL_UPDATE`; it is not a universal replacement for the R events. Choose event sets from a tested adapter, not from the union of every historical API.
