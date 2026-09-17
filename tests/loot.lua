local function configured(Host)
    local host   = Host.new()
    local state  = { loot = {}, bags = {}, metadata = {}, requested = {} }
    host.env.GetNumLootItems = function()
        return #state.loot
    end
    host.env.GetLootSlotType = function(slot)
        return state.loot[slot] and state.loot[slot].kind or nil
    end
    host.env.GetLootSlotLink = function(slot)
        return state.loot[slot] and state.loot[slot].link or nil
    end
    host.env.GetLootSlotInfo = function(slot)
        local item = state.loot[slot]
        if item then
            return 134400, item.name, item.quantity, item.currency_id, 2, false, false, nil, false, item.kind == 2
        end
    end
    host.env.C_Container = {
        GetContainerNumSlots = function(bag)
            return bag == 0 and 4 or 0
        end,
        GetContainerItemInfo = function(bag, slot)
            if state.bag_error then
                error("simulated transient bag read failure")
            end
            if bag == 0 then
                return state.bags[slot]
            end
        end,
    }
    host.env.C_Item = {
        GetItemInfo = function(item)
            local metadata = state.metadata[item]
            if metadata then
                return metadata.name, metadata.link, 2, 10, 1, "Armor", "Cloth", 20, "INVTYPE_HEAD", 134400, 125, 4, 1, 2, 0, nil, false, "A test item"
            end
        end,
        RequestLoadItemDataByID = function(itemID)
            state.requested[#state.requested + 1] = itemID
        end,
    }
    host.env.LOOT_ITEM_SELF          = "You receive loot: %s."
    host.env.LOOT_ITEM_SELF_MULTIPLE = "You receive loot: %sx%d."
    host:start()
    host:advance(0.3)
    return host, state
end

local firstLink  = "|cff1eff00|Hitem:101:0:0:0:0:0:11:0|h[Test Hood]|h|r"
local secondLink = "|cff1eff00|Hitem:101:0:0:0:0:0:12:0|h[Test Hood]|h|r"

return {
    {
        name = "loot target and mouseover observations remain candidates without source attribution",
        run = function(Host)
            local host, state = configured(Host)
            local targetGUID  = "Creature-0-1-2-3-1001-0000000001"
            local mouseGUID   = "Creature-0-1-2-3-1002-0000000002"
            host.env.UnitGUID = function(token)
                if token == "target" then
                    return targetGUID
                end
                if token == "mouseover" then
                    return mouseGUID
                end
            end
            host.env.UnitName = function(token)
                return token == "target" and "Nearby target" or "Nearby mouseover"
            end
            state.loot = { { kind = 1, link = firstLink, name = "Test Hood", quantity = 1 } }
            host:event("LOOT_OPENED", false, false)
            local interaction = host:last("loot.opened")
            local visible     = host:last("loot.visible")
            host:assertEqual(interaction.data.target_candidate.guid, targetGUID)
            host:assertEqual(interaction.data.mouseover_candidate.guid, mouseGUID)
            host:assertEqual(interaction.data.source_attribution, "unresolved")
            host:assertEqual(visible.data.source_status, "unknown")
            host:assertEqual(visible.data.sources, {})
            host:assertEqual(visible.missing_fields.sources, "unknown_source")
            host:event("LOOT_CLOSED")
            host.env.UnitGUID = function()
                return nil
            end
            host:event("LOOT_OPENED", false, false)
            host:assertEqual(host:last("loot.opened").data.target_candidate, nil)
            host:assertEqual(host:last("loot.opened").data.mouseover_candidate, nil)
            host:assertEqual(host:last("loot.visible").data.sources, {})
            host:assertHealthy()
        end,
    },
    {
        name = "loot readiness coalesces while reopening preserves distinct interactions",
        run = function(Host)
            local host, state = configured(Host)
            state.loot = { { kind = 1, link = firstLink, name = "Test Hood", quantity = 2 } }
            host:event("LOOT_READY", true)
            host:event("LOOT_OPENED", true, false)
            host:event("LOOT_READY", true)
            host:assertEqual(#host:records("loot.opened"), 1)
            host:assertEqual(#host:records("loot.visible"), 1)
            local first = host:last("loot.visible")
            host:assertEqual(first.data.source_status, "unknown")
            host:assertEqual(first.missing_fields.sources, "unknown_source")
            host:event("LOOT_SLOT_CLEARED", 1)
            host:event("LOOT_SLOT_CLEARED", 1)
            host:assertEqual(#host:records("loot.slot_cleared"), 1)
            host:assertEqual(#host:records("item.received"), 0)
            host:event("LOOT_CLOSED")
            host:event("LOOT_OPENED", false, false)
            host:assertEqual(#host:records("loot.visible"), 2)
            host:assertTrue(first.data.loot_session_id ~= host:last("loot.visible").data.loot_session_id)
            host:assertEqual(first.data.quantity, 2)
            host:assertEqual(first.data.revision, 1)
            host:assertEqual(host:records("loot.visible")[1], first)
            host:assertHealthy()
        end,
    },
    {
        name = "loot money and unresolved item slots retain their own meanings",
        run = function(Host)
            local host, state = configured(Host)
            state.loot = {
                { kind = 2, name = "12 Silver", quantity = 0 },
                { kind = 1, name = "Uncached Reward", quantity = 1 },
            }
            host:event("LOOT_READY", true)
            local records = host:records("loot.visible")
            host:assertEqual(#records, 2)
            host:assertEqual(records[1].data.slot_kind, "money")
            host:assertEqual(records[1].data.item_id, nil)
            host:assertEqual(records[1].data.quantity, 0)
            host:assertEqual(records[2].data.slot_kind, "item")
            host:assertEqual(records[2].data.name, "Uncached Reward")
            host:assertEqual(records[2].missing_fields.item_id, "not_ready")
            host:assertEqual(host:last("loot.snapshot").data.completeness, "partial")
            host:assertHealthy()
        end,
    },
    {
        name = "item metadata keeps link variants and enriches after loot closes",
        run = function(Host)
            local host, state = configured(Host)
            state.loot = {
                { kind = 1, link = firstLink, name = "Test Hood", quantity = 1 },
                { kind = 1, link = secondLink, name = "Test Hood", quantity = 3 },
            }
            host:event("LOOT_OPENED", false, false)
            local visible = host:records("loot.visible")
            local prefix  = host:records()
            host:event("LOOT_CLOSED")
            state.metadata[firstLink]  = { name = "First Variant", link = firstLink }
            state.metadata[secondLink] = { name = "Second Variant", link = secondLink }
            host:event("ITEM_DATA_LOAD_RESULT", 999, true)
            host:assertEqual(#host:records("item.metadata"), 0)
            host:event("ITEM_DATA_LOAD_RESULT", 101, true)
            host:event("GET_ITEM_INFO_RECEIVED", 101, true)
            local metadata = host:records("item.metadata")
            host:assertEqual(#metadata, 2)
            local linked = {}
            for _, record in ipairs(metadata) do
                linked[record.data.requested_link] = record.related_observation_ids[1]
            end
            host:assertEqual(linked[firstLink], visible[1].observation_id)
            host:assertEqual(linked[secondLink], visible[2].observation_id)
            host:assertEqual(visible[1].data.name, "Test Hood")
            host:assertEqual(visible[2].data.quantity, 3)
            host:assertEqual(#host:records("item.received"), 0)
            local final = host:records()
            for index, original in ipairs(prefix) do
                host:assertEqual(final[index], original)
            end
            host:assertHealthy()
        end,
    },
    {
        name = "metadata times out once without discarding the visible item",
        run = function(Host)
            local host, state = configured(Host)
            state.loot = { { kind = 1, link = firstLink, name = "Test Hood", quantity = 1 } }
            host:event("LOOT_READY", true)
            host:advance(16)
            host:assertEqual(#host:records("item.metadata_unresolved"), 1)
            host:assertEqual(host:last("item.metadata_unresolved").data.status, "timeout")
            host:assertEqual(#host:records("loot.visible"), 1)
            state.metadata[firstLink] = { name = "Late metadata", link = firstLink }
            host:event("ITEM_DATA_LOAD_RESULT", 101, true)
            host:assertEqual(#host:records("item.metadata"), 0)
            host:assertHealthy()
        end,
    },
    {
        name = "bag moves do not become gains and read failures invalidate comparisons",
        run = function(Host)
            local host, state = configured(Host)
            state.bags[1] = { itemID = 101, hyperlink = firstLink, stackCount = 3 }
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(host:last("inventory.delta").data.delta, 3)
            local deltaCount = #host:records("inventory.delta")
            state.bags[2] = state.bags[1]
            state.bags[1] = nil
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(#host:records("inventory.delta"), deltaCount)
            state.bag_error = true
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(#host:records("inventory.delta"), deltaCount)
            host:assertEqual(host:last("inventory.snapshot").data.completeness, "partial")
            state.bag_error         = false
            state.bags[2].stackCount = 8
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(#host:records("inventory.delta"), deltaCount)
            state.bags[2].stackCount = 9
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(host:last("inventory.delta").data.delta, 1)
            host:assertEqual(#host:records("item.received"), 0)
            deltaCount = #host:records("inventory.delta")
            state.bags[2].secret = true
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(#host:records("inventory.delta"), deltaCount)
            host:assertEqual(host:last("inventory.snapshot").data.completeness, "partial")
            host:assertHealthy()
        end,
    },
    {
        name = "localized local loot receipt strips social payload and preserves repeated awards",
        run = function(Host)
            local host = configured(Host)
            host.env.LOOT_ITEM_SELF_MULTIPLE = "Vous recevez %2$dx %1$s."
            host:event("CHAT_MSG_LOOT", "AnotherPlayer receives loot: " .. firstLink .. ".", "AnotherPlayer", "", "", "SocialIdentifier")
            host:assertEqual(#host:records("item.received"), 0)
            local message = "Vous recevez 3x " .. firstLink .. "."
            host:event("CHAT_MSG_LOOT", message, "PrivateName", "", "", "PrivateRealm")
            host:event("CHAT_MSG_LOOT", message, "PrivateName", "", "", "PrivateRealm")
            host:assertEqual(#host:records("item.received"), 2)
            local receipt = host:last("item.received")
            host:assertEqual(receipt.data.quantity, 3)
            host:assertEqual(receipt.data.link, firstLink)
            host:assertEqual(receipt.data.recipient, "local_player")
            host:assertEqual(receipt.data.source_status, "unknown")
            host:assertEqual(receipt.data.message, nil)
            host:assertEqual(receipt.data.player_name, nil)
            host:assertHealthy()
        end,
    },
    {
        name = "late item callbacks after reset do not attach to stale observations",
        run = function(Host)
            local host, state = configured(Host)
            state.loot = { { kind = 1, link = firstLink, name = "Test Hood", quantity = 1 } }
            host:event("LOOT_READY", true)
            host.FT.ResetCollectors("test_gap")
            state.metadata[firstLink] = { name = "New metadata", link = firstLink }
            host:event("ITEM_DATA_LOAD_RESULT", 101, true)
            host:advance(16)
            host:assertEqual(#host:records("item.metadata"), 0)
            host:assertEqual(#host:records("item.metadata_unresolved"), 0)
            host:assertHealthy()
        end,
    },
    {
        name = "metadata pending variants and timers remain bounded with explicit overflow",
        run = function(Host)
            local host, state = configured(Host)
            for variant = 1, 257 do
                local link = "|Hitem:101:0:0:0:0:0:" .. tostring(variant) .. ":0|h[Test Hood]|h"
                local id   = host.FT.Emit("test.item", { item_id = 101, link = link }, { method = "test_fixture" })
                host.FT.RequestItem(101, link, id)
            end
            host:assertEqual(#state.requested, 256)
            host:assertEqual(#host:records("item.metadata_unresolved"), 1)
            host:assertEqual(host:last("item.metadata_unresolved").data.status, "capacity_limit")
            host:advance(16)
            host:assertEqual(#host:records("item.metadata_unresolved"), 257)
            host:assertEqual(#host:records("test.item"), 257)
            host:assertHealthy()
        end,
    },
    {
        name = "storage saturation during loot or inventory capture preserves the prefix without collector errors",
        run = function(Host)
            for budget = 0, 3 do
                local host, state = configured(Host)
                local prefix      = host:records()
                host.FT.LIMITS.records = #prefix + budget
                state.loot = {
                    { kind = 1, link = firstLink, name = "Test Hood", quantity = 1 },
                    { kind = 1, link = secondLink, name = "Test Hood", quantity = 2 },
                }
                state.metadata[firstLink] = { name = "Cached metadata", link = firstLink }
                host:event("LOOT_READY", true)
                host:assertTrue(host.FT.Status().records <= #prefix + budget)
                local final = host:records()
                for index, original in ipairs(prefix) do
                    host:assertEqual(final[index], original)
                end
                host:assertHealthy()
            end
            local host, state = configured(Host)
            host.FT.LIMITS.records = host.FT.Status().records + 2
            state.bags = {
                { itemID = 101, hyperlink = firstLink, stackCount = 1 },
                { itemID = 102, hyperlink = "|Hitem:102|h[Other Item]|h", stackCount = 1 },
            }
            host:event("BAG_UPDATE_DELAYED")
            host:advance(0.3)
            host:assertEqual(host.FT.Status().blocked, "capacity_limit")
            host:assertHealthy()
        end,
    },
}
