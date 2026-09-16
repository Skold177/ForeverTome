# Acquisition catalog

[Acquisition plan](README.md) · [Storage design](storage-and-import.md) · [Machine-readable backlog](acquisition-backlog.json)

**Status: collection targets, not confirmed WF contents.** Every table/API name below is a candidate to check against the actual client. Desired output fields are requirements for our catalog, not assertions that one table or API supplies them all.

## How to use the catalog

Client tables are structured data files commonly called DBC or DB2. The table names below were checked against the pinned [WoWDBDefs definition inventory](../reference/sources.md#d-dbd); this only establishes known table families in WoW tooling. It does not establish their presence, layout, semantics, or completeness in WF.

Prefer explicit IDs and table/API relationships. Preserve localized text separately. Keep unknown columns and unresolved references instead of assigning plausible names or joining entities by display name.

| ID | Domain | Priority | Earliest attempted collection |
| --- | --- | --- | --- |
| A01 | Build and API surface | P0 | Download |
| A02 | Classes, races, specializations, skills | P0 | Download |
| A03 | Spells and abilities | P0 | Download |
| A04 | Talent trees | P0 | Download |
| A05 | Maps, zones, subzones, floors | P0 | Download |
| A06 | Items, equipment, sets, appearances | P0 | Download |
| A07 | Professions and recipes | P1 | Download; results through gameplay |
| A08 | Quests and objective definitions | P1 | Download for fragments; login/gameplay for exposed details |
| A09 | Creatures and NPC metadata | P1 | Download for definitions; gameplay for sightings |
| A10 | World objects and gathering nodes | P1 | Download for definitions; gameplay for interactions |
| A11 | Factions and reputation | P1 | Download; login/gameplay for state and gains |
| A12 | Travel networks and destinations | P1 | Download; gameplay for availability and timings |
| A13 | Dungeons, raids, encounters | P1 | Download; gameplay for active content |
| A14 | Vendors and trainers | P1 | Relevant gameplay interaction |
| A15 | Loot and acquisition relationships | P1 | Relevant gameplay event |
| A16 | Currencies | P2 | Download |
| A17 | Achievements and criteria | P2 | Download, if the system exists |
| A18 | Mounts, pets, and collections | P2 | Download, if the system exists |
| A19 | Localization and useful asset references | P1 | Download; linked to all domains |
| A20 | Newly discovered WF systems | P1 | Download discovery; validation depends on the system |

## A01. Build and API surface

**Acquire:** launcher product/channel, installed version/build, locale availability, content/config identifiers if provided, readable archive/file inventory, UI Lua/XML/TOC files, generated API declarations, enums, event names, and restriction annotations. After login, compare with `GetBuildInfo()` and actual permissions.

**Method:** inventory the actual installation before choosing a product path or archive reader. Preserve source code and generated declarations, then compare them with our pinned reference research. Produce function/event changes with signatures and restrictions, not only a list of new names. [R-BUILD](../reference/sources.md#r-build), [R-EVENT](../reference/sources.md#r-event)

**Outputs:** `build`, `artifacts`, `api_functions`, `api_events`, `api_structures`, and a capability-validation queue. API availability in source and ordinary-addon usability remain different fields.

## A02. Classes, races, specializations, and skills

**Acquire:** IDs, localized names, class/race associations, display ordering, explicit eligibility references, skill-line IDs, and specialization definitions if present. Include racial abilities and class ability associations when represented explicitly.

**Candidates:** `ChrClasses`, `ChrRaces`, `ChrSpecialization`, `SkillLine`, and `SkillLineAbility`; readable character-creation and spellbook state can validate availability after login.

**Outputs:** `classes`, `races`, `specializations`, `skills`, plus typed relationships. A class/race appearing in a table is not proof that its combination is playable. Keep creation availability separate from packaged definitions and character unlock state.

## A03. Spells and abilities

This is a first-pass priority because abilities link talent trees, items, recipes, creatures, and quests.

**Acquire when present:** spell ID; name/subtext; raw description/aura text; icon; cast time; range; duration; resource costs; base cooldown/charge metadata; ordered effects; aura/proc conditions; skill/class/race associations; rank, replacement, and prerequisite links. Preserve spell variants and passive/active classification only where their meaning is established.

**File candidates:** `Spell`, `SpellName`, `SpellMisc`, `SpellEffect`, `SpellAuraOptions`, `SpellPower`, `SpellCooldowns`, `SpellRange`, `SpellDuration`, `SpellCastTimes`, `SpellDescriptionVariables`, and `SkillLineAbility`. Multiple rows/tables may describe one spell; do not drop secondary effects or assume their IDs equal the spell ID.

**Login enrichment:** in the R reference, `C_SpellBook.GetNumSpellBookSkillLines()`, `GetSpellBookSkillLineInfo(index)`, and `GetSpellBookItemInfo(slot, bank)` provide a bounded way to inspect a character's book. Skill-line metadata supplies the slot offset/count. Preserve bank, book-item type, and known/future/override context where readable. A book item need not be a simple castable spell. [R-SPELL](../reference/sources.md#r-spell)

For known spell IDs, R declares `C_Spell.GetSpellInfo(id)` and `GetSpellDescription(id)`. It also declares `RequestLoadSpellData(id)`, with asynchronous completion through `SPELL_DATA_LOAD_RESULT`; description text can need a later `SPELL_TEXT_UPDATE`. Validate both readiness and permitted fields on WF rather than treating a completed load as a guarantee of every text field.

**Outputs:** `spells`, `spell_effects`, `spell_costs`, `spell_links`, and contextual `spell_ui_samples`. Preserve symbolic description tokens and rendered tooltip samples separately. A damage number can depend on level, gear, talents, rank, scaling, or hotfix state; a tooltip sample is not the universal base value. Runtime cooldown remaining is not base cooldown metadata.

**Coverage limit:** extracting all readable spell rows does not identify all learnable player abilities. Validate representative class/racial/profession/item/NPC spell categories before classifying the catalog.

## A04. Talent trees

**Acquire:** tree identity and class/spec applicability; node IDs and layout coordinates; ordered entries/choices; maximum ranks; rank-to-spell/definition links; edges and their types; point/currency costs; unlock/visibility conditions; subtree connections; and labels/icons. Keep each character's purchased ranks/configuration separate from the tree definition.

**File candidates:** traditional `Talent` and `TalentTab`, or trait-family `TraitTree`, `TraitNode`, `TraitEdge`, `TraitNodeEntry`, `TraitDefinition`, `TraitNodeXTraitNodeEntry`, `TraitNodeXTraitCond`, `TraitCond`, and `TraitCost`. Inspect associated relationship tables discovered in the actual schema. A matching name does not establish which talent system WF uses.

**Login method if the trait API exists:** resolve an exposed configuration; inspect its tree IDs; enumerate nodes; read node entries, definitions, costs, and conditions; retain explicit edge semantics. R references include `C_ClassTalents.GetActiveConfigID()`, `C_Traits.GetConfigInfo(configID)`, `GetTreeNodes(treeID)`, `GetNodeInfo(configID, nodeID)`, `GetEntryInfo(configID, entryID)`, and `GetDefinitionInfo(definitionID)`. R also exposes tree, node-cost, and condition readers. These are reference signatures, not WF guarantees. [R-TALENT](../reference/sources.md#r-talent)

**Outputs:** `talent_trees`, `talent_nodes`, `talent_entries`, `talent_edges`, `talent_costs`, `talent_conditions`, and separate configuration samples. Explicit relationships may be many-to-many. Do not reduce a multi-rank talent to its final rank or a choice node to the selected choice.

**Validation:** reconstruct one readable tree from the extracted graph and compare names, positions, ranks, choices, and visible connections with the game UI. Record unexposed/locked branches. A low-level character's empty or partial talent view is a coverage limitation, not evidence that the class has no talents.

## A05. Maps, zones, subzones, and floors

**Acquire:** map and UI-map IDs; localized names; map type; parent relationships; area/subarea IDs; difficulty/instance associations; floor/group relationships; map art identifiers; and explicit coordinate assignments/transforms where their units and meaning can be validated.

**Candidates:** `Map`, `AreaTable`, `UiMap`, `UiMapAssignment`, `UiMapArt`, `WorldMapArea`, `MapDifficulty`, and `Difficulty`. Keep area IDs, internal map IDs, and UI-map IDs in different namespaces.

**Login method:** inspect known map IDs through `C_Map.GetMapInfo`; use `GetMapChildrenInfo(uiMapID, mapType?, allDescendants?)` where supported, starting from known roots and retaining a visited set. Compare hierarchy to the package inventory; a UI traversal need not expose every packaged map. [R-MAP](../reference/sources.md#r-map)

**Outputs:** `maps`, `areas`, `ui_maps`, `map_relationships`, `map_art`, and validated coordinate mappings. Player-position samples and actual NPC/node locations belong in the observation layer. Map rectangles alone do not establish accessible terrain, playable boundaries, or recommended quest levels. See [location rules](../02-api/maps-and-location.md).

## A06. Items, equipment, sets, and appearances

**Acquire:** item ID; localized names/descriptions; class/subclass; quality; stack/equip/bind attributes; level/class/race/skill requirements; stats and scaling references; use/equip spell links; set membership/bonuses; appearance/display references; vendor-value metadata; and variant/bonus references when exposed.

**Candidates:** `Item`, `ItemSparse`, `ItemEffect`, `ItemSet`, `ItemAppearance`, and `ItemModifiedAppearance`, plus schema-discovered relationship tables. Preserve distinct item/appearance identities.

**Login enrichment:** request known IDs through the validated item metadata path, keeping full permitted links for encountered variants. Do not scan arbitrary ID ranges. [R-ITEM](../reference/sources.md#r-item)

**Outputs:** `items`, `item_effects`, `item_sets`, `item_set_members`, and variant/appearance relationships. Store computed tooltip values as contextual samples. A packaged item does not establish obtainability, drop source, current vendor price, or a complete loot table.

## A07. Professions and recipes

**Acquire:** profession/skill IDs; recipe identity; recipe-spell links; output item references and quantities; required/optional reagent groups; required skill/tool/focus; rank/category; and learning-source candidates where explicit.

**Candidates:** `SkillLine`, `SkillLineAbility`, `SpellReagents`, `SpellReagentsCurrency`, `SpellEffect`, `SpellFocusObject`, and `CraftingData`, supplemented by the actual profession UI/API. Use separate adapters for whichever system WF exposes. [R-PROFESSION](../reference/sources.md#r-profession), [T-PROFESSION](../reference/sources.md#t-profession)

**Outputs:** `professions`, `recipes`, `recipe_reagents`, `recipe_outputs`, and learning/result observations. A recipe can have choices, multiple outputs, or variable quantities; represent alternatives instead of one flattened reagent/output list. Do not infer trainer availability, skill-up chance, or WF support for Retail crafting systems from table presence.

## A08. Quests and objectives

**Acquire:** every readable quest ID and definition fragment; titles/text; objective rows; objective target references; flags/categories; reward definitions; map/line associations; and explicit condition/prerequisite references if present and understood.

**Candidates:** `QuestV2`, `QuestInfo`, `QuestLine`, `QuestLineXQuest`, `QuestObjective`, and `QuestPackageItem`. Their names do not mean they contain the full quest database. Server-provided dialogue, giver/finisher relationships, eligibility, and active objective state may still require normal interactions and validated quest APIs. [R-QUEST](../reference/sources.md#r-quest), [R-GOSSIP](../reference/sources.md#r-gossip)

**Outputs:** `quests`, `quest_definition_fragments`, `quest_objectives`, `quest_reward_options`, and source-backed relationships. Keep incomplete definitions importable with coverage labels. Any stable objective ID obtained from a table is distinct from the runtime objective-array index until a mapping is demonstrated.

Record observed acceptance/progress/turn-in sequences through ForeverTome. Do not treat a line's display order as a mandatory prerequisite chain or auto-complete missing WF text from another product. See [quest recording](../02-api/quests.md).

## A09. Creatures and NPCs

**Acquire:** available creature/type/family names and IDs, display/model references, and explicit spell/service/faction links where supplied. Candidates include `Creature`, `CreatureDisplayInfo`, `CreatureModelData`, `CreatureFamily`, and `CreatureType`.

**Outputs:** `creatures`, `creature_displays`, and typed references, followed by NPC sightings and service observations. A display ID is not a creature template ID. A client creature table may be a partial display/name catalog rather than the server's complete creature template database.

Exact spawns, patrols, respawn rates, level distributions, combat behavior, vendors, trainers, quest roles, and loot sources require their own evidence. Readable unit events can establish sightings; they do not reveal every nearby NPC. [R-UNIT](../reference/sources.md#r-unit)

## A10. World objects and gathering nodes

**Acquire:** available object IDs, types, labels, display references, and explicit interaction/spell/placement fields. Candidates: `GameObjects` and `GameObjectDisplayInfo`, plus new tables discovered by inventory.

**Outputs:** `world_objects`, `object_displays`, any documented packaged placements, and separate gathering/interaction samples. Even a position in a file is a packaged placement until matched to active world behavior. Chests, doors, gathering resources, and quest objects need distinct classifications.

Do not mistake a visual model for a usable node or infer node loot/respawn from its asset. Gameplay collection follows the [professions and world](../02-api/professions-and-world.md) chapter.

## A11. Factions and reputation

**Acquire:** faction IDs, localized names/descriptions, hierarchy, faction-template references, reputation labels/threshold definitions where available, and explicit relationship flags. Candidates: `Faction`, `FactionTemplate`.

**Outputs:** `factions`, `faction_templates`, and separately observed standings/reputation gains. NPC faction templates and reputation factions are related namespaces, not automatically interchangeable IDs. Do not infer a quest's reputation reward or a hostility outcome from a faction label alone.

## A12. Travel networks and destinations

**Acquire:** transport node/path IDs, names, endpoints, ordered path points, map/area references, safe-location/POI definitions, and explicit faction constraints. Candidates: `TaxiNodes`, `TaxiPath`, `TaxiPathNode`, `WorldSafeLocs`, `AreaPOI`.

**Outputs:** `travel_nodes`, `travel_paths`, `travel_path_points`, `world_destinations`, and observed availability/cost/timing. R's `C_TaxiMap.GetAllTaxiNodes(uiMapID)` is described as information at the current flight master; despite its name, it is not a promised global unlock-independent route dump. [R-TRAVEL](../reference/sources.md#r-travel)

Boat/zeppelin schedules, available destinations, learned routes, portals, and actual travel time may depend on gameplay. Preserve explicit graph direction and mode; geometric proximity does not create a travel edge.

## A13. Instances and encounters

**Acquire:** instance/map/difficulty identities, category/name/level metadata where present, encounter IDs/order, and journal creature/item/ability references where the system exists. Candidates: `MapDifficulty`, `Difficulty`, `LFGDungeons`, `DungeonEncounter`, `JournalEncounter`, `JournalEncounterCreature`, `JournalEncounterItem`.

**Outputs:** `instances`, `instance_difficulties`, `encounters`, and journal-derived relationships with source labels. A journal listing is a client-provided listing, not a recorded drop or proof of a live mechanic. New WF content may have no journal coverage.

## A14. Vendors and trainers

**Acquire through interactions:** NPC identity, offered items/abilities/recipes, bundle sizes, costs/currencies, stock, requirements, and player eligibility at observation time. `ItemExtendedCost` can help decode referenced costs if present, but does not establish which NPC offers an item.

**Outputs:** `vendor_offers`, `trainer_offers`, and linked interaction observations. Retain observer location, time, character context needed to interpret price/eligibility, and missing fields. Enumerate only the opened supported view; do not purchase or train to scrape data. [R-MERCHANT](../reference/sources.md#r-merchant), [world interactions](../02-api/professions-and-world.md)

## A15. Loot and acquisition relationships

**Acquire through gameplay:** visible loot, validated source mappings, personal receipt evidence, quest rewards, craft results, purchases, and other explicitly observed acquisition paths. Keep each method distinct.

**Outputs:** loot/receipt observations and evidence-backed `acquisition_relationships`. There is no assumed downloadable complete server loot table. Explicit client journal/reward listings can be cataloged as declared relationships, with different evidence from witnessed outcomes. Drop rates need observed eligible opportunities, coverage, and sufficient samples. [Loot and items](../02-api/loot-and-items.md)

## A16. Currencies

**Acquire:** IDs, names, icons, category/precision metadata and explicit exchange/cost references. Candidate: `CurrencyTypes` and any relationship tables identified by schema inspection.

**Outputs:** `currencies`, cost references, and separately observed balances/transactions. A character's current total, cap, or seasonal availability is contextual state and must not overwrite the definition.

## A17. Achievements and criteria

**Acquire if present:** IDs, names/descriptions, categories, points/rewards and an explicit criteria graph. Candidates: `Achievement`, `Criteria`, `CriteriaTree`.

**Outputs:** `achievements`, `achievement_criteria`, `criteria_edges`. Criteria can be nested or conditional; preserve operator/threshold semantics instead of flattening a tree into independent checkboxes. Character progress belongs in observations. Existing client definitions do not prove WF enables this system.

## A18. Mounts, pets, and collections

**Acquire if present:** mount/pet IDs, names, spell/display/item links, categories, and source text. Candidates: `Mount`, `MountXDisplay`, and `BattlePetSpecies`; inspect any WF-specific collection system separately.

**Outputs:** `mounts`, `pet_species`, and typed references. A collection entry is distinct from ownership, a summon spell, or an obtainable source. Source text is descriptive evidence; do not convert it into an exact drop rate or NPC relationship without support.

## A19. Localization and useful asset references

**Acquire:** localized names/descriptions for collected domains, supported locale list, and referenced icon/map/display FileDataIDs or readable paths. Preserve source strings, formatting tokens, and asset identity before generating plain-text search fields or previews.

**Outputs:** `localized_strings`, `asset_references`, plus optional small review previews. Extract the configured primary locale first; list other installed locales as later coverage work. Missing translations remain missing, with any display fallback identified explicitly.

Keep bulk map textures, models, and audio out of the documentation repository. The initial catalog needs resolvable references and useful previews, not every media file. Shared assets or familiar icons do not prove that an item/ability belongs to another product's content.

## A20. New WF systems

**Discover:** new UI modules, generated API namespaces, enums, table families, and relationships that do not fit existing domains. Record original names and provenance without guessing gameplay semantics.

**Outputs:** `discovered_systems` and a prioritized investigation queue: source artifacts, candidate entities/events, likely related domains, unresolved meanings, and a specific validation action. Promote a system into a typed catalog only after inspecting its structure and observing enough UI/gameplay behavior to establish field meaning.

## Boundaries for all collection

Enumerate local file rows and exposed lists; follow known references into a deduplicated work queue. API enrichment should operate on known IDs, respect load readiness, stop at configured limits, and avoid secret values. One successful lookup does not justify an unbounded scan of every possible spell/item/quest ID.

Cross-domain relationships belong to a separate evidence-bearing layer. Keep both “defined in this build” and “observed in this WF context” so a new item, ability, or quest can enter the catalog before its acquisition/usage is understood.
