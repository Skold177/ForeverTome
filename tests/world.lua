local function creature(h)
    h.env.UnitGUID = function(token)
        if token == "target" or token == "npc" or token == "nameplate1" then
            return "Creature-0-1-2-3-7001-000001"
        end
    end
    h.env.C_CreatureInfo.GetCreatureID = function()
        return 7001
    end
    h.env.UnitName = function()
        return "Forest Sentinel"
    end
    h.env.UnitIsDead = function()
        return false
    end
    h.env.UnitLevel = function()
        return 6
    end
end

local function quest(h)
    local state = { active = true, title = "A New Threat", progress = 0, requested = 0 }
    h.env.C_QuestLog = {
        GetNumQuestLogEntries = function()
            return state.active and 1 or 0, state.active and 1 or 0
        end,
        GetInfo = function()
            return { questID = 501, title = state.title, isHeader = false }
        end,
        GetQuestObjectives = function()
            return { { text = "Wolves slain: " .. state.progress .. "/5", type = "monster",
                finished = false, numFulfilled = state.progress, numRequired = 5 } }
        end,
        IsComplete = function()
            return false
        end,
        IsQuestFlaggedCompleted = function()
            return false
        end,
        IsOnQuest = function()
            return state.active
        end,
        GetTitleForQuestID = function()
            return state.title
        end,
        RequestLoadQuestByID = function()
            state.requested = state.requested + 1
        end,
    }
    h.env.GetQuestLogQuestText = function()
        return "The wolves have returned.", "Defeat five wolves."
    end
    return state
end

local function profession(h, count)
    local state = { profession_id = 164, source_counter = 1, ids = {}, name = "Known recipe", reads = 0 }
    for index = 1, count do
        state.ids[index] = 1000 + index
    end
    h.env.C_TradeSkillUI.GetBaseProfessionInfo = function()
        return { professionID = state.profession_id, professionName = "Smithing", sourceCounter = state.source_counter,
            skillLevel = 15, maxSkillLevel = 75 }
    end
    h.env.C_TradeSkillUI.GetProfessionInfoByRecipeID = function()
        return { professionID = state.profession_id, professionName = "Smithing" }
    end
    h.env.C_TradeSkillUI.GetAllRecipeIDs = function()
        return state.ids
    end
    h.env.C_TradeSkillUI.GetRecipeInfo = function(id)
        state.reads = state.reads + 1
        return { recipeID = id, name = state.name, learned = true, categoryID = 1, skillLineAbilityID = id + 2000,
            qualityItemIDs = { 8111, 8112 } }
    end
    h.env.C_TradeSkillUI.GetRecipeSchematic = function(id, isRecraft)
        assert(isRecraft == false)
        return { recipeID = id, outputItemID = 8111, quantityMin = 1, quantityMax = 2, recipeType = 1, icon = 100,
            reagentSlotSchematics = { { quantityRequired = 2, required = true, reagentType = 1,
                reagents = { { itemID = 8112 }, { currencyID = 23 } },
                variableQuantities = { { reagent = { itemID = 8112 }, quantity = 3 } },
                slotInfo = { mcrSlotID = 9, requiredSkillRank = 5, slotText = "Reagent" } } } }
    end
    h.env.C_TradeSkillUI.GetRecipeRequirements = function()
        return { { name = "Anvil", met = false, type = 0 } }
    end
    return state
end

