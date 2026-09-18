local function configured(Host)
    local h     = Host.new()
    local state = { equipped = {}, bags = {}, viewable = false }
    h.env.Constants = { InventoryConstants = { NumBagSlots = 4, NumReagentBagSlots = 1 } }
    h.env.GetInventoryItemID = function(_, slot)
        return state.equipped[slot] and state.equipped[slot].id
    end
    h.env.GetInventoryItemLink = function(_, slot)
        return state.equipped[slot] and state.equipped[slot].link
    end
    h.env.C_Container.GetContainerNumSlots = function(bag)
        return state.bags[bag] and #state.bags[bag] or 0
    end
    h.env.C_Container.GetContainerItemInfo = function(bag, slot)
        return state.bags[bag] and state.bags[bag][slot]
    end
    h.env.C_Bank = {
        FetchViewableBankTypes = function()
            return { 0 }
        end,
        CanViewBank = function()
            return state.viewable
        end,
        FetchPurchasedBankTabIDs = function()
            return { 6 }
        end,
    }
    return h, state
end

local function scope(h, name)
    local result
    for _, record in ipairs(h:records("inventory.storage")) do
        if record.data.scope == name then
            result = record
        end
    end
    return result
end

return {
    { name = "equipment and reagent bag discoveries preserve exact storage locations", run = function(Host)
        local h, state = configured(Host)
        state.equipped[1] = { id = 100, link = "item:100" }
        state.bags[5]    = { { itemID = 101, hyperlink = "item:101", stackCount = 7 } }
        h:start()
        local equipped = scope(h, "equipped_items")
        local carried  = scope(h, "carried_containers")
        assert(equipped.data.items[1].equipment_slot == 1 and equipped.data.items[1].item_id == 100)
        assert(equipped.data.items[1].quantity == nil)
        assert(carried.data.items[1].bag == 5 and carried.data.items[1].quantity == 7)
        assert(carried.data.completeness == "complete")
        h:assertHealthy()
    end },
    { name = "bank reads require opening and view permission and never imply acquisitions", run = function(Host)
        local h, state = configured(Host)
        state.bags[6] = { { itemID = 102, hyperlink = "item:102", stackCount = 3 } }
        h:start()
        assert(not scope(h, "bank_type_0"))
        h:event("BANKFRAME_OPENED")
        h:advance(0.4)
        assert(not scope(h, "bank_type_0"))
        state.viewable = true
        h:event("BAG_UPDATE_DELAYED")
        h:advance(0.4)
        assert(scope(h, "bank_type_0").data.items[1].quantity == 3)
        assert(#h:records("inventory.delta") == 0)
        h:event("BANKFRAME_CLOSED")
        state.bags[6][1].stackCount = 5
        h:event("BAG_UPDATE_DELAYED")
        h:advance(0.4)
        assert(scope(h, "bank_type_0").data.items[1].quantity == 3)
        h:assertHealthy()
    end },
    { name = "unreadable equipment and slots declare partial scans", run = function(Host)
        local h, state = configured(Host)
        state.equipped[2] = { id = 100 }
        state.bags[5]    = { { itemID = 101 } }
        h:start()
        assert(scope(h, "equipped_items").missing_fields["equipment.2.link"])
        assert(scope(h, "carried_containers").data.completeness == "partial")
        assert(scope(h, "carried_containers").data.items[1].quantity == nil)
        h:assertHealthy()
    end },
    { name = "unchanged storage does not duplicate scans and leaving cancels deferred reads", run = function(Host)
        local h = configured(Host)
        h:start()
        local count = #h:records("inventory.storage")
        h:event("BAG_UPDATE_DELAYED")
        h:advance(0.4)
        assert(#h:records("inventory.storage") == count)
        h:event("PLAYER_EQUIPMENT_CHANGED", 1)
        h:event("PLAYER_LEAVING_WORLD")
        h:advance(0.4)
        assert(#h:records("inventory.storage") == count)
        h:assertHealthy()
    end },
    { name = "item metadata retains direct spell and socket links without inventing empty effects", run = function(Host)
        local h = configured(Host)
        h.env.C_Item.GetItemInfo = function()
            return "Test", "item:100", 2
        end
        h.env.C_Item.GetItemSpell = function()
            return "Effect", 123
        end
        h.env.C_Item.GetItemGem = function(_, index)
            if index == 1 then
                return "Gem", "item:456"
            end
        end
        h:start()
        local id = h.FT.Emit("item.received", { item_id = 100 }, "CHAT_MSG_LOOT")
        h.FT.RequestItem(100, "item:100", id)
        local data = h:last("item.metadata").data
        assert(data.item_spell_id == 123 and data.item_spell_status == "available")
        assert(#data.gems == 1 and data.gems[1].item_id == 456 and data.gems[1].socket_index == 1)
        h:assertHealthy()
    end },
    { name = "unknown clients do not collect extra inventory", run = function(Host)
        local h = Host.new(nil, "2.0", "99999")
        h:start()
        h:event("BANKFRAME_OPENED")
        h:advance(0.4)
        assert(#h:records("inventory.storage") == 0)
        h:assertHealthy()
    end },
}
