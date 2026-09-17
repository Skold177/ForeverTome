local _, FT = ...

local LIMIT = { entries = 2048, lines = 64, flyout = 32, pending = 1024, cache = 4096, batch = 8 }

local pending      = {}
local queue        = {}
local cache        = {}
local pendingCount = 0
local cacheCount   = 0
local generation   = 0
local revision     = 0
local scan
local scheduled
local previous
local lastStatus   = "not_observed"
local lastCount    = 0
local droppedCount = 0
local metadataWork
local scheduleScan

local function integer(value, minimum, maximum)
    value = FT.Value(value, "number")
    if value and value % 1 == 0 and value >= minimum and value <= maximum then
        return value
    end
end

local function contentID(value)
    return integer(value, 1, 2147483647)
end

local function enabled()
    return FT.Profile.supported and FT.Profile.spellbook == "modern" and FT.InWorld
end

local function fields(source, types, missing, prefix)
    local result = {}
    for key, kind in pairs(types) do
        result[key] = FT.Field(source, key, kind)
        if missing and result[key] == nil then
            missing[(prefix or "") .. key] = "not_ready_or_restricted"
        end
    end
    return result
end

local function addReference(request, reference)
    reference = FT.Value(reference, "string")
    if not reference then
        return
    end
    for _, existing in ipairs(request.references) do
        if existing == reference then
            return
        end
    end
    if #request.references < 32 then
        request.references[#request.references + 1] = reference
    else
        request.references_truncated = true
    end
end

local function tooltipField(line, key, kind)
    if not FT.Value(line, "table") then
        return nil, true
    end
    local ok, raw = pcall(function()
        return line[key]
    end)
    if not ok or not FT.Readable(raw) then
        return nil, true
    end
    if raw == nil then
        return nil, false
    end
    local value = FT.Value(raw, kind)
    if value == nil or kind == "string" and #value > 1024 then
        return nil, true
    end
    return value, false
end

local function readTooltip(data, missing, spellID)
    data.tooltip_method  = "C_TooltipInfo.GetSpellByID"
    data.tooltip_context = "character_at_observation"
    if not FT.Profile.spell_tooltips or not FT.Resolve(data.tooltip_method) then
        data.tooltip_status           = "unsupported"
        missing["data.tooltip_lines"] = "unsupported"
        return false
    end
    local raw   = FT.Call(data.tooltip_method, spellID, nil, true, true)
    local lines = FT.Field(raw, "lines", "table")
    local count = FT.Length(lines)
    if not count then
        data.tooltip_status           = "unavailable"
        missing["data.tooltip_lines"] = "not_ready_or_restricted"
        return true
    end
    data.tooltip_lines = {}
    local reason       = count > 64 and "capacity_limit" or nil
    for index = 1, math.min(count, 64) do
        local rawLine         = FT.Field(lines, index, "table")
        local left, badLeft   = tooltipField(rawLine, "leftText", "string")
        local right, badRight = tooltipField(rawLine, "rightText", "string")
        local kind, badKind   = tooltipField(rawLine, "type", "number")
        local lineType        = integer(kind, 0, 255)
        if badLeft or badRight or badKind or kind ~= nil and lineType == nil then
            reason = reason or "invalid_or_unreadable"
        end
        if left ~= nil or right ~= nil or lineType ~= nil then
            data.tooltip_lines[#data.tooltip_lines + 1] = {
                index = index, left_text = left, right_text = right, type = lineType,
            }
        else
            reason = reason or "invalid_or_unreadable"
        end
    end
    data.tooltip_status           = reason and "partial" or "available"
    missing["data.tooltip_lines"] = reason
    return false
end

local function readMetadata(spellID)
    local missing = {}
    local source  = FT.Call("C_Spell.GetSpellInfo", spellID)
    local data    = fields(source, {
        name = "string", iconID = "number", originalIconID = "number", castTime = "number",
        minRange = "number", maxRange = "number",
    }, missing, "data.")
    data.cast_time_status = data.castTime ~= nil and "available" or "unavailable"
    if data.castTime and data.castTime < 0 then
        data.reported_cast_time_ms = data.castTime
        data.castTime              = nil
        data.cast_time_status      = "invalid_result"
        missing["data.castTime"]  = "invalid_result"
    end
    data.spell_id              = spellID
    data.resolved_spell_id     = contentID(FT.Field(source, "spellID", "number"))
    data.description           = FT.Value(FT.Call("C_Spell.GetSpellDescription", spellID), "string")
    data.subtext               = FT.Value(FT.Call("C_Spell.GetSpellSubtext", spellID), "string")
    data.is_passive            = FT.Value(FT.Call("C_Spell.IsSpellPassive", spellID), "boolean")
    data.base_spell_id         = contentID(FT.Call("C_SpellBook.FindBaseSpellByID", spellID))
    data.override_spell_id     = contentID(FT.Call("C_SpellBook.FindSpellOverrideByID", spellID))
    data.values_context        = "character_at_observation"
    data.base_cooldown_status  = "unsupported_client_contract"
    data.current_state        = {}
    missing["data.base_cooldown_ms"] = "unsupported"
    for _, key in ipairs({ "description", "subtext", "is_passive" }) do
        if data[key] == nil then
            missing["data." .. key] = "not_ready_or_restricted"
        end
    end
    if data.description == "" then
        missing["data.description"] = "empty_or_not_ready"
    end
    local costs     = FT.Call("C_Spell.GetSpellPowerCost", spellID)
    local costCount = FT.Length(costs)
    if not costCount then
        missing["data.current_state.power_costs"] = FT.Resolve("C_Spell.GetSpellPowerCost")
            and "no_cost_or_not_ready" or "unsupported"
    elseif costCount > 16 then
        missing["data.current_state.power_costs"] = "capacity_limit"
    end
    if costCount then
        data.current_state.power_costs = {}
    end
    for index = 1, math.min(costCount or 0, 16) do
        local cost = fields(FT.Field(costs, index, "table"), {
            type = "number", name = "string", cost = "number", minCost = "number",
            costPercent = "number", costPerSec = "number", requiredAuraID = "number", hasRequiredAura = "boolean",
        }, missing, "data.current_state.power_costs." .. index .. ".")
        data.current_state.power_costs[#data.current_state.power_costs + 1] = cost
    end
    local cooldown = FT.Call("C_Spell.GetSpellCooldown", spellID)
    if FT.Value(cooldown, "table") then
        data.current_state.cooldown = fields(cooldown, {
            startTime = "number", duration = "number", isEnabled = "boolean", isActive = "boolean", modRate = "number",
        }, missing, "data.current_state.cooldown.")
    else
        missing["data.current_state.cooldown"] = FT.Resolve("C_Spell.GetSpellCooldown")
            and "not_applicable_or_restricted" or "unsupported"
    end
    local charges = FT.Call("C_Spell.GetSpellCharges", spellID)
    if FT.Value(charges, "table") then
        data.current_state.charges = fields(charges, {
            currentCharges = "number", maxCharges = "number", cooldownStartTime = "number",
            cooldownDuration = "number", chargeModRate = "number", isActive = "boolean",
        }, missing, "data.current_state.charges.")
    else
        missing["data.current_state.charges"] = FT.Resolve("C_Spell.GetSpellCharges")
            and "not_charge_based_or_not_ready" or "unsupported"
    end
    local tooltipRetry = readTooltip(data, missing, spellID)
    local textRetry    = (not data.name and FT.Resolve("C_Spell.GetSpellInfo"))
        or ((not data.description or data.description == "") and FT.Resolve("C_Spell.GetSpellDescription"))
    data.text_status  = textRetry and "pending" or (data.name and data.description and "available" or "unavailable")
    data.completeness = next(missing) and "partial" or "complete"
    return data, missing, (textRetry or tooltipRetry) and true or false
end

local function enqueue(spellID, reference, force)
    if not enabled() then
        return
    end
    spellID = contentID(spellID)
    if not spellID then
        return
    end
    local request = pending[spellID]
    if request then
        addReference(request, reference)
        return
    end
    local prior = cache[spellID]
    if prior and not force then
        return
    end
    if pendingCount >= LIMIT.pending or (not prior and cacheCount + pendingCount >= LIMIT.cache) then
        FT.Diagnostic("capacity_limit", "spell_metadata")
        droppedCount = droppedCount + 1
        if droppedCount == 1 then
            FT.Emit("spell.metadata_unavailable", {
                spell_id = spellID, reason = "capacity_limit", scope = "metadata_request_queue",
            }, { method = "metadata_read" }, "api_snapshot", reference and { reference } or {},
                { ["data.metadata"] = "capacity_limit" })
        end
        return
    end
    request = {
        spell_id = spellID, references = {}, attempts = 0, next_at = FT.Now(), generation = generation,
        requested_at_s = FT.Now(), origin_location = FT.Location(), prior = prior,
        last = prior and prior.last, last_id = prior and prior.observation_id,
    }
    if prior then
        for _, id in ipairs(prior.references) do
            addReference(request, id)
        end
        addReference(request, prior.observation_id)
    end
    addReference(request, reference)
    pending[spellID] = request
    pendingCount    = pendingCount + 1
    queue[#queue + 1] = request
    FT.Schedule("spells.metadata", 0.05, metadataWork)
end

function FT.RequestSpell(spellID, relatedObservationID, force)
    enqueue(spellID, relatedObservationID, force == true)
end

metadataWork = function()
    if not enabled() then
        return
    end
    local batch = {}
    local now   = FT.Now()
    for _ = 1, math.min(#queue, LIMIT.batch) do
        local request = table.remove(queue, 1)
        if pending[request.spell_id] == request and request.generation == generation then
            if request.next_at <= now then
                batch[#batch + 1] = request
            else
                queue[#queue + 1] = request
            end
        end
    end
    for _, request in ipairs(batch) do
        local data, missing, retry = readMetadata(request.spell_id)
        request.attempts = request.attempts + 1
        local exhausted = request.attempts >= 3
        if exhausted and data.text_status == "pending" then
            data.text_status = "unresolved"
        end
        if not request.last or not FT.Equal(request.last, { data = data, missing = missing }) then
            data.metadata_origin = {
                requested_at_s = request.requested_at_s, location = request.origin_location,
                references_truncated = request.references_truncated or false,
            }
            local id = FT.Emit("spell.metadata", data, {
                api = "C_Spell.GetSpellInfo", method = "metadata_read", attempt = request.attempts,
            }, "api_snapshot", request.references, missing)
            data.metadata_origin = nil
            if request.generation ~= generation then
                return
            end
            request.last_id = id or request.last_id
            request.last    = { data = data, missing = missing }
        end
        if not retry or exhausted then
            if retry then
                local unresolved = {}
                local reason     = "tooltip_not_ready_after_retries"
                if data.text_status == "unresolved" then
                    unresolved["data.description"] = "not_ready"
                    reason                         = "text_not_ready_after_retries"
                end
                if data.tooltip_status == "unavailable" then
                    unresolved["data.tooltip_lines"] = "not_ready"
                end
                FT.Emit("spell.metadata_unavailable", {
                    spell_id = request.spell_id, attempts = request.attempts, reason = reason,
                    requested_at_s = request.requested_at_s, origin_location = request.origin_location,
                }, { method = "metadata_retry_exhausted" }, "api_snapshot", request.references,
                    unresolved)
            end
            if request.generation ~= generation then
                return
            end
            if not cache[request.spell_id] then
                cacheCount = cacheCount + 1
            end
            cache[request.spell_id] = {
                references = request.references, observation_id = request.last_id,
                refreshed_at = now, unresolved = retry, last = request.last,
            }
            pending[request.spell_id] = nil
            pendingCount             = pendingCount - 1
        else
            request.next_at = now + (request.attempts == 1 and 1 or 4)
            queue[#queue + 1] = request
            FT.Call("C_Spell.RequestLoadSpellData", request.spell_id)
        end
    end
    if #queue > 0 then
        FT.Schedule("spells.metadata", 0.1, metadataWork)
    end
end

local function enumValue(tableName, key)
    local enum  = FT.Value(Enum, "table")
    local group = FT.Field(enum, tableName, "table")
    return FT.Field(group, key, "number")
end

local function readTopology()
    local topology = { skill_lines = {}, slots = {}, missing = {} }
    local count    = integer(FT.Call("C_SpellBook.GetNumSpellBookSkillLines"), 0, 100000)
    local player   = enumValue("SpellBookSpellBank", "Player")
    local pet      = enumValue("SpellBookSpellBank", "Pet")
    if not count or player == nil then
        topology.missing["data.skill_lines"] = "not_ready_or_unsupported"
    elseif count > LIMIT.lines then
        topology.missing["data.skill_lines"] = "capacity_limit"
    end
    if count and player ~= nil then
        topology.player_count = 0
    end
    local seen = {}
    for index = 1, math.min(count or 0, LIMIT.lines) do
        local source = FT.Call("C_SpellBook.GetSpellBookSkillLineInfo", index)
        local line   = fields(source, {
            name = "string", iconID = "number", itemIndexOffset = "number", numSpellBookItems = "number",
            isGuild = "boolean", shouldHide = "boolean",
        }, topology.missing, "data.skill_lines." .. index .. ".")
        line.index     = index
        line.specID    = FT.Field(source, "specID", "number")
        line.offSpecID = FT.Field(source, "offSpecID", "number")
        topology.skill_lines[#topology.skill_lines + 1] = line
        local offset = integer(line.itemIndexOffset, 0, 100000)
        local length = integer(line.numSpellBookItems, 0, 100000)
        if offset and length and player ~= nil then
            topology.player_count = topology.player_count + length
            for item = 1, math.min(length, LIMIT.entries) do
                local slot = offset + item
                if #topology.slots >= LIMIT.entries then
                    topology.missing["data.entries"] = "capacity_limit"
                    break
                end
                if seen[slot] then
                    topology.missing["data.entries"] = "overlapping_skill_lines"
                else
                    topology.slots[#topology.slots + 1] = { slot = slot, bank = player, bank_name = "player", line = index }
                    seen[slot] = true
                end
            end
            if length > LIMIT.entries then
                topology.missing["data.entries"] = "capacity_limit"
            end
        else
            topology.missing["data.skill_lines." .. index] = "invalid_or_unavailable_range"
        end
    end
    local ok, petCount = FT.TryCall("C_SpellBook.HasPetSpells")
    if ok and petCount == nil then
        petCount = 0
    end
    petCount = integer(petCount, 0, 100000)
    if not ok or not petCount or pet == nil then
        topology.missing["data.pet_entries"] = "not_ready_or_unsupported"
    else
        topology.pet_count = petCount
        for slot = 1, math.min(petCount, LIMIT.entries) do
            if #topology.slots >= LIMIT.entries then
                topology.missing["data.entries"] = "capacity_limit"
                break
            end
            topology.slots[#topology.slots + 1] = { slot = slot, bank = pet, bank_name = "pet" }
        end
        if petCount > LIMIT.entries then
            topology.missing["data.pet_entries"] = "capacity_limit"
        end
    end
    return topology
end

local function readEntry(slot)
    local missing = {}
    local source  = FT.Call("C_SpellBook.GetSpellBookItemInfo", slot.slot, slot.bank)
    local row     = fields(source, {
        actionID = "number", itemType = "number", name = "string", subName = "string",
        iconID = "number", isPassive = "boolean", isOffSpec = "boolean",
    }, missing)
    row.slot            = slot.slot
    row.bank            = slot.bank_name
    row.skillLineIndex  = FT.Field(source, "skillLineIndex", "number") or slot.line
    row.spellID         = contentID(FT.Field(source, "spellID", "number"))
    row.levelLearned    = FT.Value(FT.Call("C_SpellBook.GetSpellBookItemLevelLearned", slot.slot, slot.bank), "number")
    row.is_low_rank     = FT.Value(FT.Call("C_SpellBook.IsSpellBookItemLowRank", slot.slot, slot.bank), "boolean")
    row.is_flyout_member = FT.Value(FT.Call("C_SpellBook.IsSpellBookItemLooseFlyoutMember", slot.slot, slot.bank), "boolean")
    for _, key in ipairs({ "levelLearned", "is_low_rank", "is_flyout_member" }) do
        if row[key] == nil then
            missing[key] = "not_ready_or_unsupported"
        end
    end
    row.item_type       = "unknown"
    for _, name in ipairs({ "None", "Spell", "FutureSpell", "PetAction", "Flyout" }) do
        local value = enumValue("SpellBookItemType", name)
        if value ~= nil and row.itemType == value then
            row.item_type = name
            break
        end
    end
    if row.item_type == "Spell" or row.item_type == "FutureSpell" then
        if not row.spellID then
            missing.spellID = "not_ready_or_restricted"
        end
        if row.spellID then
            row.is_known = FT.Value(FT.Call("C_SpellBook.IsSpellKnown", row.spellID, slot.bank), "boolean")
            if row.is_known == nil then
                missing.is_known = "not_ready_or_unsupported"
            end
        end
    elseif row.item_type == "Flyout" then
        local flyoutID = contentID(row.actionID)
        local name, description, count, known
        if flyoutID then
            name, description, count, known = FT.Call("GetFlyoutInfo", flyoutID)
        end
        row.flyout_name        = FT.Value(name, "string")
        row.flyout_description = FT.Value(description, "string")
        row.is_known           = FT.Value(known, "boolean")
        count = integer(count, 0, 100000)
        if not count then
            missing.flyout_slots = "not_ready_or_unsupported"
        elseif count > LIMIT.flyout then
            missing.flyout_slots = "capacity_limit"
        end
        if count then
            row.flyout_slots = {}
        end
        for index = 1, math.min(count or 0, LIMIT.flyout) do
            local id, override, isKnown, spellName, specID = FT.Call("GetFlyoutSlotInfo", flyoutID, index)
            local child = {
                index = index, spell_id = contentID(id), override_spell_id = contentID(override),
                is_known = FT.Value(isKnown, "boolean"), name = FT.Value(spellName, "string"),
                spec_id = FT.Value(specID, "number"),
            }
            if not child.spell_id then
                missing["flyout_slots." .. index] = "not_ready_or_restricted"
            end
            row.flyout_slots[#row.flyout_slots + 1] = child
        end
    elseif row.item_type == "unknown" then
        missing.item_type = "unknown_enum"
    end
    row.missing_fields = missing
    row.completeness   = next(missing) and "partial" or "complete"
    return row
end

local function requestEntry(row, reference, force)
    enqueue(row.spellID, reference, force)
    if row.item_type == "Spell" or row.item_type == "FutureSpell" then
        if row.actionID ~= row.spellID then
            enqueue(row.actionID, reference, force)
        end
    end
    for _, child in ipairs(row.flyout_slots or {}) do
        enqueue(child.spell_id, reference, force)
        if child.override_spell_id ~= child.spell_id then
            enqueue(child.override_spell_id, reference, force)
        end
    end
end

local function membership(entries)
    local result = {}
    for _, row in ipairs(entries) do
        if row.bank == "player" and row.spellID then
            result[row.spellID] = true
        end
    end
    return result
end

local function finishScan(current)
    if current.revision ~= revision then
        current.missing["data.entries"] = "changed_during_scan"
    end
    local complete   = next(current.missing) == nil
    local comparison = { topology = current.topology, entries = current.entries, complete = complete }
    local unchanged  = current.unchanged and complete == current.complete
    local manifest = FT.Emit("spellbook.scan", {
        snapshot_id = current.id, completeness = complete and "complete" or "partial",
        player_count = current.topology.player_count, pet_count = current.topology.pet_count,
        observed_entry_count = #current.entries, chunk_count = #current.chunks, unchanged = unchanged and not current.force or false,
        previous_snapshot_id = previous and previous.id, started_at_s = current.started_at,
        scope = "readable_spellbook_entries", includes_unlearned = true,
    }, current.event, "api_snapshot", previous and { previous.observation_id } or {}, current.missing)
    if current.generation ~= generation then
        return
    end
    if complete and previous and previous.comparable and previous.comparison.complete then
        local old     = membership(previous.comparison.entries)
        local new     = membership(current.entries)
        local added   = {}
        local removed = {}
        for spellID in pairs(new) do
            if not old[spellID] then
                added[#added + 1] = spellID
            end
        end
        for spellID in pairs(old) do
            if not new[spellID] then
                removed[#removed + 1] = spellID
            end
        end
        table.sort(added)
        table.sort(removed)
        if #added + #removed > 0 then
            FT.Emit("spellbook.changed", {
                snapshot_id = current.id, previous_snapshot_id = previous.id,
                added_spell_ids = added, removed_spell_ids = removed,
                interpretation = "spellbook_membership_only_not_learning", bank = "player",
            }, current.event, "snapshot_difference", { previous.observation_id, manifest })
        end
    end
    if current.generation ~= generation then
        return
    end
    previous   = { id = unchanged and not current.force and previous.id or current.id,
        observation_id = manifest, comparison = comparison, comparable = true }
    lastStatus = complete and "complete" or "partial"
    lastCount  = #current.entries
    scan       = nil
    if current.revision ~= revision then
        scheduleScan(current.followup_event or { method = "spellbook_rescan" })
    end
end

local function prepareChunks(current)
    local ending = readTopology()
    if current.revision ~= revision or not FT.Equal(current.topology, ending) then
        current.missing["data.entries"] = "changed_during_scan"
    end
    current.complete   = next(current.missing) == nil
    current.unchanged  = previous and FT.Equal(previous.comparison, {
        topology = current.topology, entries = current.entries, complete = current.complete,
    })
    current.chunks    = {}
    current.chunk     = 1
    if current.unchanged and not current.force then
        return
    end
    for _, bank in ipairs({ "player", "pet" }) do
        local rows = {}
        for _, row in ipairs(current.entries) do
            if row.bank == bank then
                rows[#rows + 1] = row
            end
        end
        for start = 1, math.max(1, #rows), 8 do
            local batch = {}
            for index = start, math.min(start + 7, #rows) do
                batch[#batch + 1] = rows[index]
            end
            local known = bank == "player" and current.topology.player_count ~= nil
                or bank == "pet" and current.topology.pet_count ~= nil
            current.chunks[#current.chunks + 1] = {
                bank = bank, entries = known and batch or nil, bank_status = known and "available" or "unavailable",
                skill_lines = bank == "player" and start == 1 and known and current.topology.skill_lines or nil,
            }
        end
    end
end

local function scanWork()
    local current = scan
    if not current or not enabled() then
        return
    end
    if current.chunks then
        local chunk = current.chunks[current.chunk]
        if not chunk then
            finishScan(current)
            return
        end
        local id = FT.Emit("spellbook.snapshot", {
            snapshot_id = current.id, bank = chunk.bank, chunk_index = current.chunk, entries = chunk.entries,
            skill_lines = chunk.skill_lines, bank_status = chunk.bank_status,
            completeness = current.complete and "complete" or "partial", scope = "readable_spellbook_entries",
        }, current.event, "api_snapshot", nil, current.missing)
        if current.generation ~= generation then
            return
        end
        for _, row in ipairs(chunk.entries or {}) do
            requestEntry(row, id, current.force)
        end
        current.chunk = current.chunk + 1
        FT.Schedule("spells.scan_work", 0.05, scanWork)
        return
    end
    for _ = 1, LIMIT.batch do
        local slot = current.topology.slots[current.index]
        if not slot then
            prepareChunks(current)
            FT.Schedule("spells.scan_work", 0.05, scanWork)
            return
        end
        local row = readEntry(slot)
        current.entries[#current.entries + 1] = row
        if row.completeness ~= "complete" then
            current.missing["data.entries." .. current.index] = "partial_entry"
        end
        current.index = current.index + 1
    end
    FT.Schedule("spells.scan_work", 0.05, scanWork)
end

scheduleScan = function(event)
    if not enabled() then
        return
    end
    if scan then
        if event == "FT_CATALOG" then
            scan.force = true
            scan.event = event
            if scan.chunks then
                revision = revision + 1
                scan.followup_event = event
            end
        end
        return
    end
    if scheduled then
        if event == "FT_CATALOG" then
            scheduled.event = event
        end
        return
    end
    scheduled = { event = event }
    FT.Schedule("spells.scan", 0.25, function()
        local request = scheduled
        scheduled = nil
        if not request or not enabled() then
            return
        end
        local topology = readTopology()
        scan = {
            id = FT.NewContext("spellbook"), event = request.event, topology = topology, entries = {},
            missing = FT.Copy(topology.missing), index = 1, started_at = FT.Now(), generation = generation,
            revision = revision, force = request.event == "FT_CATALOG",
        }
        scanWork()
    end)
end

function FT.SpellStatus()
    return { pending = pendingCount, scanning = scan ~= nil or scheduled ~= nil,
        completeness = lastStatus, entry_count = lastCount, cached = cacheCount, metadata_dropped = droppedCount }
end

for _, event in ipairs({ "PLAYER_ENTERING_WORLD", "FT_BASELINE", "FT_CATALOG" }) do
    FT.On(event, function(name)
        if enabled() and pendingCount > 0 then
            FT.Schedule("spells.metadata", 0.05, metadataWork)
        end
        scheduleScan(name)
    end)
end

for _, event in ipairs({ "SPELLS_CHANGED", "SPELL_FLYOUT_UPDATE", "PET_BAR_UPDATE", "PLAYER_SPECIALIZATION_CHANGED" }) do
    FT.On(event, function(name, unit)
        if name == "PLAYER_SPECIALIZATION_CHANGED" and FT.Value(unit, "string") ~= "player" then
            return
        end
        revision = revision + 1
        scheduleScan(name)
    end)
end

FT.On("LEARNED_SPELL_IN_SKILL_LINE", function(event, rawID, rawLine, rawGuild)
    if not enabled() then
        return
    end
    local id = contentID(rawID)
    if id then
        local related = FT.Emit("spell.learned", {
            spell_id = id, skill_line_index = integer(rawLine, 1, 100000), is_guild_perk = FT.Value(rawGuild, "boolean"),
        }, event, "direct_event")
        FT.RequestSpell(id, related)
    end
    revision = revision + 1
    scheduleScan(event)
end)

for _, event in ipairs({ "SPELL_DATA_LOAD_RESULT", "SPELL_TEXT_UPDATE" }) do
    FT.On(event, function(name, rawID, rawSuccess)
        if not enabled() then
            return
        end
        local id = contentID(rawID)
        if not id or (name == "SPELL_DATA_LOAD_RESULT" and FT.Value(rawSuccess, "boolean") ~= true) then
            return
        end
        local request = pending[id]
        if request then
            request.next_at = FT.Now()
            FT.Schedule("spells.metadata", 0.05, metadataWork)
        elseif cache[id] and FT.Now() - cache[id].refreshed_at >= 1 then
            enqueue(id, nil, true)
        end
    end)
end

FT.OnReset(function(reason)
    generation   = generation + 1
    revision     = revision + 1
    scan         = nil
    scheduled    = nil
    if reason == "zone_change" or reason == "world_transition" then
        if previous then
            previous.comparable = false
        end
        for _, request in pairs(pending) do
            request.generation = generation
        end
        if enabled() and pendingCount > 0 then
            FT.Schedule("spells.metadata", 0.05, metadataWork)
        end
        return
    end
    pending      = {}
    queue        = {}
    cache        = {}
    pendingCount = 0
    cacheCount   = 0
    previous     = nil
    lastStatus   = "not_observed"
    lastCount    = 0
    droppedCount = 0
end)
