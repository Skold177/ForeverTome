local _, FT = ...

local cache       = {}
local cacheCount  = 0
local scan
local pending
local requested
local lastBuild
local lastID
local lastPartial = false
local status      = { scanning = false }
local types       = { n = "number", s = "string", b = "boolean" }
local schemas     = {
    config = "ID:n type:n usesSharedActionBars:b",
    tree = "ID:n hideSingleRankNumbers:b cannotRefund:b rootNodeID:n? uiTextureKit:s titleText:s?",
    node = "ID:n posX:n posY:n flags:n canPurchaseRank:b canRefundRank:b isAvailable:b isVisible:b isDisplayError:b ranksPurchased:n ranksIncreased:n activeRank:n currentRank:n maxRanks:n totalMaxRanks:n type:n meetsEdgeRequirements:b isCascadeRepurchasable:b cascadeRepurchaseEntryID:n? subTreeID:n? subTreeActive:b?",
    entry = "definitionID:n? subTreeID:n? type:n maxRanks:n isAvailable:b isDisplayError:b",
    definition = "spellID:n? overrideName:s? overrideSubtext:s? overrideDescription:s? overrideIcon:n? overriddenSpellID:n? subType:n?",
    condition = "condID:n ranksGranted:n? isAlwaysMet:b isMet:b isGate:b isSufficient:b type:n questID:n? achievementID:n? specSetID:n? playerLevel:n? traitCurrencyID:n? spentAmountRequired:n? tooltipFormat:s? traitCondAccountElementID:n?",
    group = "groupID:n treeID:n skillLineID:n orderIndex:n displayName:s icon:n",
    subtree = "ID:n name:s? description:s? iconElementID:s? traitCurrencyID:n? isActive:b posX:n posY:n",
    edge = "targetNode:n type:n visualStyle:n isActive:b",
    gate = "topLeftNodeID:n conditionID:n",
    cost = "ID:n amount:n",
    currency = "traitCurrencyID:n quantity:n maxQuantity:n? spent:n spentInTree:n?",
    rank = "entryID:n rank:n",
}

local function numberID(value)
    local result = FT.Value(value, "number")
    if result and result > 0 and result % 1 == 0 then
        return result
    end
end

local function fields(source, schema, missing, path)
    local result = {}
    if not FT.Value(source, "table") then
        missing[path] = "not_ready_or_restricted"
        return result
    end
    for name, kind, optional in string.gmatch(schema, "(%w+):([nsb])(%??)") do
        local ok, raw = pcall(function()
            return source[name]
        end)
        local value = ok and FT.Value(raw, types[kind]) or nil
        if kind == "b" and ok and FT.Value(raw, "boolean") == false then
            value = false
        end
        result[name] = value
        if value == nil and (not ok or not FT.Readable(raw) or raw ~= nil or optional ~= "?") then
            missing[path .. "." .. name] = "not_ready_or_restricted"
        end
    end
    return result
end

