local _, FT = ...

local professions = {
    herbalism = { 2366, 2368, 2369, 2371, 3570, 11993, 1235236 },
    mining = { 2575, 2576, 2577, 2578, 2579, 3564, 10248, 1235230 },
    skinning = { 8613, 8617, 8618, 10768 },
    fishing = { 7620, 7731, 7732, 18248 },
}
local spells  = {}
local pending = nil
local completed
for profession, ids in pairs(professions) do
    for _, id in ipairs(ids) do
        spells[id] = profession
    end
end

local function castIdentity(value)
    value = FT.Value(value, "string")
    if value and value ~= "" and #value <= 256 then
        return value
    end
end

local function begin(event, token, castGUID, spellID)
    spellID  = FT.Value(spellID, "number")
    castGUID = castIdentity(castGUID)
    if not FT.Profile.supported or not FT.InWorld or token ~= "player" or not spells[spellID] then
        return
    end
    if castGUID and completed and completed.guid == castGUID and completed.spell_id == spellID then
        return
    end
    if castGUID and pending and pending.guid == castGUID and pending.spell_id == spellID then
        return
    end
    local attempt = FT.NewContext("gathering")
    local id      = FT.Emit("gathering.attempt", {
        attempt_id = attempt, spell_id = spellID, profession = spells[spellID],
        actor = "player", outcome = "started", target_candidate = FT.Unit("target"),
        cast_identity_status = castGUID and "readable" or "unavailable",
        resource_identity = "not_observed", received_items = "not_attributed",
    }, event, "direct_event")
    pending = id and castGUID and { guid = castGUID, spell_id = spellID, id = attempt, source = id } or nil
end

local function finish(event, token, castGUID, spellID)
    spellID  = FT.Value(spellID, "number")
    castGUID = castIdentity(castGUID)
    if not FT.Profile.supported or not FT.InWorld or token ~= "player" or not spells[spellID] then
        return
    end
    if castGUID and completed and completed.guid == castGUID and completed.spell_id == spellID then
        return
    end
    local matched = castGUID and pending and pending.spell_id == spellID and pending.guid == castGUID
    FT.Emit("gathering.attempt", {
        attempt_id = matched and pending.id or FT.NewContext("gathering"),
        spell_id = spellID, profession = spells[spellID], actor = "player",
        start_match_status = matched and "matched" or "unavailable",
        outcome = event == "UNIT_SPELLCAST_INTERRUPTED" and "interrupted" or "failed",
        resource_identity = "not_observed", received_items = "not_attributed",
    }, event, "direct_event", matched and { pending.source } or nil)
    completed = castGUID and { guid = castGUID, spell_id = spellID } or nil
    if matched then
        pending = nil
    end
end

function FT.GatheringSucceeded(spellID, castGUID)
    spellID  = FT.Value(spellID, "number")
    castGUID = castIdentity(castGUID)
    if not spells[spellID] then
        return nil
    end
    completed = castGUID and { guid = castGUID, spell_id = spellID } or nil
    if castGUID and pending and pending.spell_id == spellID and pending.guid == castGUID then
        local attempt = pending
        pending = nil
        return attempt.id, { attempt.source }
    end
    return FT.NewContext("gathering"), {}
end

FT.On("UNIT_SPELLCAST_START", begin)
FT.On("UNIT_SPELLCAST_CHANNEL_START", begin)
FT.On("UNIT_SPELLCAST_FAILED", finish)
FT.On("UNIT_SPELLCAST_INTERRUPTED", finish)
FT.OnReset(function()
    pending   = nil
    completed = nil
end)
