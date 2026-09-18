local _, FT = ...

local previous   = {}
local bankOpen   = false
local generation = 0
local MAX_SLOTS  = 1000

local function integer(value, minimum, maximum)
    value = FT.Value(value, "number")
    if value and value % 1 == 0 and value >= minimum and value <= maximum then
        return value
    end
end

local function publish(scope, items, containers, slots, missing, event)
    local data = {
        scope = scope, items = items, container_ids = containers, scanned_slots = slots,
        completeness = next(missing) and "partial" or "complete", quantities_meaning = "observed_storage_only",
    }
    local comparison = { data = data, missing = missing }
    if FT.Equal(previous[scope], comparison) then
        return
    end
    local id = FT.Emit("inventory.storage", data, event, "api_snapshot", nil, missing)
    if not id then
        return
    end
    previous[scope] = FT.Copy(comparison)
    for _, item in ipairs(items) do
        FT.RequestItem(item.item_id, item.link, id)
    end
end

local function equipment(event)
    local items   = {}
    local missing = {}
    local first   = integer(INVSLOT_FIRST_EQUIPPED, 1, 32) or 1
    local last    = integer(INVSLOT_LAST_EQUIPPED, first, 32) or 19
    for slot = first, last do
        local ok, itemID = FT.TryCall("GetInventoryItemID", "player", slot)
        if not ok then
            missing["equipment." .. slot] = "not_ready_or_restricted"
        elseif itemID ~= nil then
            itemID = integer(itemID, 1, 2147483647)
            local link = FT.Value(FT.Call("GetInventoryItemLink", "player", slot), "string")
            if not itemID then
                missing["equipment." .. slot] = "invalid_result"
            else
                items[#items + 1] = { item_id = itemID, link = link, equipment_slot = slot }
                if not link then
                    missing["equipment." .. slot .. ".link"] = "not_ready_or_restricted"
                end
            end
        end
    end
    publish("equipped_items", items, {}, last - first + 1, missing, event)
end

local function containers(scope, ids, event, initialMissing)
    local items   = {}
    local missing = initialMissing or {}
    local slots   = 0
    local seen    = {}
    for _, bag in ipairs(ids) do
        if not seen[bag] then
            seen[bag] = true
            local count = integer(FT.Call("C_Container.GetContainerNumSlots", bag), 0, MAX_SLOTS)
            if not count or slots + count > MAX_SLOTS then
                missing["bag." .. bag] = count and "capacity_limit" or "not_ready_or_restricted"
            else
                for slot = 1, count do
                    local ok, row = FT.TryCall("C_Container.GetContainerItemInfo", bag, slot)
                    local path    = "bag." .. bag .. ".slot." .. slot
                    if not ok then
                        missing[path] = "not_ready_or_restricted"
                    elseif row ~= nil then
                        local itemID   = integer(FT.Field(row, "itemID", "number"), 1, 2147483647)
                        local quantity = integer(FT.Field(row, "stackCount", "number"), 1, 1000000000)
                        local link     = FT.Field(row, "hyperlink", "string")
                        if not itemID then
                            missing[path] = "not_ready_or_restricted"
                        else
                            items[#items + 1] = { item_id = itemID, link = link, quantity = quantity, bag = bag, slot = slot }
                            if not quantity or not link then
                                missing[path] = "partial_item"
                            end
                        end
                    end
                end
                slots = slots + count
            end
        end
    end
    publish(scope, items, ids, slots, missing, event)
end

local function scan(event)
    if not FT.Profile.supported or not FT.InWorld then
        return
    end
    equipment(event)
    local constants = FT.Field(Constants, "InventoryConstants", "table")
    local bags      = integer(FT.Field(constants, "NumBagSlots", "number"), 0, 16)
    local reagents  = integer(FT.Field(constants, "NumReagentBagSlots", "number"), 0, 4)
    local ids       = {}
    local missing   = {}
    if bags == nil or reagents == nil then
        bags, reagents = bags or 4, reagents or 0
        missing.container_scope = "inventory_constants_unavailable"
    end
    for bag = 0, bags + reagents do
        ids[#ids + 1] = bag
    end
    containers("carried_containers", ids, event, missing)
    if not bankOpen then
        return
    end
    local ok, types = FT.TryCall("C_Bank.FetchViewableBankTypes")
    local count     = FT.Length(types)
    if not ok or not count or count > 8 then
        publish("accessible_bank", {}, {}, 0, { bank_types = "not_ready_or_unsupported" }, event)
        return
    end
    for index = 1, count do
        local bankType = integer(FT.Field(types, index, "number"), 0, 16)
        if bankType and FT.Call("C_Bank.CanViewBank", bankType) == true then
            local tabs     = FT.Call("C_Bank.FetchPurchasedBankTabIDs", bankType)
            local tabCount = FT.Length(tabs)
            local bankIDs  = {}
            local absent   = {}
            if not tabCount or tabCount > 32 then
                absent.bank_tabs = tabCount and "capacity_limit" or "not_ready_or_restricted"
            end
            for tab = 1, math.min(tabCount or 0, 32) do
                local id = integer(FT.Field(tabs, tab, "number"), -10, 100)
                if id then
                    bankIDs[#bankIDs + 1] = id
                else
                    absent["bank_tabs." .. tab] = "invalid_result"
                end
            end
            containers("bank_type_" .. bankType, bankIDs, event, absent)
        elseif not bankType then
            publish("accessible_bank", {}, {}, 0, { bank_type = "invalid_result" }, event)
        end
    end
end

local function schedule(event)
    local current = generation
    FT.Schedule("inventory.storage", 0.3, function()
        if current == generation then
            scan({ event = event, method = "deferred_storage_snapshot" })
        end
    end)
end

for _, event in ipairs({ "PLAYER_ENTERING_WORLD", "PLAYER_EQUIPMENT_CHANGED", "BAG_UPDATE_DELAYED",
                         "PLAYERBANKSLOTS_CHANGED", "BANK_TAB_SETTINGS_UPDATED" }) do
    FT.On(event, schedule)
end
FT.On("FT_BASELINE", function()
    schedule(nil)
end)
FT.On("FT_CATALOG", function()
    previous = {}
    schedule(nil)
end)
FT.On("BANKFRAME_OPENED", function(event)
    bankOpen = true
    schedule(event)
end)
FT.On("BANKFRAME_CLOSED", function()
    bankOpen = false
end)
FT.OnReset(function()
    generation = generation + 1
    previous   = {}
    bankOpen   = false
end)
