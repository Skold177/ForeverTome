local _, FT = ...

local LIMIT = { recipes = 2048, batch = 8, cache = 4096, slots = 32, reagents = 16 }

local cache      = {}
local cacheCount = 0
local generation = 0
local pending
local scan
local lastProfession
local lastScan
local lastStatus = "not_observed"
local lastCount  = 0

local function contentID(value)
    value = FT.Value(value, "number")
    if value and value > 0 and value % 1 == 0 and value <= 2147483647 then
        return value
    end
end

local function enabled()
    local state = FT.Status()
    return FT.Profile.supported and FT.Profile.professions and FT.InWorld
        and state.initialized and not state.paused and not state.blocked
end

local function fields(source, schema)
    local result = {}
    for key, kind in pairs(schema) do
        result[key] = FT.Field(source, key, kind)
    end
    return result
end

local function professionInfo()
    local source = FT.Call("C_TradeSkillUI.GetBaseProfessionInfo")
    local data   = fields(source, {
        professionID = "number", professionName = "string", expansionName = "string",
        skillLevel = "number", maxSkillLevel = "number", parentProfessionID = "number",
        parentProfessionName = "string", sourceCounter = "number", skillModifier = "number",
        isPrimaryProfession = "boolean",
    })
    data.professionID = contentID(data.professionID)
    data.scope        = "currently_viewed_profession"
    for field, path in pairs({ is_linked = "C_TradeSkillUI.IsTradeSkillLinked", is_guild = "C_TradeSkillUI.IsTradeSkillGuild" }) do
        if FT.Resolve(path) then
            data[field] = FT.Value(FT.Call(path), "boolean")
        end
    end
    return data
end