return {
    { name = "zone changes retain accepted quest runs and queued objective comparisons", run = function(Host)
        local h     = Host.new()
        local state = quest(h)
        state.active = false
        h:start()
        state.active = true
        h:event("QUEST_ACCEPTED", 501)
        h:advance(0.5)
        local accepted = h:last("quest.accepted")
        local previous = h:last("quest.snapshot")
        for index, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
            state.progress = index
            h.state.map    = 42 + index
            h:event("QUEST_LOG_UPDATE")
            h:event(event)
            local context = h:last("world.context")
            assert(context.capture.event == event and context.location.ui_map_id == 42 + index)
            h:advance(0.5)
            local current = h:last("quest.snapshot")
            local delta   = h:last("quest.objective_delta")
            assert(current.data.quest_run_id == accepted.data.quest_run_id)
            assert(delta and delta.data.amount == 1 and delta.data.quest_run_id == accepted.data.quest_run_id)
            assert(delta.related_observation_ids[1] == previous.observation_id)
            assert(delta.related_observation_ids[2] == current.observation_id)
            assert(current.capture.event == "QUEST_LOG_UPDATE")
            assert(#h:records("quest.baseline") == 0 and #h:records("quest.objective_delta") == index)
            previous = current
        end
        h:advance(3)
        assert(h:last("location.sample") and h:last("location.sample").location.ui_map_id == 45)
        assert(#h:records("world.context") == 4)
        h:assertHealthy()
    end },
    { name = "zone changes preserve pending quest and item metadata references", run = function(Host)
        local h     = Host.new()
        local state = quest(h)
        state.title = nil
        h:start()
        local snapshot = h:last("quest.snapshot")
        local receipt  = h.FT.Emit("item.received", { item_id = 8111 }, "CHAT_MSG_LOOT", "direct_event")
        h.FT.RequestItem(8111, nil, receipt)
        for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
            h:event(event)
            h:advance(0.5)
        end
        assert(state.requested == 1)
        state.title = "Resolved quest"
        h.env.C_Item.GetItemInfo = function()
            return "Resolved item", "item:8111"
        end
        h:event("QUEST_DATA_LOAD_RESULT", 501, true)
        h:event("ITEM_DATA_LOAD_RESULT", 8111, true)
        local metadata = h:last("quest.metadata")
        local item     = h:last("item.metadata")
        assert(metadata and metadata.related_observation_ids[1] == snapshot.observation_id)
        assert(item and item.related_observation_ids[1] == receipt)
        assert(snapshot.data.metadata.title == nil)
        h:advance(0.5)
        assert(h:last("quest.snapshot").data.quest_run_id == snapshot.data.quest_run_id)
        assert(#h:records("quest.baseline") == 1)
        h:assertHealthy()
    end },
    { name = "zone changes preserve pending metadata timeout workers", run = function(Host)
        local h     = Host.new()
        local state = quest(h)
        state.title = nil
        h:start()
        local snapshot = h:last("quest.snapshot")
        local receipt  = h.FT.Emit("item.received", { item_id = 8111 }, "CHAT_MSG_LOOT", "direct_event")
        h.FT.RequestItem(8111, nil, receipt)
        for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
            h:event(event)
        end
        h:advance(23)
        local metadata = h:last("quest.metadata_unavailable")
        local item     = h:last("item.metadata_unresolved")
        assert(metadata and metadata.related_observation_ids[1] == snapshot.observation_id)
        assert(item and item.related_observation_ids[1] == receipt and item.data.status == "timeout")
        assert(state.requested == 2)
        h:assertHealthy()
    end },
    { name = "zone changes keep active and queued catalogs without starting extra scans", run = function(Host)
        local catalogs = {
            { suite = "spells", namespace = "C_SpellBook", method = "GetNumSpellBookSkillLines", kind = "spellbook.scan" },
            { suite = "talents", namespace = "C_ClassTalents", method = "GetActiveConfigID", kind = "talent.snapshot" },
        }
        for _, catalog in ipairs(catalogs) do
            local h = Host.new()
            dofile("tests/" .. catalog.suite .. ".lua").setup(h, 65)
            local namespace = h.env[catalog.namespace]
            local original  = namespace[catalog.method]
            local calls     = 0
            namespace[catalog.method] = function(...)
                calls = calls + 1
                return original(...)
            end
            h:start()
            for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
                h:event(event)
                h:advance(0.1)
            end
            h:advance(4)
            assert(calls == 2 and #h:records(catalog.kind) == 1)
            assert(h:last(catalog.kind).capture.event == "PLAYER_ENTERING_WORLD")
            for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
                h:event(event)
                h:advance(0.5)
            end
            assert(calls == 2 and #h:records(catalog.kind) == 1)
            h.FT.Dispatch("FT_CATALOG")
            for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
                h:event(event)
            end
            h:advance(4)
            assert(calls == 4 and #h:records(catalog.kind) == 2)
            assert(h:last(catalog.kind).capture.method == "manual_catalog")
            h:assertHealthy()
        end
    end },
    { name = "world transitions pause and recovery still reset queued quest comparisons", run = function(Host)
        for _, boundary in ipairs({ "world", "pause", "recovery" }) do
            local h     = Host.new()
            local state = quest(h)
            local ran   = false
            h:start()
            local previous = h:last("quest.snapshot")
            state.progress = 2
            h:event("QUEST_LOG_UPDATE")
            h.FT.Schedule("test.pending", 0.1, function()
                ran = true
            end)
            if boundary == "world" then
                h:event("PLAYER_LEAVING_WORLD")
                assert(h.FT.InWorld == false)
                for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
                    h:event(event)
                end
                h:advance(0.5)
                assert(#h:records("world.context") == 1 and #h:records("quest.snapshot") == 1)
                h:event("PLAYER_ENTERING_WORLD", false, false)
            elseif boundary == "pause" then
                h.FT.Pause(true)
                h:advance(0.5)
                h.FT.Pause(false)
            else
                h.FT.ResetCollectors("collector_error")
            end
            h:advance(2)
            local baseline = h:last("quest.snapshot")
            assert(not ran and baseline.data.quest_run_id ~= previous.data.quest_run_id)
            assert(baseline.data.baseline == true and #h:records("quest.objective_delta") == 0)
            state.progress = 3
            h:event("QUEST_LOG_UPDATE")
            h:advance(0.5)
            assert(h:last("quest.objective_delta").data.amount == 1)
            assert(h:last("quest.objective_delta").data.quest_run_id == baseline.data.quest_run_id)
            h:assertHealthy()
        end
    end },
    { name = "sightings preserve creature and observer without inventing deaths", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        h:event("NAME_PLATE_UNIT_ADDED", "nameplate1")
        local sighting = h:last("unit.sighting")
        assert(sighting.data.creature_id == 7001 and sighting.location.subject == "player")
        h:event("NAME_PLATE_UNIT_REMOVED", "nameplate1")
        assert(#h:records("unit.death") == 0)
        assert(#h:records("unit.sighting") == 1)
        h:assertHealthy()
    end },
    { name = "player and secret identities never become creature data", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        h.env.UnitGUID = function()
            return "Player-123-Private"
        end
        h:event("PLAYER_TARGET_CHANGED")
        h.env.UnitGUID = function()
            return { secret = true }
        end
        h:event("PLAYER_TARGET_CHANGED")
        assert(#h:records("unit.sighting") == 0)
        h:assertHealthy()
    end },
    { name = "merchant offers retain costs and do not become purchases", run = function(Host)
        local h = Host.new()
        creature(h)
        h.env.GetMerchantNumItems = function()
            return 1
        end
        h.env.GetMerchantItemLink = function()
            return "|Hitem:8111:0|h[Leaf]|h"
        end
        h.env.C_MerchantFrame.GetItemInfo = function()
            return { name = "Leaf", price = 55, stackCount = 2, numAvailable = -1, hasExtendedCost = true }
        end
        h.env.GetMerchantItemCostInfo = function()
            return 1
        end
        h.env.GetMerchantItemCostItem = function()
            return 100, 3, "|Hitem:8112:0|h[Token]|h"
        end
        h.env.UnitPosition = function()
            return 1, 2, 3, 99
        end
        h:start()
        h:event("MERCHANT_SHOW")
        h:advance(1)
        h:event("MERCHANT_UPDATE")
        local offer = h:last("merchant.offer")
        assert(#h:records("merchant.offer") == 1)
        assert(offer.data.costs[1].quantity == 3 and offer.data.npc.creature_id == 7001)
        assert(#h:records("item.received") == 0)
        h:event("MERCHANT_CLOSED")
        h:event("MERCHANT_SHOW")
        assert(#h:records("merchant.offer") == 2)
        h:assertHealthy()
    end },
    { name = "periodic reads do not fabricate game events", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        h:advance(5)
        local sighting = h:last("unit.sighting")
        assert(sighting and sighting.capture.event == nil and sighting.capture.method == "periodic_sample")
        assert(h:last("location.sample").capture.method == "periodic_sample")
        h:assertHealthy()
    end },
    { name = "cast success identifies spell without claiming gathering or loot", run = function(Host)
        local h = Host.new()
        h.env.C_Spell.GetSpellInfo = function(id)
            assert(id == 1234)
            return { name = "Gather", castTime = 1500 }
        end
        h:start()
        h:event("UNIT_SPELLCAST_SUCCEEDED", "player", "private-cast-guid", 1234)
        h:advance(0.2)
        local record = h:last("spell.succeeded")
        assert(record.data.spell_id == 1234 and record.data.cast_guid == nil)
        assert(h:last("spell.metadata").related_observation_ids[1] == record.observation_id)
        assert(#h:records("loot.visible") == 0)
        h:assertHealthy()
    end },
    { name = "clearing history allows spell metadata to be captured again", run = function(Host)
        local h = Host.new()
        h.env.C_Spell.GetSpellInfo = function()
            return { name = "Known spell" }
        end
        h:start()
        h:event("UNIT_SPELLCAST_SUCCEEDED", "player", "cast", 123)
        h:advance(0.2)
        assert(#h:records("spell.metadata") == 1)
        assert(h.FT.Clear())
        h:event("UNIT_SPELLCAST_SUCCEEDED", "player", "cast", 123)
        h:advance(0.2)
        assert(#h:records("spell.metadata") == 1)
        h:assertHealthy()
    end },
    { name = "changing unit identity invalidates the complete sighting", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        local calls = 0
        h.env.UnitGUID = function()
            calls = calls + 1
            return calls == 1 and "Creature-0-1-2-3-7001-A" or "Creature-0-1-2-3-8002-B"
        end
        h:event("PLAYER_TARGET_CHANGED")
        assert(#h:records("unit.sighting") == 0)
        h:assertHealthy()
    end },
    { name = "invalid map identifiers never form valid coordinates", run = function(Host)
        local h = Host.new()
        h:start()
        for _, map in ipairs({ 0, -1, 1.5 }) do
            h.state.map = map
            local location = h.FT.Location()
            assert(location.status == "unavailable" and location.reason == "invalid_result")
            assert(location.x == nil and location.ui_map_id == nil)
        end
        h:assertHealthy()
    end },
    { name = "missing merchant metadata and invalid cost counts remain partial", run = function(Host)
        local h = Host.new()
        creature(h)
        h.env.GetMerchantNumItems = function()
            return 1
        end
        h.env.GetMerchantItemCostInfo = function()
            return -1
        end
        h:start()
        h:event("MERCHANT_SHOW")
        local offer = h:last("merchant.offer")
        assert(offer.data.completeness == "partial")
        assert(offer.missing_fields["data.name"] == "not_ready")
        assert(offer.missing_fields["data.costs"] == "invalid_result")
        h.env.GetMerchantItemCostInfo = function()
            return 17
        end
        h.env.GetMerchantItemCostItem = function()
            return 1, 2, "|Hitem:8112:0|h[Token]|h"
        end
        h:event("MERCHANT_UPDATE")
        offer = h:last("merchant.offer")
        assert(#offer.data.costs == 16 and offer.missing_fields["data.costs"] == "capacity_limit")
        h:assertHealthy()
    end },
    { name = "recipe reagent truncation and unreadable rows declare incomplete coverage", run = function(Host)
        local h = Host.new()
        h.env.C_TradeSkillUI.GetRecipeInfo = function()
            return { name = "Synthetic recipe" }
        end
        h.env.C_TradeSkillUI.GetRecipeSchematic = function()
            local slots = {}
            for index = 1, 33 do
                local reagents = {}
                for reagent = 1, 17 do
                    reagents[reagent] = { itemID = reagent }
                end
                slots[index] = { quantityRequired = 1, required = true, reagentType = 1, reagents = reagents }
            end
            slots[2] = {}
            return { reagentSlotSchematics = slots }
        end
        h:start()
        h:event("NEW_RECIPE_LEARNED", 123)
        local recipe = h:last("recipe.metadata")
        assert(#recipe.data.reagent_slots == 32)
        assert(#recipe.data.reagent_slots[1].reagents == 16)
        assert(recipe.data.completeness == "partial")
        assert(recipe.missing_fields["data.reagent_slots"] == "capacity_limit")
        assert(recipe.missing_fields["data.reagent_slots.1.reagents"] == "capacity_limit")
        assert(recipe.missing_fields["data.reagent_slots.2.reagents"] == "not_ready")
        h:assertHealthy()
    end },
    { name = "profession baseline catalogs already known recipes with direct ownership and requirements", run = function(Host)
        local h = Host.new()
        profession(h, 3)
        h:start()
        assert(#h:records("recipe.metadata") == 0)
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        local scan   = h:last("recipe.scan")
        local recipe = h:last("recipe.metadata")
        assert(#h:records("recipe.metadata") == 3 and #h:records("recipe.learned") == 0)
        assert(scan.data.returned_count == 3 and scan.data.processed_count == 3)
        assert(scan.data.completeness == "complete" and scan.data.enumeration_complete == true)
        assert(scan.data.enumeration_contract == "unverified_runtime_probe" and scan.data.profession_coverage == "unverified")
        assert(recipe.data.profession_id == 164 and recipe.data.quantity_max == 2)
        assert(recipe.data.reagent_slots[1].reagents[2].currencyID == 23)
        assert(recipe.data.reagent_slots[1].variable_quantities[1].quantity == 3)
        assert(recipe.data.requirements[1].met == false and recipe.data.quality_item_ids[2] == 8112)
        assert(#scan.related_observation_ids == 3)
        h:assertHealthy()
    end },
    { name = "profession rescans deduplicate metadata while manual scans retain scope evidence", run = function(Host)
        local h     = Host.new()
        local state = profession(h, 2)
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        h:event("TRADE_SKILL_DATA_SOURCE_CHANGED")
        h:advance(1)
        assert(#h:records("recipe.metadata") == 2 and #h:records("recipe.scan") == 1)
        h.FT.Dispatch("FT_CATALOG")
        h:advance(1)
        assert(#h:records("recipe.metadata") == 2 and #h:records("recipe.scan") == 2)
        assert(h:last("recipe.scan").capture.method == "manual_catalog")
        state.name = "Updated recipe"
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        assert(#h:records("recipe.metadata") == 4 and h:last("recipe.metadata").data.name == state.name)
        h:assertHealthy()
    end },
    { name = "filtered recipe enumeration never claims the entire profession", run = function(Host)
        local h     = Host.new()
        local state = profession(h, 2)
        h.env.C_TradeSkillUI.GetAllRecipeIDs = nil
        h.env.C_TradeSkillUI.GetFilteredRecipeIDs = function()
            return state.ids
        end
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        local scan = h:last("recipe.scan")
        assert(scan.data.scope == "currently_viewed_profession_filtered")
        assert(scan.data.profession_coverage == "filtered" and scan.data.enumeration_complete == true)
        assert(scan.data.enumeration_method == "C_TradeSkillUI.GetFilteredRecipeIDs")
        h:assertHealthy()
    end },
    { name = "missing recipe output and unavailable enumeration remain explicit gaps", run = function(Host)
        local h = Host.new()
        profession(h, 1)
        h.env.C_TradeSkillUI.GetRecipeSchematic = function(id)
            return { recipeID = id, reagentSlotSchematics = {} }
        end
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        local recipe = h:last("recipe.metadata")
        local scan   = h:last("recipe.scan")
        assert(recipe.data.output_item_id == nil and recipe.data.output_status == "not_observed")
        assert(recipe.missing_fields["data.output_item_id"] == "not_observed")
        assert(recipe.missing_fields["data.quantity_min"] == "not_ready")
        assert(scan.data.partial_recipe_count == 1 and scan.data.completeness == "partial")
        h.env.C_TradeSkillUI.GetAllRecipeIDs = nil
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        scan = h:last("recipe.scan")
        assert(scan.data.enumeration_complete == false and scan.data.returned_count == nil)
        assert(scan.missing_fields["data.recipe_ids"] == "not_ready_or_unsupported")
        h:assertHealthy()
    end },
    { name = "recipe enumeration is bounded and source closure preserves incomplete scan status", run = function(Host)
        local h = Host.new()
        profession(h, 2050)
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(0.3)
        assert(#h:records("recipe.metadata") == 8)
        h:event("TRADE_SKILL_CLOSE")
        h:advance(2)
        local scan = h:last("recipe.scan")
        assert(scan.data.returned_count == 2050 and scan.data.enumerated_count == 2048)
        assert(scan.data.processed_count == 8 and #h:records("recipe.metadata") == 8)
        assert(scan.data.enumeration_complete == false and scan.data.completeness == "partial")
        assert(scan.missing_fields["data.recipe_ids"] == "capacity_limit")
        assert(scan.missing_fields["data.scan"] == "data_source_closed_or_changing")
        h:assertHealthy()
    end },
    { name = "clearing during profession scan cancels stale work and resets metadata deduplication", run = function(Host)
        local h = Host.new()
        profession(h, 17)
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(0.3)
        assert(#h:records("recipe.metadata") == 8)
        assert(h.FT.Clear())
        h:advance(2)
        assert(#h:records("recipe.metadata") == 0 and #h:records("recipe.scan") == 0)
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        assert(#h:records("recipe.metadata") == 17)
        assert(h:last("recipe.scan").data.processed_count == 17)
        h:assertHealthy()
    end },
    { name = "profession source changes cannot mix recipes from different views", run = function(Host)
        local h     = Host.new()
        local state = profession(h, 17)
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(0.3)
        state.profession_id = 171
        state.source_counter = 2
        state.ids = { 4000 }
        h:event("TRADE_SKILL_DATA_SOURCE_CHANGED")
        h:advance(1)
        local scans = h:records("recipe.scan")
        assert(#scans == 2 and scans[1].data.processed_count == 8)
        assert(scans[1].data.completeness == "partial" and scans[2].data.profession_id == 171)
        assert(#h:records("recipe.metadata") == 9 and h:last("recipe.metadata").data.profession_id == 171)
        h:assertHealthy()
    end },
    { name = "learning and crafting retain direct evidence without guessed recipe attribution", run = function(Host)
        local h = Host.new()
        profession(h, 1)
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        h:event("NEW_RECIPE_LEARNED", 1001, 2, 1000)
        local learned = h:last("recipe.learned")
        local recipe  = h:last("recipe.metadata")
        assert(learned.data.recipe_level == 2 and learned.data.base_recipe_id == 1000)
        assert(recipe.related_observation_ids[1] == learned.observation_id)
        h:event("TRADE_SKILL_ITEM_CRAFTED_RESULT", { itemID = 8111, quantity = 2, operationID = 35, recipeID = 1001 })
        local craft = h:last("craft.result")
        assert(craft.data.operationID == 35 and craft.data.quantity == 2)
        assert(craft.data.recipe_id == nil and craft.data.recipeID == nil)
        assert(craft.missing_fields["data.recipe_id"] == "not_observed")
        h:assertHealthy()
    end },
    { name = "recipe identity mismatches never attach metadata from another recipe", run = function(Host)
        local h = Host.new()
        profession(h, 1)
        h.env.C_TradeSkillUI.GetRecipeInfo = function()
            return { recipeID = 9999, name = "Wrong recipe", learned = true }
        end
        h.env.C_TradeSkillUI.GetRecipeSchematic = function()
            return { recipeID = 9999, outputItemID = 5000, quantityMin = 1, quantityMax = 1, reagentSlotSchematics = {} }
        end
        h:start()
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        local recipe = h:last("recipe.metadata")
        assert(recipe.data.recipe_id == 1001 and recipe.data.name == nil and recipe.data.output_item_id == nil)
        assert(recipe.missing_fields["data.info"] == "identity_mismatch")
        assert(recipe.missing_fields["data.schematic"] == "identity_mismatch")
        assert(h:last("recipe.scan").data.completeness == "partial")
        h:assertHealthy()
    end },
    { name = "profession scan stops cleanly when recording capacity resets collectors", run = function(Host)
        local h     = Host.new()
        local state = profession(h, 17)
        h:start()
        h.FT.LIMITS.records = h.FT.Export().record_count + 2
        h:event("TRADE_SKILL_SHOW")
        h:advance(1)
        assert(h.FT.Status().blocked == "capacity_limit")
        assert(h.FT.ProfessionStatus().scanning == false)
        local reads = state.reads
        h:advance(1)
        assert(state.reads == reads and reads < 17)
        h:assertHealthy()
    end },
    { name = "readable NPC casts identify the caster and deduplicate shared unit tokens", run = function(Host)
        local h = Host.new()
        creature(h)
        h.env.C_Spell.GetSpellInfo = function(id)
            return { name = "Observed ability", spellID = id }
        end
        h:start()
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "npc-cast-1", 5678)
        h:event("UNIT_SPELLCAST_SUCCEEDED", "nameplate1", "npc-cast-1", 5678)
        h:advance(0.2)
        local cast = h:last("spell.succeeded")
        assert(#h:records("spell.succeeded") == 1 and cast.data.actor == "npc")
        assert(cast.data.npc.creature_id == 7001 and cast.data.target == nil)
        assert(cast.data.cast_guid == nil and cast.data.cast_identity_status == "readable_deduplicated")
        assert(h:last("spell.metadata").related_observation_ids[1] == cast.observation_id)
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "npc-cast-2", 5678)
        assert(#h:records("spell.succeeded") == 2)
        assert(h.FT.Clear())
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "npc-cast-1", 5678)
        assert(#h:records("spell.succeeded") == 1)
        h:assertHealthy()
    end },
    { name = "restricted NPC casts and player identities never become NPC abilities", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        h:event("UNIT_SPELLCAST_SUCCEEDED", { secret = true }, "private", 5678)
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "private", { secret = true })
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "private", 1.5)
        h:event("UNIT_SPELLCAST_SUCCEEDED", "party1", "private", 5678)
        assert(#h:records("spell.succeeded") == 0)
        h.env.UnitGUID = function()
            return "Player-123-Private"
        end
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", "private", 5678)
        assert(#h:records("spell.succeeded") == 0)
        creature(h)
        h:event("UNIT_SPELLCAST_SUCCEEDED", "target", { secret = true }, 5678)
        local cast = h:last("spell.succeeded")
        assert(cast.data.actor == "npc" and cast.data.cast_identity_status == "unavailable")
        assert(cast.missing_fields["data.cast_identity"] == "not_ready_or_restricted")
        h:assertHealthy()
    end },
    { name = "NPC service roles require actual opened interactions and an identified NPC", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        for event, service in pairs({ TRAINER_SHOW = "trainer", BANKFRAME_OPENED = "bank", TAXIMAP_OPENED = "flight_master" }) do
            h:event(event)
            local record = h:last("interaction.snapshot")
            assert(record.data.service == service and record.data.npc.creature_id == 7001)
            assert(record.capture.event == event and record.data.scope == "opened_npc_service")
        end
        local count = #h:records("interaction.snapshot")
        h.env.UnitGUID = function()
            return nil
        end
        h:event("TRAINER_SHOW")
        assert(#h:records("interaction.snapshot") == count)
        h:assertHealthy()
    end },
    { name = "NPC descriptors report unreadable fields and unavailable native positions", run = function(Host)
        local h = Host.new()
        creature(h)
        h:start()
        h:event("NAME_PLATE_UNIT_ADDED", "nameplate1")
        local sighting = h:last("unit.sighting")
        assert(sighting.data.name == "Forest Sentinel" and sighting.data.level == 6)
        for _, key in ipairs({ "classification", "creature_type", "reaction", "max_health" }) do
            assert(sighting.missing_fields["data." .. key] == "not_ready_or_restricted")
        end
        assert(sighting.data.entity_position == nil)
        assert(sighting.missing_fields["data.entity_position"] == "native_position_unavailable")
        h:assertHealthy()
    end },
}
