# Recording loot and item information

[Documentation index](../README.md) · [Event catalog](event-catalog.md)

**Status:** R reference plus an explicitly historical source-mapping candidate; WF unverified. Sources: [R-LOOT](../reference/sources.md#r-loot), [R-UI](../reference/sources.md#r-ui), [R-ITEM](../reference/sources.md#r-item), [R-BAGS](../reference/sources.md#r-bags), [H-LOOT-SOURCE](../reference/sources.md#h-loot-source).

## Keep three observations separate

1. **Loot visible:** an item appeared in a readable loot slot.
2. **Loot source:** the client associated that slot or quantity with a source entity.
3. **Item received:** evidence indicates an item was awarded to the local player.

A visible slot can remain unlooted. A cleared slot can reflect distribution or other state changes. An inventory increase can come from a quest reward, trade, mail, crafting, purchase, or loot. Store those facts separately and link them only with adequate evidence.

## Loot-slot readers

The R loot UI calls these global functions; their existence in Blizzard code does not by itself establish WF permissions or a complete native signature. [R-UI](../reference/sources.md#r-ui)

| Function | Observed reference use | Capture guidance |
| --- | --- | --- |
| `GetNumLootItems()` | Bounds the slot loop | Counts loot slots, not total item quantity or dead creatures |
| `GetLootSlotType(slot)` | Distinguishes item, currency, money, or none | Decode slot type before interpreting a link |
| `GetLootSlotInfo(slot)` | Returns display and quantity fields | Snapshot while the slot exists |
| `GetLootSlotLink(slot)` | Reads an item/currency hyperlink | Preserve the full permitted link; do not assume every link is an item |

The R `LootFrame.lua` call site unpacks `GetLootSlotInfo` as `texture, item, quantity, currencyID, itemQuality, locked, isQuestItem, questID, isActive, isCoin`. This is the tuple used in that source snapshot, not a guaranteed cross-client contract.

Use separate item, money, and currency record variants. Do not turn money into an item ID, interpret an absent link as an empty slot, or reuse a slot index outside its loot session.

## Proposed loot-session lifecycle

```text
LOOT_READY / LOOT_OPENED -> snapshot slots and readable source mappings
LOOT_SLOT_CHANGED       -> revise one saved slot
LOOT_SLOT_CLEARED       -> record its removal using the saved snapshot
LOOT_CLOSED             -> finalize the session; preserve unresolved receipt/source
```

This diagram expresses collector responsibilities, not an assertion that both opening events always occur once or in a fixed order. Test automatic looting explicitly.

Assign a local loot-session ID. Multiple readiness/open notifications for the same active interaction should not duplicate all items. Closing and reopening a corpse produces a new interaction, but repeated visibility of its same items must not be counted as newly received items or a new kill.

Capture critical slot data immediately; deferred metadata can arrive after the window closes. Record whether the snapshot was complete, partial, or unavailable. Empty, closed-before-read, and restricted are different outcomes.

## Associating loot with a source

`GetLootSourceInfo(slot)` is a **historical candidate**. An original 2012 developer trace reports alternating values `sourceGUID1, quantity1, sourceGUID2, quantity2, ...` for an area-loot slot. That trace does not show a leading source count. We did not locate a generated declaration or use of this function in the inspected R/T UI trees, so this handbook does not certify its current presence, tuple, restrictions, or quantity semantics. [H-LOOT-SOURCE](../reference/sources.md#h-loot-source)

If WF supplies a readable supported equivalent, validate it with one-source and multi-source looting before using it. Preserve all source pairs. Compare their quantities with the visible slot quantity, and retain mismatches as unresolved evidence instead of correcting them by guesswork.

**Proposed attribution rules:**

- An explicit, validated slot-to-source mapping is direct source evidence.
- A recently targeted corpse or nearby death is a candidate association only.
- With area loot, one visible slot can combine items from several sources.
- A source can be a creature, game object, container item, or another supported kind. Do not parse every GUID as a creature.
- If source information is missing, save the loot with an unknown source. Do not assign it to the last killed monster.

Even a correct source mapping does not prove who killed the creature, where it spawned, or whether the player received the item.

## Item metadata

| R API/event | Contract relevant to recording |
| --- | --- |
| `C_Item.GetItemInfo(itemInfo)` | Can return nothing; otherwise returns item name/link, quality, levels, type/subtype, stack size, equip location, texture, sell price, class/subclass, bind type, expansion, optional set, crafting-reagent flag and description |
| `C_Item.GetItemInfoInstant(itemInfo)` | Can return nothing; otherwise returns item ID, type/subtype, equip location, icon and class/subclass IDs |
| `C_Item.RequestLoadItemDataByID(itemInfo)` | Requests metadata; the declared argument accepts the `ItemInfo` type |
| `ITEM_DATA_LOAD_RESULT(itemID, success)` | Re-read matching pending metadata on success |
| `GET_ITEM_INFO_RECEIVED(itemID, success)` | Additional metadata notification; avoid duplicate enrichment |

`itemInfo` is the declaration's input type, not a ForeverTome record. Use an observed item ID or supported link form validated on WF. Do not assume deprecated global `GetItemInfo` aliases exist on every client. [R-ITEM](../reference/sources.md#r-item)

Keep the item ID as content identity and the full item hyperlink when permitted. Item links may encode variants; two links with the same item ID need not describe identical instances. Store locale and build alongside names/descriptions. An uncached or new item is unresolved, not invalid content to discard.

## Receipt and inventory changes

`C_Container.GetContainerItemInfo(containerIndex, slotIndex)` provides a structured R bag-slot result or no result. `BAG_UPDATE_DELAYED` is useful for batching comparisons. Define the inspected bag scope explicitly; a move between bag slots is not a new item gain. [R-BAGS](../reference/sources.md#r-bags)

If `CHAT_MSG_LOOT` is used, classify it against the client's localized message templates and verify recipient semantics. Do not use English-only regular expressions or assume a generic chat GUID identifies a loot source. Discard unrelated player names and chat fields after classification. [R-CHAT](../reference/sources.md#r-chat)

Other receipt/toast events may be useful, but their exact WF support and coverage require independent validation. No single toast or bag event is assumed to cover every acquisition path.

## Drop-rate limits

Recorded loot can establish observed item-source relationships. Estimating a drop rate also needs a defensible denominator: distinct, eligible, completely observed opportunities. Unlooted corpses, quest eligibility, group distribution, containers, repeat openings, and recording gaps bias that denominator.

Do not calculate “item drops divided by all nearby deaths” as a drop rate. Keep eligibility and capture coverage available to the external analysis step.

## Validation cases

Test manual/automatic loot, repeated opening, money/currency slots, two creatures in area loot, identical items from multiple sources, uncollected items, full bags, containers, gathering, group distribution, and uncached metadata. Include a bag-only gain from another source to prove it is not misclassified as a monster drop.