local function reagents(source, missing, path)
    local result = {}
    local count  = FT.Length(source)
    if not count then
        missing[path] = "not_ready_or_restricted"
    elseif count > LIMIT.reagents then
        missing[path] = "capacity_limit"
    end
    for index = 1, math.min(count or 0, LIMIT.reagents) do
        local row = fields(FT.Field(source, index, "table"), { itemID = "number", currencyID = "number" })
        row.itemID     = contentID(row.itemID)
        row.currencyID = contentID(row.currencyID)
        if not row.itemID and not row.currencyID then
            missing[path .. "." .. index] = "not_ready_or_restricted"
        end
        result[#result + 1] = row
    end
    return result
end

local function recipeMetadata(recipeID, related, force, recipeLevel)
    local source  = FT.Call("C_TradeSkillUI.GetRecipeInfo", recipeID, recipeLevel)
    local missing = {}
    if FT.Field(source, "recipeID", "number") and FT.Field(source, "recipeID", "number") ~= recipeID then
        source                = nil
        missing["data.info"] = "identity_mismatch"
    end
    local data = fields(source, {
        name = "string", recipeID = "number", learned = "boolean", categoryID = "number",
        skillLineAbilityID = "number", hyperlink = "string", maxTrivialLevel = "number",
        relativeDifficulty = "number", itemLevel = "number", numSkillUps = "number", canSkillUp = "boolean",
        firstCraft = "boolean", sourceType = "number", disabled = "boolean", disabledReason = "string",
        craftable = "boolean", supportsQualities = "boolean", previousRecipeID = "number", nextRecipeID = "number",
        unlockedRecipeLevel = "number", maxQuality = "number", isRecraft = "boolean",
        isDummyRecipe = "boolean", isGatheringRecipe = "boolean", isEnchantingRecipe = "boolean", isSalvageRecipe = "boolean",
    })
    for _, key in ipairs({ "name", "learned", "categoryID", "skillLineAbilityID" }) do
        if data[key] == nil then
            missing["data." .. key] = "not_ready"
        end
    end
    data.recipe_id      = recipeID
    data.recipe_level   = recipeLevel
    data.values_context = "currently_accessible_recipe_api"
    if FT.Resolve("C_TradeSkillUI.GetProfessionInfoByRecipeID") then
        local profession = FT.Call("C_TradeSkillUI.GetProfessionInfoByRecipeID", recipeID)
        data.profession_id   = contentID(FT.Field(profession, "professionID", "number"))
        data.profession_name = FT.Field(profession, "professionName", "string")
    end
    if not data.profession_id then
        missing["data.profession_id"] = "not_ready_or_unsupported"
    end
    local qualityIDs   = FT.Field(source, "qualityItemIDs", "table")
    local qualityCount = FT.Length(qualityIDs)
    if qualityCount then
        data.quality_item_ids = {}
        if qualityCount > LIMIT.reagents then
            missing["data.quality_item_ids"] = "capacity_limit"
        end
        for index = 1, math.min(qualityCount, LIMIT.reagents) do
            local identity = contentID(FT.Field(qualityIDs, index, "number"))
            if identity then
                data.quality_item_ids[#data.quality_item_ids + 1] = identity
            else
                missing["data.quality_item_ids." .. index] = "invalid_or_unreadable"
            end
        end
    elseif data.supportsQualities then
        missing["data.quality_item_ids"] = "not_ready_or_restricted"
    end
    local schematic = FT.Call("C_TradeSkillUI.GetRecipeSchematic", recipeID, false, recipeLevel)
    if FT.Field(schematic, "recipeID", "number") and FT.Field(schematic, "recipeID", "number") ~= recipeID then
        schematic                  = nil
        missing["data.schematic"] = "identity_mismatch"
    end
    data.output_item_id  = contentID(FT.Field(schematic, "outputItemID", "number"))
    data.quantity_min    = FT.Field(schematic, "quantityMin", "number")
    data.quantity_max    = FT.Field(schematic, "quantityMax", "number")
    data.recipe_type     = FT.Field(schematic, "recipeType", "number")
    data.product_quality = FT.Field(schematic, "productQuality", "number")
    data.icon_id         = contentID(FT.Field(schematic, "icon", "number"))
    data.output_status   = data.output_item_id and "available" or "not_observed"
    if not data.output_item_id then
        missing["data.output_item_id"] = "not_observed"
    end
    for _, key in ipairs({ "quantity_min", "quantity_max" }) do
        if data[key] == nil then
            missing["data." .. key] = "not_ready"
        elseif data[key] < 0 or data[key] % 1 ~= 0 then
            data[key]              = nil
            missing["data." .. key] = "invalid_result"
        end
    end
    if data.quantity_min and data.quantity_max and data.quantity_min > data.quantity_max then
        missing["data.quantity_max"] = "inconsistent_range"
    end
    data.reagent_slots = {}
    local slots     = FT.Field(schematic, "reagentSlotSchematics", "table")
    local slotCount = FT.Length(slots)
    if not slotCount then
        missing["data.reagent_slots"] = "not_ready"
    elseif slotCount > LIMIT.slots then
        missing["data.reagent_slots"] = "capacity_limit"
    end
    for index = 1, math.min(slotCount or 0, LIMIT.slots) do
        local slot = FT.Field(slots, index, "table")
        local row  = fields(slot, {
            quantityRequired = "number", required = "boolean", reagentType = "number", dataSlotType = "number",
            dataSlotIndex = "number", slotIndex = "number", orderSource = "number", hiddenInCraftingForm = "boolean",
        })
        local path = "data.reagent_slots." .. index
        row.index    = index
        row.reagents = reagents(FT.Field(slot, "reagents", "table"), missing, path .. ".reagents")
        if missing[path .. ".reagents"] == "not_ready_or_restricted" then
            missing[path .. ".reagents"] = "not_ready"
        end
        if row.quantityRequired == nil or row.required == nil or row.reagentType == nil then
            missing[path] = "not_ready"
        end
        local slotInfo = FT.Field(slot, "slotInfo", "table")
        if slotInfo then
            row.slot_info = fields(slotInfo, { mcrSlotID = "number", requiredSkillRank = "number", slotText = "string" })
        end
        local variables     = FT.Field(slot, "variableQuantities", "table")
        local variableCount = FT.Length(variables)
        if variableCount then
            row.variable_quantities = {}
            if variableCount > LIMIT.reagents then
                missing[path .. ".variable_quantities"] = "capacity_limit"
            end
            for variableIndex = 1, math.min(variableCount, LIMIT.reagents) do
                local variable = FT.Field(variables, variableIndex, "table")
                local reagent  = fields(FT.Field(variable, "reagent", "table"), { itemID = "number", currencyID = "number" })
                local quantity = FT.Field(variable, "quantity", "number")
                reagent.itemID     = contentID(reagent.itemID)
                reagent.currencyID = contentID(reagent.currencyID)
                if not quantity or quantity < 0 or not reagent.itemID and not reagent.currencyID then
                    missing[path .. ".variable_quantities." .. variableIndex] = "invalid_or_unreadable"
                end
                row.variable_quantities[#row.variable_quantities + 1] = { quantity = quantity, reagent = reagent }
            end
        else
            missing[path .. ".variable_quantities"] = "not_ready_or_restricted"
        end
        data.reagent_slots[#data.reagent_slots + 1] = row
    end
    if FT.Resolve("C_TradeSkillUI.GetRecipeRequirements") then
        local requirements = FT.Call("C_TradeSkillUI.GetRecipeRequirements", recipeID)
        local count        = FT.Length(requirements)
        data.requirements = {}
        if not count or count > LIMIT.slots then
            missing["data.requirements"] = count and "capacity_limit" or "not_ready_or_restricted"
        end
        for index = 1, math.min(count or 0, LIMIT.slots) do
            local requirement = fields(FT.Field(requirements, index, "table"), { name = "string", met = "boolean", type = "number" })
            if requirement.name == nil or requirement.met == nil or requirement.type == nil then
                missing["data.requirements." .. index] = "not_ready_or_restricted"
            end
            data.requirements[#data.requirements + 1] = requirement
        end
    else
        missing["data.requirements"] = "unsupported"
    end
    data.completeness = next(missing) and "partial" or "complete"
    local comparison = FT.Copy({ data = data, missing = missing })
    local previous   = cache[recipeID]
    if not comparison then
        FT.Diagnostic("invalid_record", "recipe_metadata")
        return nil, false
    end
    if not force and previous and FT.Equal(previous.comparison, comparison) then
        return previous.id, data.completeness == "complete"
    end
    local id = FT.Emit("recipe.metadata", data, { api = "C_TradeSkillUI.GetRecipeSchematic", method = "metadata_read" },
        "api_snapshot", related and { related } or {}, missing)
    if id then
        if not previous then
            cacheCount = cacheCount + 1
        end
        if cacheCount > LIMIT.cache then
            cache      = {}
            cacheCount = 1
        end
        cache[recipeID] = { comparison = comparison, id = id }
        if data.output_item_id then
            FT.RequestItem(data.output_item_id, nil, id)
        end
    end
    return id, id ~= nil and data.completeness == "complete"
end

local function finishScan(current, reason)
    if scan ~= current then
        return
    end
    if reason then
        current.missing["data.scan"] = reason
    end
    local data = {
        profession_id = current.profession.professionID, source_counter = current.profession.sourceCounter,
        scope = current.scope, enumeration_method = current.method, enumeration_contract = current.contract,
        recipe_ids = current.ids, returned_count = current.returned_count, enumerated_count = #current.ids,
        processed_count = current.index - 1, complete_recipe_count = current.complete_count,
        partial_recipe_count = current.partial_count, enumeration_complete = current.enumeration_complete,
        profession_coverage = current.contract == "unverified_runtime_probe" and "unverified" or "filtered",
        completeness = next(current.missing) and "partial" or "complete",
    }
    local comparison = FT.Copy({ data = data, missing = current.missing })
    if current.force or not FT.Equal(lastScan, comparison) then
        FT.Emit("recipe.scan", data, current.event, "api_snapshot", current.references, current.missing)
        if scan ~= current then
            return
        end
        lastScan = comparison
    end
    lastStatus = data.completeness
    lastCount  = data.processed_count
    scan = nil
end

local function scanWork()
    local current = scan
    if not current or current.generation ~= generation or not enabled() then
        return
    end
    local profession = professionInfo()
    if profession.professionID ~= current.profession.professionID or profession.sourceCounter ~= current.profession.sourceCounter then
        finishScan(current, "data_source_changed")
        return
    end
    for _ = 1, LIMIT.batch do
        local recipeID = current.ids[current.index]
        if not recipeID then
            finishScan(current)
            return
        end
        local id, complete = recipeMetadata(recipeID)
        if scan ~= current or current.generation ~= generation then
            return
        end
        if id then
            current.references[#current.references + 1] = id
        end
        if complete then
            current.complete_count = current.complete_count + 1
        else
            current.partial_count = current.partial_count + 1
            current.missing["data.recipes"] = "partial_metadata"
        end
        current.index = current.index + 1
    end
    FT.Schedule("professions.work", 0.05, scanWork)
end

local function startScan(event)
    if not enabled() then
        return
    end
    local epoch      = generation
    local profession = professionInfo()
    if not FT.Equal(lastProfession, profession) then
        local missing = profession.professionID and {} or { ["data.professionID"] = "not_ready_or_unsupported" }
        FT.Emit("profession.snapshot", profession, event, "api_snapshot", nil, missing)
        if generation ~= epoch or not enabled() then
            return
        end
        lastProfession = FT.Copy(profession)
    end
    local method   = "C_TradeSkillUI.GetAllRecipeIDs"
    local raw      = FT.Resolve(method) and FT.Call(method) or nil
    local scope    = "currently_viewed_profession_all_exposed_recipes"
    local contract = "unverified_runtime_probe"
    if not FT.Length(raw) then
        method   = "C_TradeSkillUI.GetFilteredRecipeIDs"
        raw      = FT.Resolve(method) and FT.Call(method) or nil
        scope    = "currently_viewed_profession_filtered"
        contract = "installed_client_ui"
    end
    local count   = FT.Length(raw)
    local missing = {}
    local ids     = {}
    local seen    = {}
    if not profession.professionID then
        missing["data.profession_id"] = "not_ready_or_unsupported"
    end
    if not count then
        missing["data.recipe_ids"] = "not_ready_or_unsupported"
    elseif count > LIMIT.recipes then
        missing["data.recipe_ids"] = "capacity_limit"
    end
    for index = 1, math.min(count or 0, LIMIT.recipes) do
        local identity = contentID(FT.Field(raw, index, "number"))
        if not identity then
            missing["data.recipe_ids"] = "invalid_or_unreadable"
        elseif not seen[identity] then
            seen[identity] = true
            ids[#ids + 1] = identity
        end
    end
    table.sort(ids)
    scan = {
        profession = profession, ids = ids, index = 1, references = {}, complete_count = 0, partial_count = 0,
        event = event, method = method, scope = scope, contract = contract, returned_count = count,
        missing = missing, generation = generation, force = event == "FT_CATALOG",
        enumeration_complete = not missing["data.recipe_ids"],
    }
    scanWork()
end

local function scheduleScan(event)
    if not enabled() then
        return
    end
    if scan then
        finishScan(scan, "superseded_scan")
    end
    if not enabled() then
        return
    end
    pending = event
    FT.Schedule("professions.scan", 0.25, function()
        local capture = pending
        pending = nil
        if capture then
            startScan(capture)
        end
    end)
end

FT.OnReset(function()
    generation     = generation + 1
    pending        = nil
    scan           = nil
    cache          = {}
    cacheCount     = 0
    lastProfession = nil
    lastScan       = nil
    lastStatus     = "not_observed"
    lastCount      = 0
end)

function FT.ProfessionStatus()
    return { scanning = scan ~= nil or pending ~= nil, completeness = lastStatus,
        recipe_count = lastCount, cached = cacheCount }
end

for _, event in ipairs({ "TRADE_SKILL_SHOW", "TRADE_SKILL_DATA_SOURCE_CHANGED", "FT_CATALOG" }) do
    FT.On(event, scheduleScan)
end

for _, event in ipairs({ "TRADE_SKILL_CLOSE", "TRADE_SKILL_DATA_SOURCE_CHANGING" }) do
    FT.On(event, function()
        pending = nil
        if scan then
            finishScan(scan, "data_source_closed_or_changing")
        end
    end)
end

FT.On("NEW_RECIPE_LEARNED", function(event, recipeID, recipeLevel, baseRecipeID)
    recipeID = contentID(recipeID)
    if not recipeID or not enabled() then
        return
    end
    recipeLevel = contentID(recipeLevel)
    local related = FT.Emit("recipe.learned", {
        recipe_id = recipeID, recipe_level = recipeLevel, base_recipe_id = contentID(baseRecipeID),
    }, event, "direct_event")
    recipeMetadata(recipeID, related, true, recipeLevel)
end)

FT.On("TRADE_SKILL_ITEM_CRAFTED_RESULT", function(event, source)
    if not enabled() then
        return
    end
    local data = fields(source, {
        itemID = "number", hyperlink = "string", quantity = "number", craftingQuality = "number",
        isCrit = "boolean", critBonusSkill = "number", recraftable = "boolean", bonusCraft = "boolean",
        multicraft = "number", firstCraftReward = "boolean", isEnchant = "boolean", operationID = "number",
    })
    data.itemID = contentID(data.itemID)
    if data.itemID then
        local id = FT.Emit("craft.result", data, event, "direct_event", nil, { ["data.recipe_id"] = "not_observed" })
        FT.RequestItem(data.itemID, data.hyperlink, id)
    end
end)
