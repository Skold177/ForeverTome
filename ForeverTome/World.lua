local _, FT = ...

local sightings   = {}
local merchant
local offers      = {}
local lastPlayer
local lastRoute
local lastRouteAt = 0

local function selectFields(source, fields)
    local result = {}
    for name, kind in pairs(fields) do
        result[name] = FT.Field(source, name, kind)
    end
    return result
end

local function playerSnapshot(event)
    local _, class, classID = FT.Call("UnitClass", "player")
    local _, race, raceID   = FT.Call("UnitRace", "player")
    local data = {
        level = FT.Value(FT.Call("UnitLevel", "player"), "number"),
        class = FT.Value(class, "string"), class_id = FT.Value(classID, "number"),
        race = FT.Value(race, "string"), race_id = FT.Value(raceID, "number"),
        faction = FT.Value(FT.Call("UnitFactionGroup", "player"), "string"),
        xp = FT.Value(FT.Call("UnitXP", "player"), "number"),
        xp_max = FT.Value(FT.Call("UnitXPMax", "player"), "number"),
        rested_xp = FT.Value(FT.Call("GetXPExhaustion"), "number"),
        money_copper = FT.Value(FT.Call("GetMoney"), "number"),
        group_size = FT.Value(FT.Call("GetNumGroupMembers"), "number"),
        in_raid = FT.Value(FT.Call("IsInRaid"), "boolean"),
    }
    if not FT.Equal(data, lastPlayer) then
        FT.Emit("player.snapshot", data, event)
        lastPlayer = data
    end
end

local function sight(event, token)
    if not FT.InWorld then
        return
    end
    local data = FT.Unit(token)
    if not data then
        sightings[token] = nil
        return
    end
    local prior   = sightings[token]
    local current = FT.Now()
    if prior and prior.guid == data.guid and prior.dead == data.dead and current - prior.at < 10 then
        return
    end
    local id = FT.Emit("unit.sighting", data, event, "api_snapshot", nil,
        data.creature_id and {} or { ["data.creature_id"] = "not_ready" })
    if id then
        sightings[token] = { guid = data.guid, dead = data.dead, at = current }
    end
end

local function worldSnapshot(event)
    local name, kind, difficulty, difficultyName, maxPlayers, _, _, instance = FT.Call("GetInstanceInfo")
    FT.Emit("world.context", {
        zone = FT.Value(FT.Call("GetZoneText"), "string"),
        subzone = FT.Value(FT.Call("GetSubZoneText"), "string"),
        instance_name = FT.Value(name, "string"), instance_type = FT.Value(kind, "string"),
        difficulty_id = FT.Value(difficulty, "number"), difficulty_name = FT.Value(difficultyName, "string"),
        max_players = FT.Value(maxPlayers, "number"), instance_id = FT.Value(instance, "number"),
    }, event)
end

local function routeSample()
    if FT.InWorld then
        local point = FT.Location()
        local moved = not lastRoute or point.status ~= lastRoute.status or point.ui_map_id ~= lastRoute.ui_map_id
        if not moved and point.status == "available" then
            moved = math.abs(point.x - lastRoute.x) + math.abs(point.y - lastRoute.y) >= 0.002
        end
        if moved or FT.Now() - lastRouteAt >= 60 then
            FT.Emit("location.sample", { sample_interval_s = 5 }, { method = "periodic_sample" })
            lastRoute   = point
            lastRouteAt = FT.Now()
        end
        sight({ method = "periodic_sample", api = "UnitGUID" }, "target")
        FT.Schedule("world.route", 5, routeSample)
    end
end

