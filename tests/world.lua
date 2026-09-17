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

return {
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