local function array(source, schema, limit, missing, path)
    local result = {}
    local count  = FT.Length(source)
    if not count or count < 0 or count % 1 ~= 0 then
        missing[path] = "not_ready_or_restricted"
        return nil
    end
    if count > limit then
        missing[path] = "capacity_limit"
    end
    for index = 1, math.min(count, limit) do
        local item = FT.Field(source, index, schema and "table" or "number")
        if schema then
            result[#result + 1] = fields(item, schema, missing, path .. "." .. index)
        elseif item then
            result[#result + 1] = item
        else
            missing[path .. "." .. index] = "not_ready_or_restricted"
        end
    end
    return result
end

local function addArray(info, source, key, schema, limit, missing)
    info[key] = array(FT.Field(source, key, "table"), schema, limit, missing, "data.info." .. key)
    if not schema then
        for index, id in ipairs(info[key] or {}) do
            if not numberID(id) then
                missing["data.info." .. key .. "." .. index] = "invalid_identifier"
            end
        end
    end
end

local function emitted(kind, key, data, missing)
    if not scan then
        return nil
    end
    local running = scan
    local saved   = cache[key]
    if next(missing) then
        scan.partial = true
    end
    data.completeness = next(missing) and "partial" or "complete"
    if saved and FT.Equal(saved.data, data) and FT.Equal(saved.missing, missing) then
        return saved.id
    end
    local id = FT.Emit(kind, data, scan.capture, "api_snapshot", nil, missing)
    if id and scan == running then
        scan.metadata_count = scan.metadata_count + 1
        if saved or cacheCount < 8192 then
            if not saved then
                cacheCount = cacheCount + 1
            end
            cache[key] = { data = data, missing = missing, id = id }
        end
    end
    return id
end

local function metadata(entity, id, info, missing, treeID)
    if not scan then
        return nil
    end
    return emitted("talent.metadata", entity .. ":" .. scan.config_id .. ":" .. tostring(id), {
        entity_type = entity, entity_id = id, config_id = scan.config_id,
        tree_id = treeID, info = info,
    }, missing)
end

local function condition(id, treeID)
    if not scan or not numberID(id) or scan.conditions[id] then
        return
    end
    scan.conditions[id] = true
    local missing = {}
    local info    = fields(FT.Call("C_Traits.GetConditionInfo", scan.config_id, id), schemas.condition, missing, "data.info")
    metadata("condition", id, info, missing, treeID)
end

local function subtree(id, treeID)
    if not scan or not numberID(id) or scan.subtrees[id] then
        return
    end
    scan.subtrees[id] = true
    local missing = {}
    local raw     = FT.Call("C_Traits.GetSubTreeInfo", scan.config_id, id)
    local info    = fields(raw, schemas.subtree, missing, "data.info")
    addArray(info, raw, "subTreeSelectionNodeIDs", nil, 64, missing)
    metadata("subtree", id, info, missing, treeID)
end

local function definition(id, treeID)
    if not scan or not numberID(id) or scan.definitions[id] then
        return
    end
    scan.definitions[id] = true
    local missing = {}
    local info    = fields(FT.Call("C_Traits.GetDefinitionInfo", id), schemas.definition, missing, "data.info")
    local record  = metadata("definition", id, info, missing, treeID)
    if record and FT.RequestSpell then
        if numberID(info.spellID) then
            FT.RequestSpell(info.spellID, record, scan and scan.force)
        end
        if numberID(info.overriddenSpellID) then
            FT.RequestSpell(info.overriddenSpellID, record, scan and scan.force)
        end
    end
end

local function entry(id, treeID)
    if not scan or not numberID(id) or scan.entries[id] then
        return
    end
    scan.entries[id] = true
    local missing = {}
    local raw     = FT.Call("C_Traits.GetEntryInfo", scan.config_id, id)
    local info    = fields(raw, schemas.entry, missing, "data.info")
    addArray(info, raw, "conditionIDs", nil, 64, missing)
    if not info.maxRanks or info.maxRanks < 0 or info.maxRanks % 1 ~= 0 then
        missing["data.info.maxRanks"] = "invalid_or_unavailable"
    elseif info.maxRanks > 32 then
        missing["data.rank_descriptions"] = "capacity_limit"
    end
    if not metadata("entry", id, info, missing, treeID) then
        return
    end
    definition(info.definitionID, treeID)
    subtree(info.subTreeID, treeID)
    for _, conditionID in ipairs(info.conditionIDs or {}) do
        condition(conditionID, treeID)
    end
    if info.maxRanks and info.maxRanks >= 0 and info.maxRanks % 1 == 0 then
        for rank = 1, math.min(info.maxRanks, 32) do
            if not scan then
                return
            end
            local description = FT.Value(FT.Call("C_Traits.GetTraitDescription", id, rank), "string")
            local absent      = {}
            if not description then
                absent["data.description"] = "not_ready_or_restricted"
            end
            emitted("talent.rank", "rank:" .. id .. ":" .. rank, {
                entry_id = id, rank = rank, description = description,
            }, absent)
        end
    end
end

local function node(id, treeID)
    local missing = {}
    local raw     = FT.Call("C_Traits.GetNodeInfo", scan.config_id, id)
    local info    = fields(raw, schemas.node, missing, "data.info")
    for _, name in ipairs({ "entryIDs", "entryIDsWithCommittedRanks", "groupIDs", "conditionIDs" }) do
        addArray(info, raw, name, nil, 64, missing)
    end
    addArray(info, raw, "visibleEdges", schemas.edge, 64, missing)
    for _, name in ipairs({ "activeEntry", "nextEntry" }) do
        local value = FT.Field(raw, name, "table")
        if value then
            info[name] = fields(value, schemas.rank, missing, "data.info." .. name)
        elseif FT.Value(raw, "table") then
            local ok, result = pcall(function()
                return raw[name]
            end)
            if not ok or not FT.Readable(result) or result ~= nil then
                missing["data.info." .. name] = "not_ready_or_restricted"
            end
        end
    end
    info.costs = array(FT.Call("C_Traits.GetNodeCost", scan.config_id, id), schemas.cost, 32, missing, "data.info.costs")
    local increases = FT.Field(raw, "entryIDToRanksIncreased", "table")
    if not increases then
        missing["data.info.entry_rank_increases"] = "not_ready_or_restricted"
    else
        info.entry_rank_increases = {}
        for _, entryID in ipairs(info.entryIDs or {}) do
            local amount = FT.Field(increases, entryID, "number")
            if amount then
                info.entry_rank_increases[#info.entry_rank_increases + 1] = { entry_id = entryID, ranks_increased = amount }
            else
                missing["data.info.entry_rank_increases." .. entryID] = "not_ready_or_restricted"
            end
        end
    end
    local record = metadata("node", id, info, missing, treeID)
    if not record or not scan then
        return
    end
    scan.build[#scan.build + 1] = {
        tree_id = treeID, node_id = id, node_observation_id = record,
        ranks_purchased = info.ranksPurchased, active_rank = info.activeRank,
        current_rank = info.currentRank, active_entry = info.activeEntry,
        committed_entry_ids = info.entryIDsWithCommittedRanks,
        completeness = next(missing) and "partial" or "complete",
    }
    scan.node_count = scan.node_count + 1
    subtree(info.subTreeID, treeID)
    for _, entryID in ipairs(info.entryIDs or {}) do
        entry(entryID, treeID)
    end
    for _, conditionID in ipairs(info.conditionIDs or {}) do
        condition(conditionID, treeID)
    end
end

local function tree(id)
    local missing = {}
    local raw     = FT.Call("C_Traits.GetTreeInfo", scan.config_id, id)
    local info    = fields(raw, schemas.tree, missing, "data.info")
    addArray(info, raw, "gates", schemas.gate, 64, missing)
    info.tree_hash = array(FT.Call("C_Traits.GetTreeHash", id), nil, 64, missing, "data.info.tree_hash")
    info.currencies = array(FT.Call("C_Traits.GetTreeCurrencyInfo", scan.config_id, id, true), schemas.currency, 32, missing, "data.info.currencies")
    local nodes = array(FT.Call("C_Traits.GetTreeNodes", id), nil, 2048, missing, "data.node_ids")
    if not nodes then
        scan.enumeration_complete = false
    end
    for path in pairs(missing) do
        if string.match(path, "^data%.node_ids") then
            scan.enumeration_complete = false
        end
    end
    info.node_count = nodes and #nodes or nil
    if not metadata("tree", id, info, missing, id) then
        return
    end
    for _, gate in ipairs(info.gates or {}) do
        condition(gate.conditionID, id)
    end
    local groupMissing = {}
    local groups       = array(FT.Call("C_Traits.GetGroupDisplayInfoByTreeID", id), schemas.group, 64, groupMissing, "data.info.groups")
    if not scan then
        return
    end
    if next(groupMissing) then
        scan.partial = true
        scan.missing["data.groups"] = "not_ready_or_restricted"
    end
    for _, group in ipairs(groups or {}) do
        local absent = {}
        for key, reason in pairs(groupMissing) do
            absent[key] = reason
        end
        metadata("group", group.groupID, group, absent, id)
    end
    if not scan then
        return
    end
    for _, nodeID in ipairs(nodes or {}) do
        if numberID(nodeID) and #scan.queue < 4096 then
            scan.queue[#scan.queue + 1] = { tree_id = id, node_id = nodeID }
        else
            scan.partial = true
            scan.enumeration_complete = false
            scan.missing["data.nodes"] = "invalid_or_capacity_limit"
        end
    end
end

local function finish()
    local running = scan
    local active = numberID(FT.Call("C_ClassTalents.GetActiveConfigID"))
    local staged = scan.config_id and FT.Value(FT.Call("C_Traits.ConfigHasStagedChanges", scan.config_id), "boolean")
    if active ~= scan.config_id or staged ~= scan.has_staged_changes or scan.invalidated then
        scan.partial = true
        scan.missing["data.consistency"] = "changed_during_scan"
    end
    if scan.partial and not next(scan.missing) then
        scan.missing["data.metadata"] = "incomplete_metadata"
    end
    local signature = {
        config_id = scan.config_id, tree_ids = scan.tree_ids,
        has_staged_changes = scan.has_staged_changes, nodes = scan.build,
    }
    local changed = not FT.Equal(signature, lastBuild)
    if changed or scan.force or scan.partial or lastPartial or scan.metadata_count > 0 then
        local links = {}
        local chunk = 0
        for first = 1, #scan.build, 32 do
            local rows = {}
            local refs = {}
            chunk = chunk + 1
            for index = first, math.min(first + 31, #scan.build) do
                local row = scan.build[index]
                rows[#rows + 1] = row
                if row.node_observation_id then
                    refs[#refs + 1] = row.node_observation_id
                end
            end
            local id = FT.Emit("talent.build", {
                scan_id = scan.id, config_id = scan.config_id, chunk_index = chunk,
                nodes = rows, completeness = scan.partial and "partial" or "complete",
            }, scan.capture, "api_snapshot", refs)
            if scan ~= running then
                return
            end
            if id then
                links[#links + 1] = id
            end
        end
        lastID = FT.Emit("talent.snapshot", {
            scan_id = scan.id, config_id = scan.config_id, tree_ids = scan.tree_ids,
            scope = "active_player_config_and_readable_class_tree",
            has_staged_changes = scan.has_staged_changes, node_count = scan.node_count,
            expected_node_count = scan.enumeration_complete and #scan.queue or nil, chunk_count = chunk,
            metadata_count = scan.metadata_count, completeness = scan.partial and "partial" or "complete",
            previous_snapshot_id = lastID,
        }, scan.capture, "api_snapshot", links, scan.missing)
        if scan ~= running then
            return
        end
    end
    if not scan.partial then
        lastBuild = signature
    end
    lastPartial = scan.partial
    status      = { scanning = false, node_count = scan.node_count, completeness = scan.partial and "partial" or "complete" }
    scan        = nil
    if pending then
        local capture = pending
        pending = nil
        FT.CaptureTalents(capture)
    end
end

local function step()
    if not scan then
        return
    end
    if not FT.InWorld then
        scan.partial = true
        scan.missing["data.consistency"] = "world_transition"
        finish()
        return
    end
    for _ = 1, 4 do
        local work = scan.queue[scan.cursor]
        if not work then
            finish()
            return
        end
        scan.cursor = scan.cursor + 1
        node(work.node_id, work.tree_id)
        if not scan or FT.Blocked then
            return
        end
    end
    status.node_count = scan.node_count
    FT.Schedule("talents.scan", 0.05, step)
end

function FT.CaptureTalents(capture)
    local recording = FT.Status()
    if not FT.Profile.supported or FT.Profile.talents ~= "traits" or not FT.InWorld
        or not recording.initialized or recording.paused or recording.blocked then
        return
    end
    capture = capture or { method = "catalog_scan" }
    if scan then
        if not pending or capture == "FT_CATALOG" or type(capture) == "table" and capture.method == "catalog_scan" then
            pending = capture
        end
        scan.invalidated = true
        return
    end
    local configID = numberID(FT.Call("C_ClassTalents.GetActiveConfigID"))
    scan = {
        id = FT.NewContext("talents"), config_id = configID, capture = capture,
        force = type(capture) == "table" and capture.method == "catalog_scan" or capture == "FT_CATALOG",
        partial = false, missing = {}, queue = {}, cursor = 1, build = {}, enumeration_complete = true,
        definitions = {}, entries = {}, conditions = {}, subtrees = {}, node_count = 0, metadata_count = 0,
    }
    status = { scanning = true, node_count = 0 }
    if not configID then
        scan.partial = true
        scan.enumeration_complete = false
        scan.missing["data.config_id"] = "unavailable_or_restricted"
        finish()
        return
    end
    local missing = {}
    local raw     = FT.Call("C_Traits.GetConfigInfo", configID)
    local info    = fields(raw, schemas.config, missing, "data.info")
    addArray(info, raw, "treeIDs", nil, 16, missing)
    if not info.treeIDs or missing["data.info.treeIDs"] then
        scan.enumeration_complete = false
    end
    for path in pairs(missing) do
        if string.match(path, "^data%.info%.treeIDs") then
            scan.enumeration_complete = false
        end
    end
    scan.has_staged_changes = FT.Value(FT.Call("C_Traits.ConfigHasStagedChanges", configID), "boolean")
    if scan.has_staged_changes == nil then
        missing["data.has_staged_changes"] = "not_ready_or_restricted"
    end
    if not metadata("config", configID, info, missing) then
        return
    end
    scan.tree_ids = info.treeIDs and {} or nil
    for _, treeID in ipairs(info.treeIDs or {}) do
        if numberID(treeID) then
            scan.tree_ids[#scan.tree_ids + 1] = treeID
            tree(treeID)
            if not scan then
                return
            end
        else
            scan.partial = true
            scan.enumeration_complete = false
            scan.missing["data.tree_ids"] = "invalid_result"
        end
    end
    FT.Schedule("talents.scan", 0.05, step)
end

function FT.TalentStatus()
    return FT.Copy(status)
end

local function request(event)
    local capture   = event
    local recording = FT.Status()
    if not FT.Profile.supported or FT.Profile.talents ~= "traits" or not FT.InWorld
        or not recording.initialized or recording.paused or recording.blocked then
        return
    end
    status.scanning = true
    if scan then
        if not pending or capture == "FT_CATALOG" then
            pending = capture
        end
        scan.invalidated = true
    else
        if not requested or capture == "FT_CATALOG" then
            requested = capture
        end
        FT.Schedule("talents.request", 0.2, function()
            local nextCapture = requested
            requested = nil
            FT.CaptureTalents(nextCapture)
        end)
    end
end

for _, event in ipairs({
    "PLAYER_ENTERING_WORLD", "FT_BASELINE", "FT_CATALOG", "PLAYER_TALENT_UPDATE",
    "ACTIVE_COMBAT_CONFIG_CHANGED", "ACTIVE_PLAYER_SPECIALIZATION_CHANGED",
    "TRAIT_CONFIG_UPDATED", "TRAIT_CONFIG_LIST_UPDATED", "TRAIT_TREE_CHANGED",
    "TRAIT_NODE_CHANGED", "TRAIT_NODE_CHANGED_PARTIAL", "TRAIT_NODE_ENTRY_UPDATED",
    "TRAIT_COND_INFO_CHANGED", "TRAIT_SUB_TREE_CHANGED", "TRAIT_TREE_CURRENCY_INFO_UPDATED",
}) do
    FT.On(event, request)
end

FT.OnReset(function(reason)
    if reason == "user_clear" then
        cache      = {}
        cacheCount = 0
    end
    scan        = nil
    pending     = nil
    requested   = nil
    lastBuild   = nil
    lastID      = nil
    lastPartial = false
    status      = { scanning = false }
end)