local function merchantSnapshot(event)
    if not merchant then
        merchant = FT.NewContext("merchant")
        FT.Emit("merchant.opened", { interaction_id = merchant, npc = FT.Unit("npc") }, event)
    end
    local count = FT.Value(FT.Call("GetMerchantNumItems"), "number")
    if not count or count < 0 or count > 250 or count % 1 ~= 0 then
        FT.Diagnostic("unavailable", "merchant_inventory")
        return
    end
    for index = 1, count do
        local source  = FT.Call("C_MerchantFrame.GetItemInfo", index)
        local link    = FT.Value(FT.Call("GetMerchantItemLink", index), "string")
        local missing = {}
        local data    = selectFields(source, {
            name = "string", price = "number", stackCount = "number", numAvailable = "number",
            isPurchasable = "boolean", isUsable = "boolean", hasExtendedCost = "boolean",
            currencyID = "number", spellID = "number", isQuestStartItem = "boolean",
        })
        data.interaction_id = merchant
        data.npc            = FT.Unit("npc")
        data.index          = index
        data.link           = link
        data.item_id        = FT.ItemID(link)
        data.costs          = {}
        for _, key in ipairs({ "name", "price", "stackCount" }) do
            if data[key] == nil then
                missing["data." .. key] = "not_ready"
            end
        end
        if not data.npc then
            missing["data.npc"] = "unknown_source"
        end
        local costCount = FT.Value(FT.Call("GetMerchantItemCostInfo", index), "number")
        if not costCount then
            missing["data.costs"] = "not_ready"
        elseif costCount < 0 or costCount % 1 ~= 0 then
            missing["data.costs"] = "invalid_result"
        else
            if costCount > 16 then
                missing["data.costs"] = "capacity_limit"
            end
            for cost = 1, math.min(costCount, 16) do
                local _, quantity, costLink, currencyName = FT.Call("GetMerchantItemCostItem", index, cost)
                costLink     = FT.Value(costLink, "string")
                quantity     = FT.Value(quantity, "number")
                currencyName = FT.Value(currencyName, "string")
                local row = {
                    index = cost, quantity = FT.Value(quantity, "number"), link = costLink,
                    item_id = FT.ItemID(costLink), currency_name = currencyName,
                }
                if not quantity or not costLink and not currencyName then
                    missing["data.costs." .. cost] = "not_ready"
                end
                table.insert(data.costs, row)
            end
        end
        data.completeness = next(missing) and "partial" or "complete"
        local comparison = FT.Copy({ data = data, missing = missing })
        if not comparison then
            FT.Diagnostic("invalid_record", "merchant_offer")
            return
        end
        if comparison.data.npc and comparison.data.npc.entity_position then
            comparison.data.npc.entity_position.sampled_elapsed_s = nil
        end
        if not FT.Equal(offers[index], comparison) then
            local id = FT.Emit("merchant.offer", data, event, "api_snapshot", nil, missing)
            offers[index] = comparison
            if data.item_id then
                FT.RequestItem(data.item_id, link, id)
            end
        end
    end
end

local function professionSnapshot(event)
    local source = FT.Call("C_TradeSkillUI.GetBaseProfessionInfo")
    local data   = selectFields(source, {
        professionID = "number", professionName = "string", expansionName = "string",
        skillLevel = "number", maxSkillLevel = "number", parentProfessionID = "number",
        sourceCounter = "number", skillModifier = "number", isPrimaryProfession = "boolean",
    })
    if data.professionID then
        data.scope = "currently_viewed_profession"
        FT.Emit("profession.snapshot", data, event)
    end
end

local function recipeLearned(event, recipeID, recipeLevel, baseRecipeID)
    recipeID = FT.Value(recipeID, "number")
    if not recipeID or recipeID <= 0 then
        return
    end
    local related = FT.Emit("recipe.learned", {
        recipe_id = recipeID, recipe_level = FT.Value(recipeLevel, "number"),
        base_recipe_id = FT.Value(baseRecipeID, "number"),
    }, event, "direct_event")
    local source  = FT.Call("C_TradeSkillUI.GetRecipeInfo", recipeID)
    local missing = {}
    local data    = selectFields(source, {
        name = "string", recipeID = "number", learned = "boolean", categoryID = "number",
        skillLineAbilityID = "number", hyperlink = "string", maxTrivialLevel = "number",
    })
    if not data.name then
        missing["data.name"] = "not_ready"
    end
    data.recipe_id = recipeID
    local schematic = FT.Call("C_TradeSkillUI.GetRecipeSchematic", recipeID, false)
    data.output_item_id = FT.Field(schematic, "outputItemID", "number")
    data.quantity_min   = FT.Field(schematic, "quantityMin", "number")
    data.quantity_max   = FT.Field(schematic, "quantityMax", "number")
    data.reagent_slots  = {}
    local slots     = FT.Field(schematic, "reagentSlotSchematics", "table")
    local slotCount = FT.Length(slots)
    if not slotCount then
        missing["data.reagent_slots"] = "not_ready"
    elseif slotCount > 32 then
        missing["data.reagent_slots"] = "capacity_limit"
    end
    for index = 1, math.min(slotCount or 0, 32) do
        local slot = FT.Field(slots, index, "table")
        local row  = selectFields(slot, { quantityRequired = "number", required = "boolean", reagentType = "number" })
        row.index    = index
        row.reagents = {}
        local reagents     = FT.Field(slot, "reagents", "table")
        local reagentCount = FT.Length(reagents)
        local field        = "data.reagent_slots." .. index
        if row.quantityRequired == nil or row.required == nil or row.reagentType == nil then
            missing[field] = "not_ready"
        end
        if not reagentCount then
            missing[field .. ".reagents"] = "not_ready"
        elseif reagentCount > 16 then
            missing[field .. ".reagents"] = "capacity_limit"
        end
        for reagent = 1, math.min(reagentCount or 0, 16) do
            local entry = selectFields(FT.Field(reagents, reagent, "table"), { itemID = "number", currencyID = "number" })
            if entry.itemID == nil and entry.currencyID == nil then
                missing[field .. ".reagents." .. reagent] = "not_ready"
            end
            table.insert(row.reagents, entry)
        end
        table.insert(data.reagent_slots, row)
    end
    data.completeness = next(missing) and "partial" or "complete"
    local id = FT.Emit("recipe.metadata", data, { api = "C_TradeSkillUI.GetRecipeSchematic", method = "metadata_read" },
        "api_snapshot", related and { related } or {}, missing)
    if data.output_item_id then
        FT.RequestItem(data.output_item_id, nil, id)
    end
