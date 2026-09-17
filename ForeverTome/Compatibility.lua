local _, FT = ...

function FT.ClientIdentity()
    local version, build, buildDate, interface = FT.Call("GetBuildInfo")
    return {
        version = FT.Value(version, "string"), build = FT.Value(build, "string"),
        build_date = FT.Value(buildDate, "string"), interface_version = FT.Value(interface, "number"),
        project_id = FT.Value(WOW_PROJECT_ID, "number"), locale = FT.Value(FT.Call("GetLocale"), "string"),
    }
end

local client = FT.ClientIdentity()
local known  = client.version == "1.60.1" and client.build == "69893"

FT.Profile = {
    id = known and "forever-beta-69893-source-v1" or "unknown-client-v1",
    product = known and "WF" or "UNKNOWN", supported = known,
    quest_mode = known and "modern" or nil,
    quest_accepted_arg = 1, quest_turned_in = known, quest_removed = known, quest_loot_received = known,
    quest_dialogue = known, quest_rewards = known, quest_gossip = known, quest_data_load = known,
    loot_info = known and "modern" or nil, container_info = known and "modern" or nil,
    item_info = known and "modern" or nil, loot_source_pairs = false,
    spellbook = known and "modern" or nil, talents = known and "traits" or nil,
    capabilities = {
        quests = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        loot_visibility = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        item_metadata = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        units = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        location = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        world = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        spellbook = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        talents = { status = "wf_unverified", evidence = "installed_client_source", enabled = known },
        loot_source_mapping = { status = "unsupported", enabled = false, reason = "no_validated_contract" },
        combat_death_feed = { status = "restricted", enabled = false, reason = "secure_only_client_api" },
    },
}

FT.InWorld = false

function FT.ItemID(link)
    link = FT.Value(link, "string")
    if not link then
        return nil
    end
    local id = tonumber(string.match(link, "item:(%d+)"))
    if id and id > 0 and id % 1 == 0 then
        return id
    end
end

function FT.Location()
    local sample = {
        status = "unavailable", subject = "player", reason = "transition",
        sampled_elapsed_s = FT.Now(), method = "C_Map.GetPlayerMapPosition",
    }
    if not FT.InWorld or not FT.Profile.supported then
        sample.reason = FT.Profile.supported and "transition" or "unsupported"
        return sample
    end
    local map = FT.Value(FT.Call("C_Map.GetBestMapForUnit", "player"), "number")
    if not map then
        sample.reason = "no_map"
        return sample
    end
    if map <= 0 or map % 1 ~= 0 then
        sample.reason = "invalid_result"
        return sample
    end
    sample.ui_map_id = map
    local position = FT.Value(FT.Call("C_Map.GetPlayerMapPosition", map, "player"), "table")
    if not position then
        sample.reason = "no_position"
        return sample
    end
    local ok, x, y = pcall(function()
        return position:GetXY()
    end)
    x = FT.Value(x, "number")
    y = FT.Value(y, "number")
    if not ok or not x or not y or x < 0 or x > 1 or y < 0 or y > 1 then
        sample.reason = "invalid_result"
        return sample
    end
    if FT.Call("C_Map.GetBestMapForUnit", "player") ~= map then
        return sample
    end
    sample.status            = "available"
    sample.reason            = nil
    sample.coordinate_system = "ui_map_normalized"
    sample.x                 = x
    sample.y                 = y
    local info = FT.Call("C_Map.GetMapInfo", map)
    sample.map_name      = FT.Field(info, "name", "string")
    sample.parent_map_id = FT.Field(info, "parentMapID", "number")
    sample.zone         = FT.Value(FT.Call("GetZoneText"), "string")
    sample.subzone      = FT.Value(FT.Call("GetSubZoneText"), "string")
    return sample
end

function FT.Unit(token)
    token = FT.Value(token, "string")
    if not token or not FT.Profile.supported then
        return nil
    end
    local guid = FT.Value(FT.Call("UnitGUID", token), "string")
    if not guid then
        return nil
    end
    local kind = string.match(guid, "^([A-Za-z]+)%-")
    if kind ~= "Creature" and kind ~= "Vehicle" then
        return nil
    end
    local result = {
        guid = guid, entity_kind = kind, unit_token = token,
        creature_id = FT.Value(FT.Call("C_CreatureInfo.GetCreatureID", guid), "number"),
        name = FT.Value(FT.Call("UnitName", token), "string"),
        level = FT.Value(FT.Call("UnitLevel", token), "number"),
        classification = FT.Value(FT.Call("UnitClassification", token), "string"),
        creature_type = FT.Value(FT.Call("UnitCreatureType", token), "string"),
        creature_family = FT.Value(FT.Call("UnitCreatureFamily", token), "string"),
        dead = FT.Value(FT.Call("UnitIsDead", token), "boolean"),
        reaction = FT.Value(FT.Call("UnitReaction", token, "player"), "number"),
        max_health = FT.Value(FT.Call("UnitHealthMax", token), "number"),
        identity_method = "UnitGUID", creature_id_method = "C_CreatureInfo.GetCreatureID",
    }
    local x, y, z, map = FT.Call("UnitPosition", token)
    x   = FT.Value(x, "number")
    y   = FT.Value(y, "number")
    z   = FT.Value(z, "number")
    map = FT.Value(map, "number")
    if x and y and z and map then
        result.entity_position = {
            subject = guid, coordinate_system = "unit_position_native", method = "UnitPosition",
            x = x, y = y, z = z, map_id = map, sampled_elapsed_s = FT.Now(),
        }
    end
    if FT.Call("UnitGUID", token) ~= guid then
        return nil
    end
    return result
end
