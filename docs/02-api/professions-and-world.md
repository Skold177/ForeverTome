# Recording professions and world interactions

[Documentation index](../README.md)

**Status:** branch-specific reference candidates; WF systems unverified. Sources: [R-PROFESSION](../reference/sources.md#r-profession), [T-PROFESSION](../reference/sources.md#t-profession), [R-GOSSIP](../reference/sources.md#r-gossip), [R-MERCHANT](../reference/sources.md#r-merchant).

## Professions need their own compatibility adapter

The inspected Retail source has detailed `C_TradeSkillUI` recipe, schematic, and result APIs. T has a smaller namespace and legacy trade/craft UI code. Neither determines how WF's new professions will work.

Do not assume Retail specializations, quality tiers, recrafting, or crafting orders exist in WF. Model the observed profession/recipe IDs and requirements first; add product-specific features only when actually exposed.

## Recipe discovery and metadata

| Reference candidate | Use | Limitation |
| --- | --- | --- |
| `SKILL_LINES_CHANGED` | Refresh profession/skill state | Does not itself name a new recipe |
| `TRADE_SKILL_SHOW`, `TRADE_SKILL_LIST_UPDATE` | Capture/diff visible recipe state | Filters, learned/unlearned views, and data loading affect completeness |
| `TRADE_SKILL_DATA_SOURCE_CHANGED` | Reset the viewed profession context | Viewed data may describe another source, not the player's learned recipes |
| `NEW_RECIPE_LEARNED` | Record a reported recipe acquisition | Payload differs by branch; validate WF |
| R `C_TradeSkillUI.GetRecipeInfo(recipeSpellID, recipeLevel?)` | Recipe metadata or nil | Record recipe ID and profession context, not a UI row index |
| R `C_TradeSkillUI.GetRecipeSchematic(recipeSpellID, isRecraft, recipeLevel?)` | Structured recipe requirements | Retail contract; WF adoption is unknown |
| Legacy `GetTradeSkillInfo`, `GetTradeSkillItemLink`, `GetTradeSkillRecipeLink` | Read classic-style trade-skill rows/links where supported | These are UI call-site candidates, not a WF tuple contract |
| Legacy `GetCraftInfo` | Separate craft-style UI reader | Not interchangeable with the Retail recipe API |

**Proposed recipe record:** observed recipe identity, profession/skill identity, learned/available state where reported, output references, required reagents and quantities, optional slots separately, skill requirements, source API, locale, and build. A snapshot establishes what was visible in that context; it is not a complete global recipe catalog.

Preserve unavailable reagent data. Resolve item metadata through the same bounded loading queue as loot, rather than dropping a newly introduced reagent.

## Crafting outcomes

R declares `TRADE_SKILL_ITEM_CRAFTED_RESULT(data)`, with a `CraftingItemResultData` structure containing item ID, item GUID, hyperlink, quantity, and further Retail-specific result fields. It does not provide a simple universal recipe-ID field in that structure. A recipe association therefore requires separately observed crafting context or another validated explicit relationship.

A successful spellcast is not by itself a complete craft-result record. R's `UNIT_SPELLCAST_SUCCEEDED` payload can be restricted/secret; inspect only permitted fields. A crafting attempt, successful cast, and received output are different stages. [R-UNIT](../reference/sources.md#r-unit)

When craft-result events are unavailable, retain recipe snapshots and independently observed item gains. Label any proposed link as inferred. Do not infer every bag increase near a profession window to be that recipe's output, especially with queued crafts or unrelated incoming items.

## Gathering, fishing, skinning, and containers

A possible gathering record combines a readable interaction/cast, an observed loot session, any validated source identity, and the player's position. Each input can be absent.

- A mining or herbalism object is not necessarily an addressable unit.
- Skinning can produce another loot interaction on a corpse that was already looted.
- Fishing and item containers need distinct source kinds.
- A spell succeeding does not prove which object supplied the later loot.
- A tooltip label is localized display evidence, not a universal game-object identifier.

Use explicit source mapping when available; otherwise preserve a candidate association and its timing. Do not query forbidden information or parse UI display output to reconstruct secret data. The [loot chapter](loot-and-items.md) explains the unresolved source API and area-loot limitations.

A gathering sample is not proof of a fixed node position, a respawn interval, or an exhaustive list of materials that source can yield.

## Gossip and world interactions

During `GOSSIP_SHOW`, R offers `C_GossipInfo.GetText()`, `GetOptions()`, `GetAvailableQuests()`, and `GetActiveQuests()`. Snapshot permitted text/options/quest IDs while the interaction exists. `GOSSIP_CLOSED` includes an interaction-continuation flag in R; do not flatten every close into a completed gameplay action.

Store an interaction ID, readable NPC identity if available, observer location, text locale, and offered options. The presence of an option does not prove the player chose it. Choosing a dialogue option does not establish that a quest objective advanced unless the objective state also changes.

Default to passive reads. `SelectOption`, quest-selection functions, and similar APIs perform actions and are not required to collect the player's naturally observed choices or outcomes.

For new WF systems with no verified API, keep an open research question rather than inventing an event name. If only dialogue or resulting inventory/quest changes are observable, document that limited coverage.

## Vendors and item availability

R declares `MERCHANT_SHOW`, `MERCHANT_UPDATE`, and `MERCHANT_CLOSED`. `C_MerchantFrame.GetItemInfo(index)` returns a `MerchantItemInfo` record or no result. Its fields include name, texture, price, stack count, available count, purchase/usability flags, extended-cost flag, and optional currency/spell IDs.

This structure does not by itself provide a complete item-link or extended-cost contract. Validate companion enumeration/link/cost APIs on WF before promising complete vendor records.

**Proposed vendor observation:** interaction/NPC identity where readable, observer location, offered item reference, price and bundle size, currency/extended costs when known, stock state, and contextual restrictions. Limited stock, discounts, and eligibility can vary. An offer does not establish a purchase.

Never issue purchases, profession casts, or dialogue selections simply to populate the database.

## Validation cases

Test recipe learning, filtered/unfiltered recipe views, a profession with legacy UI if present, missing reagent metadata, single and queued crafts, an interrupted cast, two adjacent nodes, skinning after corpse loot, fishing, item containers, continued gossip interactions, and vendors with limited stock or extended costs.