end

FT.OnReset(function()
    sightings  = {}
    merchant   = nil
    offers     = {}
    lastPlayer = nil
    lastRoute  = nil
end)

local function enterWorld(event)
    if event == "PLAYER_ENTERING_WORLD" then
        FT.InWorld = true
    end
    if not FT.Profile.supported or not FT.InWorld then
        return
    end
    worldSnapshot(event)
    playerSnapshot(event)
    FT.Schedule("world.route", 5, routeSample)
end

FT.On("PLAYER_ENTERING_WORLD", enterWorld)
FT.On("FT_BASELINE", enterWorld)

FT.On("PLAYER_LEAVING_WORLD", function(event)
    FT.Emit("world.transition", { state = "leaving" }, event, "direct_event")
    FT.InWorld = false
    FT.ResetCollectors("world_transition")
end)

for _, event in ipairs({ "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
    FT.On(event, function(name)
        FT.ResetCollectors("zone_change")
        worldSnapshot(name)
        FT.Schedule("world.route", 5, routeSample)
        FT.Schedule("world.baseline", 0.2, function()
            FT.Dispatch("FT_BASELINE")
        end)
    end)
end

FT.On("PLAYER_TARGET_CHANGED", function(event)
    sight(event, "target")
end)

FT.On("UPDATE_MOUSEOVER_UNIT", function(event)
    sight(event, "mouseover")
end)

for _, event in ipairs({ "NAME_PLATE_UNIT_ADDED", "UNIT_FLAGS" }) do
    FT.On(event, function(name, token)
        token = FT.Value(token, "string")
        if token and (token == "target" or token == "mouseover" or string.match(token, "^nameplate%d+$")) then
            sight(name, token)
        end
    end)
end

FT.On("NAME_PLATE_UNIT_REMOVED", function(_, token)
    token = FT.Value(token, "string")
    if token then
        sightings[token] = nil
    end
end)

for _, event in ipairs({ "PLAYER_LEVEL_UP", "PLAYER_XP_UPDATE", "PLAYER_MONEY", "GROUP_ROSTER_UPDATE", "UPDATE_EXHAUSTION" }) do
    FT.On(event, function(name)
        FT.Schedule("world.player", 0.2, function()
            playerSnapshot({ event = name, method = "deferred_snapshot", sampled_elapsed_s = FT.Now() })
        end)
    end)
end

for _, event in ipairs({ "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED", "PLAYER_DEAD", "PLAYER_ALIVE", "PLAYER_UNGHOST" }) do
    FT.On(event, function(name)
        FT.Emit("player.state", { state_event = name }, name, "direct_event")
    end)
end

FT.On("UNIT_SPELLCAST_SUCCEEDED", function(event, token, _, spellID)
    token   = FT.Value(token, "string")
    spellID = FT.Value(spellID, "number")
    if token == "player" and spellID and spellID > 0 then
        local id = FT.Emit("spell.succeeded", { spell_id = spellID, actor = "player", target = FT.Unit("target") }, event, "direct_event")
        FT.RequestSpell(spellID, id)
    end
end)

FT.On("MERCHANT_SHOW", merchantSnapshot)
FT.On("MERCHANT_UPDATE", merchantSnapshot)
FT.On("MERCHANT_CLOSED", function(event)
    if merchant then
        FT.Emit("merchant.closed", { interaction_id = merchant }, event, "direct_event")
    end
    merchant = nil
    offers   = {}
end)

FT.On("TRADE_SKILL_SHOW", professionSnapshot)
FT.On("TRADE_SKILL_DATA_SOURCE_CHANGED", professionSnapshot)
FT.On("NEW_RECIPE_LEARNED", recipeLearned)
FT.On("TRADE_SKILL_ITEM_CRAFTED_RESULT", function(event, source)
    local data = selectFields(source, { itemID = "number", hyperlink = "string", quantity = "number" })
    if data.itemID then
        local id = FT.Emit("craft.result", data, event, "direct_event", nil, { ["data.recipe_id"] = "not_observed" })
        FT.RequestItem(data.itemID, data.hyperlink, id)
    end
end)

FT.On("PLAYER_LOGOUT", function(event)
    FT.Emit("session.ended", { reason = "logout_or_reload" }, event, "direct_event")
end)
