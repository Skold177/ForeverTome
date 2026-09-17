local _, FT = ...

local MAX_LOOT_SLOTS  = 200
local MAX_BAG_SLOTS   = 1000
local MAX_PENDING    = 256
local MAX_REFERENCES = 64
local ITEM_TIMEOUT   = 15
local activeLoot     = nil
local bagBaseline    = nil
local pendingItems   = {}
local pendingCount   = 0
local generation     = 0
local insideWorld    = true

local function number(value, minimum, maximum)
    value = FT.Value(value, "number")
    if value and value >= minimum and value <= maximum and value == math.floor(value) then
        return value
    end
end

local function same(first, second)
    if type(first) ~= type(second) then
        return false
    end
    if type(first) ~= "table" then
        return first == second
    end
    for key, value in pairs(first) do
        if not same(value, second[key]) then
            return false
        end
    end
    for key in pairs(second) do
        if first[key] == nil then
            return false
        end
    end
    return true
end

local function itemKey(itemID, link)
    return tostring(itemID) .. ":" .. (link or "")
end

local function itemAPI(method)
    if FT.Profile.item_info == "classic" then
        return method
    end
    if FT.Profile.item_info == "modern" then
        return "C_Item." .. method
    end
end

local function readItem(itemID, link)
    local method = itemAPI("GetItemInfo")
    if not method then
        return nil
    end
    local name, resolvedLink, quality, itemLevel, minimumLevel, itemType, subtype, stackSize,
        equipLocation, texture, sellPrice, classID, subclassID, bindType, expansionID,
        setID, craftingReagent, description = FT.Call(method, link or itemID)
    name = FT.Value(name, "string")
    if not name then
        return nil
    end
    return {
        item_id           = itemID,
        requested_link    = link,
        link              = FT.Value(resolvedLink, "string"),
        name              = name,
        quality           = number(quality, 0, 100),
        item_level        = number(itemLevel, 0, 100000),
        minimum_level     = number(minimumLevel, 0, 100000),
        item_type         = FT.Value(itemType, "string"),
        subtype           = FT.Value(subtype, "string"),
        stack_size        = number(stackSize, 0, 1000000000),
        equip_location    = FT.Value(equipLocation, "string"),
        icon_id           = number(texture, 0, 2147483647),
        icon_path         = FT.Value(texture, "string"),
        sell_price_copper = number(sellPrice, 0, 1000000000000),
        class_id          = number(classID, 0, 1000),
        subclass_id       = number(subclassID, 0, 1000),
        bind_type         = number(bindType, 0, 100),
        expansion_id      = number(expansionID, 0, 100),
        set_id            = number(setID, 0, 2147483647),
        crafting_reagent  = FT.Value(craftingReagent, "boolean"),
        description       = FT.Value(description, "string"),
    }
end

local function removePending(key)
    local pending = pendingItems[key]
    if pending then
        pendingItems[key] = nil
        pendingCount     = pendingCount - 1
    end
    return pending
end

local function unresolved(pending, reason, event, status)
    FT.Diagnostic("item_metadata_" .. (status or reason), tostring(pending.item_id))
    FT.Emit("item.metadata_unresolved", {
        item_id = pending.item_id,
        link    = pending.link,
        status  = status or reason,
    }, event, "api_snapshot", pending.references, { metadata = reason })
end

local function resolveItem(key, event)
    local pending = pendingItems[key]
    if not pending then
        return false
    end
    local metadata = readItem(pending.item_id, pending.link)
    if not metadata then
        return false
    end
    removePending(key)
    FT.Emit("item.metadata", metadata, {
        event             = event,
        method            = "item_metadata_read",
        trigger_elapsed_s = pending.requested_at,
        sampled_elapsed_s = FT.Now(),
    }, "api_snapshot", pending.references)
    return true
end

