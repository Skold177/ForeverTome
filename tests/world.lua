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
}