local function scheduleItemTimeouts()
    local requestGeneration = generation
    FT.Schedule("loot.item_timeouts", 1, function()
        if requestGeneration ~= generation then
            return
        end
        local keys = {}
        for key, pending in pairs(pendingItems) do
            if FT.Now() - pending.requested_at >= ITEM_TIMEOUT then
                keys[#keys + 1] = key
            end
        end
        for _, key in ipairs(keys) do
            if not resolveItem(key) then
                local pending = removePending(key)
                if pending then
                    unresolved(pending, "not_ready", nil, "timeout")
                end
            end
        end
        if pendingCount > 0 then
            scheduleItemTimeouts()
        end
    end)
end

function FT.RequestItem(itemID, link, observationID)
    itemID        = number(itemID, 1, 2147483647)
    link          = FT.Value(link, "string")
    observationID = FT.Value(observationID, "string")
    if not itemID then
        itemID = FT.ItemID(link)
    end
    if not itemID or not observationID then
        return
    end
    if not itemAPI("GetItemInfo") then
        unresolved({ item_id = itemID, link = link, references = { observationID } }, "unsupported")
        return
    end
    if link and FT.ItemID(link) ~= itemID then
        link = nil
    end
    local key     = itemKey(itemID, link)
    local pending = pendingItems[key]
    if pending then
        for _, reference in ipairs(pending.references) do
            if reference == observationID then
                return
            end
        end
        if #pending.references >= MAX_REFERENCES then
            unresolved({ item_id = itemID, link = link, references = { observationID } }, "capacity_limit")
            return
        end
        pending.references[#pending.references + 1] = observationID
        return
    end
    if pendingCount >= MAX_PENDING then
        unresolved({ item_id = itemID, link = link, references = { observationID } }, "capacity_limit")
        return
    end
    pending = {
        item_id      = itemID,
        link         = link,
        requested_at = FT.Now(),
        references   = { observationID },
        generation   = generation,
    }
    pendingItems[key] = pending
    pendingCount     = pendingCount + 1
    if resolveItem(key) then
        return
    end
    local requestMethod = itemAPI("RequestLoadItemDataByID")
    if requestMethod then
        FT.Call(requestMethod, itemID)
    end
    scheduleItemTimeouts()
end

local function itemLoaded(event, itemID, success)
    itemID  = number(itemID, 1, 2147483647)
    success = FT.Value(success, "boolean")
    if not itemID then
        return
    end
    local keys = {}
    for key, pending in pairs(pendingItems) do
        if pending.item_id == itemID then
            keys[#keys + 1] = key
        end
    end
    for _, key in ipairs(keys) do
        if not resolveItem(key, event) and success == false then
            local pending = removePending(key)
            if pending then
                unresolved(pending, "not_ready", event, "load_failed")
            end
        end
    end
end

local function packValues(...)
    return { n = select("#", ...), ... }
end

local function readSources(slot, quantity)
    local sources = {}
    if FT.Profile.loot_source_pairs ~= true then
        return sources, "unknown", nil, "unsupported"
    end
    local raw     = packValues(FT.Call("GetLootSourceInfo", slot))
    local total   = 0
    local partial = raw.n % 2 ~= 0
    if raw.n > 128 then
        return sources, "unknown", nil, "capacity_limit"
    end
    for index = 1, raw.n, 2 do
        local guid  = FT.Value(raw[index], "string")
        local count = number(raw[index + 1], 0, 1000000000)
        if guid and count and (guid:match("^Creature%-%d+%-%d+%-%d+%-%d+%-%d+%-%x+$")
            or guid:match("^GameObject%-%d+%-%d+%-%d+%-%d+%-%d+%-%x+$")
            or guid:match("^Vehicle%-%d+%-%d+%-%d+%-%d+%-%d+%-%x+$")
            or guid:match("^Item%-%d+%-%d+%-%x+$")) then
            sources[#sources + 1] = { source_guid = guid, quantity = count }
            total                = total + count
        else
            partial = true
        end
    end
    if #sources == 0 then
        return sources, "unknown", nil, "unknown_source"
    end
    local matches = nil
    if quantity ~= nil and not partial then
        matches = total == quantity
    end
    return sources, partial and "partial" or "mapped", matches, partial and "invalid_result" or nil
end

local function readLootSlot(slot)
    local slotType = number(FT.Call("GetLootSlotType", slot), 0, 100)
    local link     = FT.Value(FT.Call("GetLootSlotLink", slot), "string")
    local texture, name, quantity, currencyID, quality, locked, questItem, questID, active, coin
    if FT.Profile.loot_info == "modern" then
        texture, name, quantity, currencyID, quality, locked, questItem, questID, active, coin = FT.Call("GetLootSlotInfo", slot)
    elseif FT.Profile.loot_info == "classic" then
        texture, name, quantity, quality, locked = FT.Call("GetLootSlotInfo", slot)
    end
    name     = FT.Value(name, "string")
    quantity = number(quantity, 0, 1000000000)
    coin     = FT.Value(coin, "boolean")
    if slotType == nil and link == nil and name == nil and quantity == nil then
        return nil
    end
    local itemID = FT.ItemID(link)
    local kind   = "unknown"
    if coin == true or slotType == 2 then
        kind = "money"
    elseif itemID then
        kind = "item"
    elseif slotType == 3 or number(currencyID, 1, 2147483647) then
        kind = "currency"
    elseif slotType == 1 then
        kind = "item"
    end
    local sources, sourceState, sourceMatches, sourceReason = readSources(slot, quantity)
    local missing = {}
    if sourceReason then
        missing.sources = "unknown_source"
        missing.source_mapping = sourceReason
    end
    if kind == "item" and not itemID then
        missing.item_id = "not_ready"
    end
    if kind == "currency" and not number(currencyID, 1, 2147483647) then
        missing.currency_id = "not_ready"
    end
    if not link and kind ~= "money" then
        missing.link = "not_ready"
    end
    if quantity == nil then
        missing.quantity = "not_ready"
    end
    local complete = quantity ~= nil and kind ~= "unknown"
        and (kind ~= "item" or itemID ~= nil) and (kind == "money" or link ~= nil)
    return {
        slot                    = slot,
        slot_type               = slotType,
        slot_kind               = kind,
        item_id                 = kind == "item" and itemID or nil,
        currency_id             = kind == "currency" and number(currencyID, 1, 2147483647) or nil,
        link                    = link,
        name                    = name,
        quantity                = quantity,
        quality                 = number(quality, 0, 100),
        locked                  = FT.Value(locked, "boolean"),
        is_quest_item           = FT.Value(questItem, "boolean"),
        quest_id                = number(questID, 1, 2147483647),
        quest_active            = FT.Value(active, "boolean"),
        is_coin                 = coin,
        icon_id                 = number(texture, 0, 2147483647),
        icon_path               = FT.Value(texture, "string"),
        sources                 = sources,
        source_status           = sourceState,
        source_quantity_matches = sourceMatches,
        completeness            = complete and "complete" or "partial",
    }, missing
end

local function snapshotSlot(slot, event)
    local context = activeLoot
    if not context then
        return false
    end
    local data, missing = readLootSlot(slot)
    if not data then
        return false
    end
    local previous = activeLoot.slots[slot]
    if previous and same(previous.data, data) and same(previous.missing, missing) and not previous.cleared then
        return true, data.completeness == "complete"
    end
    local revision = previous and previous.revision + 1 or 1
    local record   = {}
    for key, value in pairs(data) do
        record[key] = value
    end
    record.loot_session_id = activeLoot.id
    record.revision        = revision
    local observationID = FT.Emit("loot.visible", record, event, "api_snapshot", nil, missing)
    if not observationID or activeLoot ~= context then
        return false
    end
    activeLoot.slots[slot] = { data = data, missing = missing, revision = revision, observation_id = observationID }
    if data.item_id then
        FT.RequestItem(data.item_id, data.link, observationID)
    end
    return true, data.completeness == "complete"
end

local function lootOpened(event, automatic, fromItem)
    if not activeLoot then
        activeLoot = { id = FT.NewContext("loot"), slots = {} }
        local openedID = FT.Emit("loot.opened", {
            loot_session_id     = activeLoot.id,
            automatic           = FT.Value(automatic, "boolean"),
            from_item           = FT.Value(fromItem, "boolean"),
            target_candidate    = FT.Unit("target"),
            mouseover_candidate = FT.Unit("mouseover"),
            source_attribution  = "unresolved",
        }, event, "direct_event")
        if not openedID or not activeLoot then
            return
        end
    end
    local context  = activeLoot
    local count    = number(FT.Call("GetNumLootItems"), 0, 100000)
    local captured = 0
    local complete = true
    local status   = "unavailable"
    if count then
        for slot = 1, math.min(count, MAX_LOOT_SLOTS) do
            local available, full = snapshotSlot(slot, event)
            if activeLoot ~= context then
                return
            end
            if available then
                captured = captured + 1
            end
            if not full then
                complete = false
            end
        end
        status = captured == count and complete and "complete" or "partial"
    end
    local state = { loot_session_id = activeLoot.id, slot_count = count, captured_slots = captured, completeness = status }
    if not same(state, activeLoot.scan) then
        local missing = {}
        if status ~= "complete" then
            missing.slots = count and count > MAX_LOOT_SLOTS and "capacity_limit" or "not_ready"
        end
        FT.Emit("loot.snapshot", state, event, "api_snapshot", nil, missing)
        if activeLoot == context then
            activeLoot.scan = state
        end
    end
end

local function lootChanged(event, slot)
    slot = number(slot, 1, MAX_LOOT_SLOTS)
    if activeLoot and slot then
        if not snapshotSlot(slot, event) then
            FT.Emit("loot.slot_unavailable", { loot_session_id = activeLoot.id, slot = slot }, event,
                "api_snapshot", nil, { slot = "not_ready" })
        end
    end
end

local function lootCleared(event, slot)
    slot = number(slot, 1, MAX_LOOT_SLOTS)
    if not activeLoot or not slot then
        return
    end
    local previous = activeLoot.slots[slot]
    if previous and previous.cleared then
        return
    end
    FT.Emit("loot.slot_cleared", {
        loot_session_id = activeLoot.id,
        slot            = slot,
        revision        = previous and previous.revision or nil,
    }, event, "direct_event", previous and previous.observation_id and { previous.observation_id } or nil,
        { receipt = "not_observed" })
    if previous then
        previous.cleared = true
    end
end

local function closeLoot(event, reason)
    if activeLoot then
        FT.Emit("loot.closed", { loot_session_id = activeLoot.id, reason = reason or "closed" }, event, "direct_event")
        activeLoot = nil
    end
end

local function containerMethod(method)
    if FT.Profile.container_info == "modern" then
        return "C_Container." .. method
    end
    if FT.Profile.container_info == "classic" then
        return method
    end
end

local function readBagSlot(bag, slot)
    local method = containerMethod("GetContainerItemInfo")
    if not method then
        return nil, "unsupported"
    end
    local itemID, link, quantity, icon
    if FT.Profile.container_info == "modern" then
        local ok, result = FT.TryCall(method, bag, slot)
        if not ok then
            return nil, "invalid_result"
        end
        if result == nil then
            return nil
        end
        itemID   = number(FT.Field(result, "itemID", "number"), 1, 2147483647)
        link     = FT.Field(result, "hyperlink", "string")
        quantity = number(FT.Field(result, "stackCount", "number"), 1, 1000000000)
    else
        local locked, quality, readable, lootable, filtered, noValue
        icon, quantity, locked, quality, readable, lootable, link, filtered, noValue, itemID = FT.Call(method, bag, slot)
        if FT.Value(icon, "number") == nil and FT.Value(icon, "string") == nil then
            return nil
        end
        itemID   = number(itemID, 1, 2147483647)
        link     = FT.Value(link, "string")
        quantity = number(quantity, 1, 1000000000)
    end
    itemID = itemID or FT.ItemID(link)
    if not itemID or not quantity then
        return nil, "not_ready"
    end
    return { item_id = itemID, link = link, quantity = quantity }
end

local function inventorySnapshot(event, triggerTime)
    if not insideWorld then
        return
    end
    local scanGeneration = generation
    local baseline       = bagBaseline
    local entries        = {}
    local ordered        = {}
    local slotCount      = 0
    local completeness   = "complete"
    local missing        = {}
    local method         = containerMethod("GetContainerNumSlots")
    if not method then
        FT.Emit("inventory.snapshot", { completeness = "unavailable", scope = "carried_bags_0_to_4" }, event,
            "api_snapshot", nil, { bags = "unsupported" })
        bagBaseline = nil
        return
    end
    for bag = 0, 4 do
        local count = number(FT.Call(method, bag), 0, MAX_BAG_SLOTS)
        if not count or slotCount + count > MAX_BAG_SLOTS then
            completeness                 = "partial"
            missing["bag_" .. tostring(bag)] = count and "capacity_limit" or "not_ready"
        else
            slotCount = slotCount + count
            for slot = 1, count do
                local item, reason = readBagSlot(bag, slot)
                if reason then
                    completeness = "partial"
                    missing["bag_" .. tostring(bag)] = reason
                elseif item then
                    local entry = entries[item.item_id]
                    if not entry then
                        entry                 = { item_id = item.item_id, quantity = 0, links = {} }
                        entries[item.item_id] = entry
                        ordered[#ordered + 1] = entry
                    end
                    entry.quantity = entry.quantity + item.quantity
                    if item.link then
                        entry.links[item.link] = true
                    end
                end
            end
        end
    end
    table.sort(ordered, function(first, second)
        return first.item_id < second.item_id
    end)
    for _, entry in ipairs(ordered) do
        local links = {}
        for link in pairs(entry.links) do
            links[#links + 1] = link
        end
        table.sort(links)
        entry.links = links
    end
    if completeness == "complete" and baseline and same(ordered, baseline.items) then
        return
    end
    local capture = { event = event, trigger_elapsed_s = triggerTime, sampled_elapsed_s = FT.Now() }
    local snapshotID = FT.Emit("inventory.snapshot", {
        scope        = "carried_bags_0_to_4",
        completeness = completeness,
        slots        = slotCount,
        items        = ordered,
    }, capture, "api_snapshot", nil, missing)
    if completeness ~= "complete" or not snapshotID or generation ~= scanGeneration then
        bagBaseline = nil
        return
    end
    local before = baseline and baseline.entries or nil
    if before then
        local ids = {}
        for itemID in pairs(before) do
            ids[itemID] = true
        end
        for itemID in pairs(entries) do
            ids[itemID] = true
        end
        local sortedIDs = {}
        for itemID in pairs(ids) do
            sortedIDs[#sortedIDs + 1] = itemID
        end
        table.sort(sortedIDs)
        for _, itemID in ipairs(sortedIDs) do
            local oldQuantity = before[itemID] and before[itemID].quantity or 0
            local newQuantity = entries[itemID] and entries[itemID].quantity or 0
            if oldQuantity ~= newQuantity then
                FT.Emit("inventory.delta", {
                    item_id         = itemID,
                    before_quantity = oldQuantity,
                    after_quantity  = newQuantity,
                    delta           = newQuantity - oldQuantity,
                    scope           = "carried_bags_0_to_4",
                    source_status   = "unknown",
                }, capture, "snapshot_diff", { baseline.observation_id, snapshotID }, { source = "unknown_source" })
                if generation ~= scanGeneration then
                    return
                end
            end
        end
    end
    for _, entry in ipairs(ordered) do
        local old = before and before[entry.item_id] or nil
        if not old or not same(old.links, entry.links) then
            if #entry.links == 0 then
                FT.RequestItem(entry.item_id, nil, snapshotID)
                if generation ~= scanGeneration then
                    return
                end
            else
                for _, link in ipairs(entry.links) do
                    FT.RequestItem(entry.item_id, link, snapshotID)
                    if generation ~= scanGeneration then
                        return
                    end
                end
            end
        end
    end
    bagBaseline = { entries = entries, items = ordered, observation_id = snapshotID }
end

local function scheduleInventory(event)
    local triggerTime        = FT.Now()
    local requestGeneration  = generation
    FT.Schedule("loot.inventory", 0.2, function()
        if generation == requestGeneration then
            inventorySnapshot(event, triggerTime)
        end
    end)
end

local function inventoryBaseline(event)
    bagBaseline = nil
    insideWorld = true
    scheduleInventory(event)
end

local function escapePattern(character)
    return character:gsub("([%(%)%.%%%+%-%*%?%[%]%^%$])", "%%%1")
end

local function receiptPattern(template)
    if not template or #template > 512 then
        return nil
    end
    local pieces   = { "^" }
    local captures = {}
    local cursor   = 1
    local argument = 0
    while cursor <= #template do
        local rest = template:sub(cursor)
        if rest:sub(1, 2) == "%%" then
            pieces[#pieces + 1] = "%%"
            cursor              = cursor + 2
        elseif rest:sub(1, 1) == "%" then
            local index, format = rest:match("^%%(%d+)%$([sd])")
            local width         = nil
            if index then
                width = #index + 3
                index = tonumber(index)
            else
                format = rest:match("^%%([sd])")
                width  = 2
                argument = argument + 1
                index    = argument
            end
            if not format or #captures >= 2 or (index ~= 1 and index ~= 2) then
                return nil
            end
            captures[#captures + 1] = { index = index, format = format }
            pieces[#pieces + 1]     = format == "d" and "(%d+)" or "(.+)"
            cursor                  = cursor + width
        else
            pieces[#pieces + 1] = escapePattern(rest:sub(1, 1))
            cursor              = cursor + 1
        end
    end
    pieces[#pieces + 1] = "$"
    return table.concat(pieces), captures
end

local receiptTemplates = {
    "LOOT_ITEM_SELF_MULTIPLE", "LOOT_ITEM_SELF",
    "LOOT_ITEM_CREATED_SELF_MULTIPLE", "LOOT_ITEM_CREATED_SELF",
    "LOOT_ITEM_PUSHED_SELF_MULTIPLE", "LOOT_ITEM_PUSHED_SELF",
}

local function localReceipt(event, message)
    message = FT.Value(message, "string")
    if not message or #message > 4096 then
        return
    end
    for _, templateName in ipairs(receiptTemplates) do
        local pattern, captures = receiptPattern(FT.Field(_G, templateName, "string"))
        if pattern then
            local results = { message:match(pattern) }
            if #results == #captures and #results > 0 then
                local link     = nil
                local quantity = 1
                local valid    = true
                for index, capture in ipairs(captures) do
                    if capture.index == 1 and capture.format == "s" then
                        link = results[index]
                    elseif capture.index == 2 and capture.format == "d" then
                        quantity = number(tonumber(results[index]), 1, 1000000000)
                    else
                        valid = false
                    end
                end
                local itemID = FT.ItemID(link)
                if valid and itemID and quantity then
                    local observationID = FT.Emit("item.received", {
                        item_id         = itemID,
                        link            = link,
                        quantity        = quantity,
                        recipient       = "local_player",
                        receipt_template = templateName,
                        source_status   = "unknown",
                    }, event, "localized_self_receipt", nil, { source = "unknown_source" })
                    FT.RequestItem(itemID, link, observationID)
                    return
                end
            end
        end
    end
end

FT.On("LOOT_READY", lootOpened)
FT.On("LOOT_OPENED", lootOpened)
FT.On("LOOT_SLOT_CHANGED", lootChanged)
FT.On("LOOT_SLOT_CLEARED", lootCleared)
FT.On("LOOT_CLOSED", function(event)
    closeLoot(event)
end)
FT.On("ITEM_DATA_LOAD_RESULT", itemLoaded)
FT.On("GET_ITEM_INFO_RECEIVED", itemLoaded)
FT.On("CHAT_MSG_LOOT", localReceipt)
FT.On("BAG_UPDATE_DELAYED", scheduleInventory)
FT.On("PLAYER_LOGIN", scheduleInventory)
FT.On("PLAYER_ENTERING_WORLD", inventoryBaseline)
FT.On("FT_BASELINE", inventoryBaseline)
FT.On("PLAYER_LEAVING_WORLD", function(event)
    closeLoot(event, "transition")
    bagBaseline = nil
    insideWorld = false
end)
FT.OnReset(function()
    generation   = generation + 1
    activeLoot   = nil
    bagBaseline  = nil
    pendingItems = {}
    pendingCount = 0
end)
