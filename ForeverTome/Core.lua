local addonName, FT = ...

FT.VERSION = "unknown"
FT.SCHEMA  = 1
FT.LIMITS  = {
    records = 60000, bytes = 48 * 1024 * 1024, sessions = 512,
    record_bytes = 256 * 1024, string_bytes = 65536, nodes = 12000,
    tasks = 128, diagnostics = 64,
    session_bytes = 32768,
}

local recordKinds      = {}
local internalCaptures = { FT_BASELINE = "baseline_refresh", FT_CATALOG = "manual_catalog" }
for kind in string.gmatch([[
session.started session.ended coverage.gap player.snapshot player.state unit.sighting
world.context world.transition location.sample merchant.opened merchant.offer merchant.closed
spell.metadata spell.succeeded profession.snapshot recipe.learned recipe.metadata craft.result
spell.metadata_unavailable spell.learned spellbook.snapshot spellbook.scan spellbook.changed
talent.metadata talent.rank talent.build talent.snapshot
quest.baseline quest.metadata_unavailable quest.snapshot quest.objective_delta quest.ready
quest.log_scope quest.dialogue quest.accepted quest.turned_in quest.removed quest.metadata quest.reward_received
interaction.snapshot item.metadata_unresolved item.metadata item.received loot.visible loot.opened
loot.snapshot loot.slot_unavailable loot.slot_cleared loot.closed inventory.snapshot inventory.delta
]], "%S+") do
    recordKinds[kind] = true
end

local handlers  = {}
local resets    = {}
local scheduled = {}
local context    = 0
local generation = 0
local started   = 0
local previous  = 0
local database
local active

function FT.Readable(value)
    if type(issecretvalue) == "function" then
        local ok, secret = pcall(issecretvalue, value)
        if not ok or secret then
            return false
        end
    end
    if type(canaccessvalue) == "function" then
        local ok, accessible = pcall(canaccessvalue, value)
        if not ok or not accessible then
            return false
        end
    end
    return true
end

function FT.Value(value, expected)
    if not FT.Readable(value) or type(value) ~= expected then
        return nil
    end
    if expected == "number" and (value ~= value or value == math.huge or value == -math.huge) then
        return nil
    end
    if expected == "string" and #value > FT.LIMITS.string_bytes then
        return nil
    end
    return value
end

function FT.Field(source, key, expected)
    if not FT.Value(source, "table") then
        return nil
    end
    local ok, value = pcall(function()
        return source[key]
    end)
    if ok then
        return FT.Value(value, expected)
    end
end

function FT.Length(source)
    if not FT.Value(source, "table") then
        return nil
    end
    local ok, length = pcall(function()
        return #source
    end)
    if ok then
        return FT.Value(length, "number")
    end
end

function FT.Resolve(path)
    local current = _G
    for part in string.gmatch(path, "[^.]+") do
        if not FT.Readable(current) or type(current) ~= "table" then
            return nil
        end
        current = current[part]
    end
    if FT.Readable(current) and type(current) == "function" then
        return current
    end
end

for _, path in ipairs({ "C_AddOns.GetAddOnMetadata", "GetAddOnMetadata" }) do
    local metadata = FT.Resolve(path)
    if metadata then
        local ok, version = pcall(metadata, addonName, "Version")
        if ok and FT.Value(version, "string") and version ~= "" then
            FT.VERSION = version
            break
        end
    end
end

local function pack(...)
    return { n = select("#", ...), ... }
end

function FT.TryCall(path, ...)
    local fn = FT.Resolve(path)
    if not fn then
        return false
    end
    local result = pack(pcall(fn, ...))
    if not result[1] then
        FT.Diagnostic("api_error", path)
        return false
    end
    for index = 2, result.n do
        if not FT.Readable(result[index]) then
            FT.Diagnostic("restricted", path)
            return false
        end
    end
    return unpack(result, 1, result.n)
end

function FT.Equal(left, right)
    if type(left) ~= type(right) then
        return false
    end
    if type(left) ~= "table" then
        return left == right
    end
    for key, value in pairs(left) do
        if not FT.Equal(value, right[key]) then
            return false
        end
    end
    for key in pairs(right) do
        if left[key] == nil then
            return false
        end
    end
    return true
end

function FT.Call(path, ...)
    local fn = FT.Resolve(path)
    if not fn then
        return nil
    end
    local result = pack(pcall(fn, ...))
    if not result[1] then
        FT.Diagnostic("api_error", path)
        return nil
    end
    for index = 2, result.n do
        if not FT.Readable(result[index]) then
            FT.Diagnostic("restricted", path)
            result[index] = nil
        end
    end
    return unpack(result, 2, result.n)
end

function FT.Now()
    local clock = started
    if type(GetTime) == "function" then
        local ok, value = pcall(GetTime)
        if ok then
            clock = FT.Value(value, "number") or started
        end
    end
    previous = math.max(previous, clock - started, 0)
    return previous
end

local function copyPlain(value, state, depth)
    if not FT.Readable(value) then
        error("restricted value")
    end
    local kind = type(value)
    state.nodes = state.nodes + 1
    if state.nodes > state.max_nodes or depth > 16 then
        error("data complexity limit")
    end
    if kind == "string" then
        if #value > FT.LIMITS.string_bytes then
            error("string limit")
        end
        state.bytes = state.bytes + #value + 16
    elseif kind == "number" then
        if not FT.Value(value, "number") then
            error("invalid number")
        end
        state.bytes = state.bytes + 24
    elseif kind == "boolean" or kind == "nil" then
        state.bytes = state.bytes + 8
    elseif kind == "table" then
        if getmetatable(value) ~= nil or state.seen[value] then
            error("non-plain or cyclic table")
        end
        state.seen[value] = true
        state.bytes       = state.bytes + 40
        local result = {}
        for key, child in pairs(value) do
            if not FT.Readable(key) then
                error("restricted key")
            end
            if type(key) ~= "string" and (type(key) ~= "number" or key < 1 or key % 1 ~= 0) then
                error("unsupported key")
            end
            if type(key) == "string" then
                if #key > 128 then
                    error("key limit")
                end
                state.bytes = state.bytes + #key + 16
            end
            result[key] = copyPlain(child, state, depth + 1)
        end
        state.seen[value] = nil
        if state.bytes > state.max_bytes then
            error("data size limit")
        end
        return result
    else
        error("unsupported value")
    end
    if state.bytes > state.max_bytes then
        error("data size limit")
    end
    return value
end

function FT.Copy(value, maxBytes, maxNodes)
    local state = {
        seen = {}, nodes = 0, bytes = 0,
        max_bytes = maxBytes or FT.LIMITS.record_bytes,
        max_nodes = maxNodes or FT.LIMITS.nodes,
    }
    local ok, result = pcall(copyPlain, value, state, 0)
    if not ok then
        return nil, "invalid_plain_data"
    end
    return result, state.bytes
end

function FT.Print(message)
    if DEFAULT_CHAT_FRAME and DEFAULT_CHAT_FRAME.AddMessage then
        DEFAULT_CHAT_FRAME:AddMessage("|cffd5b66cForeverTome:|r " .. message)
    end
end

function FT.Diagnostic(code, detail)
    local health = active and active.diagnostics
    if not health then
        return
    end
    detail = FT.Value(detail, "string") or ""
    local key = code .. ":" .. string.sub(detail, 1, 100)
    if not health.counts[key] and health.distinct >= FT.LIMITS.diagnostics then
        key = "other"
    elseif not health.counts[key] then
        health.distinct = health.distinct + 1
    end
    health.counts[key] = (health.counts[key] or 0) + 1
    health.last_at_s   = FT.Now()
end

function FT.On(event, callback)
    handlers[event] = handlers[event] or {}
    table.insert(handlers[event], callback)
end

function FT.OnReset(callback)
    table.insert(resets, callback)
end

function FT.ResetCollectors(reason)
    generation = generation + 1
    scheduled  = {}
    for _, callback in ipairs(resets) do
        local ok = pcall(callback, reason)
        if not ok then
            FT.Diagnostic("collector_error", "reset")
        end
    end
    if (reason == "collector_error" or reason == "invalid_record") and FT.InWorld then
        FT.Schedule("core.recovery", 0.5, function()
            FT.Emit("coverage.gap", { reason = reason, baseline_required = true }, { method = "collector_recovery" })
            FT.Dispatch("FT_BASELINE")
        end)
    end
end

function FT.NewContext(prefix)
    context = context + 1
    return (active and active.session.session_id or "uninitialized") .. ":" .. prefix .. ":" .. context
end

function FT.Schedule(key, delay, callback)
    if not active or database.settings.paused or FT.Blocked then
        return
    end
    if scheduled[key] then
        return
    end
    local count = 0
    for _ in pairs(scheduled) do
        count = count + 1
    end
    if count >= FT.LIMITS.tasks then
        FT.Diagnostic("capacity_limit", "tasks")
        return
    end
    scheduled[key] = { at = FT.Now() + delay, callback = callback, generation = generation }
end

function FT.Tick()
    if not active or FT.Blocked or database.settings.paused then
        return
    end
    local now   = FT.Now()
    local ready = {}
    for key, task in pairs(scheduled) do
        if task.at <= now then
            ready[#ready + 1] = { key = key, task = task }
            if #ready >= 4 then
                break
            end
        end
    end
    for _, entry in ipairs(ready) do
        if FT.Blocked or database.settings.paused then
            return
        end
        local key  = entry.key
        local task = entry.task
        if scheduled[key] == task and task.generation == generation then
            scheduled[key] = nil
            local ok = pcall(task.callback)
            if not ok then
                FT.Diagnostic("collector_error", key)
                FT.ResetCollectors("collector_error")
                return
            end
        end
    end
end

function FT.Emit(kind, data, capture, evidence, related, missing)
    if not active or FT.Blocked or database.settings.paused then
        return nil
    end
    if type(kind) ~= "string" or not string.match(kind, "^[a-z_]+%.[a-z_]+$") then
        FT.Diagnostic("invalid_record", "kind")
        return nil
    end
    if type(capture) == "string" and internalCaptures[capture] then
        capture = { method = internalCaptures[capture] }
    elseif type(capture) == "table" and internalCaptures[capture.event] then
        local method = internalCaptures[capture.event]
        capture = FT.Copy(capture)
        capture.event  = nil
        capture.method = method
    end
    local elapsed = FT.Now()
    local record  = {
        session_id = active.session.session_id,
        sequence = #active.observations + 1,
        kind = kind,
        observed_at_server_s = FT.Value(FT.Call("GetServerTime"), "number"),
        elapsed_s = elapsed,
        capture = type(capture) == "table" and capture or { event = capture, sampled_elapsed_s = elapsed },
        location = FT.Location and FT.Location() or nil,
        data = data or {},
        evidence = { method = evidence or "api_snapshot" },
        related_observation_ids = related or {},
        missing_fields = missing or {},
    }
    record.observation_id = record.session_id .. ":" .. record.sequence
    local owned, bytes = FT.Copy(record)
    if not owned then
        FT.Diagnostic("invalid_record", kind)
        FT.ResetCollectors("invalid_record")
        return nil
    end
    if database.record_count >= FT.LIMITS.records or database.estimated_bytes + bytes > FT.LIMITS.bytes then
        FT.Blocked = "capacity_limit"
        FT.Diagnostic("capacity_limit", "observations")
        FT.Print("Storage is full; recording stopped. Save with /reload, export, then use /ft clear confirm.")
        FT.ResetCollectors("capacity_limit")
        return nil
    end
    active.observations[#active.observations + 1] = owned
    database.record_count    = database.record_count + 1
    database.estimated_bytes = database.estimated_bytes + bytes
    return owned.observation_id
end

local function validInteger(value)
    return type(value) == "number" and value >= 0 and value % 1 == 0 and value < 9007199254740991
end

local function denseArray(value)
    if type(value) ~= "table" or getmetatable(value) ~= nil then
        return false
    end
    local count = 0
    for key in pairs(value) do
        if not validInteger(key) or key < 1 then
            return false
        end
        count = count + 1
    end
    return count == #value
end

local function nonnegativeNumber(value)
    return type(value) == "number" and value >= 0 and value < math.huge
end

local function stringMap(value)
    if type(value) ~= "table" or getmetatable(value) ~= nil then
        return false
    end
    for key in pairs(value) do
        if type(key) ~= "string" then
            return false
        end
    end
    return true
end

local function validLocation(location)
    if location == nil then
        return true
    end
    if not stringMap(location) or (location.status ~= "available" and location.status ~= "unavailable") then
        return false
    end
    if location.ui_map_id ~= nil and (not validInteger(location.ui_map_id) or location.ui_map_id < 1) then
        return false
    end
    if location.sampled_elapsed_s ~= nil and not nonnegativeNumber(location.sampled_elapsed_s) then
        return false
    end
    if location.status == "available" then
        return location.subject == "player" and location.coordinate_system == "ui_map_normalized"
            and validInteger(location.ui_map_id) and location.ui_map_id > 0
            and nonnegativeNumber(location.x) and location.x <= 1
            and nonnegativeNumber(location.y) and location.y <= 1
    end
    return type(location.reason) == "string" and location.x == nil and location.y == nil
end

local function validObservation(observation, previousElapsed)
    if not recordKinds[observation.kind] or not nonnegativeNumber(observation.elapsed_s)
        or observation.elapsed_s < previousElapsed or not stringMap(observation.data)
        or not stringMap(observation.capture) or not stringMap(observation.evidence)
        or not stringMap(observation.missing_fields) or not denseArray(observation.related_observation_ids)
        or type(observation.evidence.method) ~= "string" or observation.evidence.method == ""
        or not validLocation(observation.location) then
        return false
    end
    if observation.observed_at_server_s ~= nil and not nonnegativeNumber(observation.observed_at_server_s) then
        return false
    end
    for _, key in ipairs({ "event", "method", "api" }) do
        if observation.capture[key] ~= nil and type(observation.capture[key]) ~= "string" then
            return false
        end
    end
    for _, key in ipairs({ "sampled_elapsed_s", "trigger_elapsed_s" }) do
        if observation.capture[key] ~= nil and not nonnegativeNumber(observation.capture[key]) then
            return false
        end
    end
    for _, reason in pairs(observation.missing_fields) do
        if type(reason) ~= "string" then
            return false
        end
    end
    for _, reference in ipairs(observation.related_observation_ids) do
        if type(reference) ~= "string" then
            return false
        end
    end
    return true
end

local function validateStore(candidate)
    if type(candidate) ~= "table" or getmetatable(candidate) ~= nil or candidate.schema_version ~= FT.SCHEMA then
        return false
    end
    local allowed = {
        schema_version = true, synthetic = true, installation_id = true, next_session = true,
        settings = true, sessions = true, record_count = true, estimated_bytes = true,
    }
    for key in pairs(candidate) do
        if not allowed[key] then
            return false
        end
    end
    if type(candidate.synthetic) ~= "boolean" or type(candidate.installation_id) ~= "string"
        or #candidate.installation_id ~= 32 or not string.match(candidate.installation_id, "^[a-f0-9]+$") then
        return false
    end
    if not validInteger(candidate.next_session) or not denseArray(candidate.sessions) or #candidate.sessions > FT.LIMITS.sessions then
        return false
    end
    if type(candidate.settings) ~= "table" or type(candidate.settings.paused) ~= "boolean" then
        return false
    end
    for key in pairs(candidate.settings) do
        if key ~= "paused" then
            return false
        end
    end
    local ids            = {}
    local observationIDs = {}
    local count          = 0
    local bytes          = #candidate.sessions * FT.LIMITS.session_bytes
    for _, entry in ipairs(candidate.sessions) do
        if type(entry) ~= "table" or type(entry.session) ~= "table" or not denseArray(entry.observations)
            or type(entry.diagnostics) ~= "table" then
            return false
        end
        local id = entry.session.session_id
        if type(id) ~= "string" or ids[id] then
            return false
        end
        local serial = tonumber(string.match(id, "^" .. candidate.installation_id .. "%-(%d+)$"))
        if not validInteger(serial) or serial < 1 or serial > candidate.next_session then
            return false
        end
        for key in pairs(entry) do
            if key ~= "session" and key ~= "observations" and key ~= "diagnostics" then
                return false
            end
        end
        local header = entry.session
        if not stringMap(header) or not stringMap(header.client) or not stringMap(header.capabilities) then
            return false
        end
        for _, key in ipairs({ "product", "addon_version", "adapter_id" }) do
            if type(header[key]) ~= "string" or header[key] == "" then
                return false
            end
        end
        for _, key in ipairs({ "version", "build", "locale" }) do
            if type(header.client[key]) ~= "string" or header.client[key] == "" then
                return false
            end
        end
        for _, key in ipairs({ "interface_version", "project_id" }) do
            if header.client[key] ~= nil and not validInteger(header.client[key]) then
                return false
            end
        end
        if header.started_at_server_s ~= nil and not nonnegativeNumber(header.started_at_server_s) then
            return false
        end
        for _, capability in pairs(header.capabilities) do
            if not stringMap(capability) or type(capability.status) ~= "string" or type(capability.enabled) ~= "boolean" then
                return false
            end
        end
        if type(entry.diagnostics.counts) ~= "table" or not validInteger(entry.diagnostics.distinct) then
            return false
        end
        local diagnosticCount = 0
        for key, value in pairs(entry.diagnostics.counts) do
            if type(key) ~= "string" or not validInteger(value) then
                return false
            end
            diagnosticCount = diagnosticCount + 1
        end
        if diagnosticCount > FT.LIMITS.diagnostics + 1 or not FT.Copy(header, 8192)
            or not FT.Copy(entry.diagnostics, FT.LIMITS.session_bytes - 8192) then
            return false
        end
        ids[id] = true
        local previousElapsed = 0
        for index, observation in ipairs(entry.observations) do
            if type(observation) ~= "table" or observation.session_id ~= id or observation.sequence ~= index
                or observation.observation_id ~= id .. ":" .. index or type(observation.kind) ~= "string"
                or type(observation.data) ~= "table" or type(observation.capture) ~= "table"
                or type(observation.evidence) ~= "table" or type(observation.missing_fields) ~= "table"
                or type(observation.related_observation_ids) ~= "table" then
                return false
            end
            if not validObservation(observation, previousElapsed) then
                return false
            end
            local owned, size = FT.Copy(observation)
            if not owned then
                return false
            end
            count = count + 1
            bytes = bytes + size
            previousElapsed = observation.elapsed_s
            observationIDs[observation.observation_id] = true
            if count > FT.LIMITS.records or bytes > FT.LIMITS.bytes then
                return false
            end
        end
    end
    if count > FT.LIMITS.records or bytes > FT.LIMITS.bytes then
        return false
    end
    for _, entry in ipairs(candidate.sessions) do
        for _, observation in ipairs(entry.observations) do
            for _, reference in ipairs(observation.related_observation_ids) do
                if not observationIDs[reference] then
                    return false
                end
            end
        end
    end
    candidate.record_count    = count
    candidate.estimated_bytes = bytes
    return true
end

local function installationID()
    local parts = {}
    for index = 1, 8 do
        parts[index] = string.format("%04x", math.random(0, 65535))
    end
    return table.concat(parts, "")
end

function FT.Initialize(saved)
    if database then
        return false
    end
    if saved ~= nil then
        local ok, valid = pcall(validateStore, saved)
        if not ok or not valid then
            FT.Blocked = "unsupported_or_invalid_saved_data"
            FT.Print("Saved data could not be validated. It was preserved; recording is disabled.")
            return false
        end
        database = saved
    else
        database = {
            schema_version = FT.SCHEMA, synthetic = false,
            installation_id = installationID(), next_session = 0,
            settings = { paused = false }, sessions = {}, record_count = 0, estimated_bytes = 0,
        }
    end
    ForeverTomeDB = database
    if #database.sessions >= FT.LIMITS.sessions or database.estimated_bytes + FT.LIMITS.session_bytes > FT.LIMITS.bytes then
        FT.Blocked = "session_capacity"
        FT.Print("Session limit reached. Export saved data before clearing it.")
        return false
    end
    started  = FT.Value(FT.Call("GetTime"), "number") or 0
    previous = 0
    database.next_session = database.next_session + 1
    local client  = FT.ClientIdentity()
    local header  = {
        session_id = database.installation_id .. "-" .. database.next_session,
        product = FT.Profile.product,
        client = client, addon_version = FT.VERSION, adapter_id = FT.Profile.id,
        capabilities = FT.Copy(FT.Profile.capabilities),
        started_at_server_s = FT.Value(FT.Call("GetServerTime"), "number"),
        previous_session_end = #database.sessions > 0 and "unknown_until_saved" or "not_applicable",
    }
    active = { session = header, observations = {}, diagnostics = { counts = {}, distinct = 0 } }
    table.insert(database.sessions, active)
    database.estimated_bytes = database.estimated_bytes + FT.LIMITS.session_bytes
    FT.Emit("session.started", { recording = not database.settings.paused }, { method = "addon_initialization" })
    if not FT.Profile.supported then
        FT.Diagnostic("unsupported", "client_profile")
        FT.Print("Client profile is unknown. Only lifecycle observations will be recorded.")
    end
    return true
end

function FT.Status()
    return {
        initialized = active ~= nil, blocked = FT.Blocked,
        paused = database and database.settings.paused or false,
        records = database and database.record_count or 0,
        estimated_bytes = database and database.estimated_bytes or 0,
        sessions = database and #database.sessions or 0,
        session_id = active and active.session.session_id,
        adapter_id = FT.Profile and FT.Profile.id,
    }
end

function FT.Export()
    if not database then
        return nil, "not_initialized"
    end
    return FT.Copy(database, FT.LIMITS.bytes * 2, FT.LIMITS.records * 200)
end

function FT.Pause(paused)
    if not database or not active or FT.Blocked then
        return
    end
    if database.settings.paused == paused then
        return
    end
    if paused then
        FT.Emit("coverage.gap", { reason = "user_pause", boundary = "start" }, { method = "user_command" })
    end
    database.settings.paused = paused
    FT.ResetCollectors(paused and "pause" or "resume")
    FT.Diagnostic("coverage_gap", paused and "pause" or "resume")
    if not paused then
        FT.Emit("coverage.gap", { reason = "user_pause", boundary = "end", baseline_required = true }, { method = "user_command" })
        if FT.InWorld then
            FT.Dispatch("FT_BASELINE")
        end
    end
end

function FT.Clear()
    if not database then
        return false
    end
    local identity = database.installation_id
    local serial   = database.next_session
    FT.ResetCollectors("user_clear")
    database = nil
    active   = nil
    FT.Blocked = nil
    return FT.Initialize({
        schema_version = FT.SCHEMA, synthetic = false, installation_id = identity,
        next_session = serial, settings = { paused = false }, sessions = {},
    })
end

function FT.Dispatch(event, ...)
    if not active then
        return
    end
    if database.settings.paused and event ~= "PLAYER_LOGOUT" and event ~= "PLAYER_LEAVING_WORLD" then
        return
    end
    for _, callback in ipairs(handlers[event] or {}) do
        local ok = pcall(callback, event, ...)
        if not ok then
            FT.Diagnostic("collector_error", event)
            FT.ResetCollectors("collector_error")
        end
    end
end

function FT.Register(frame)
    for event in pairs(handlers) do
        if not string.match(event, "^FT_") and (FT.Profile.supported or string.match(event, "^PLAYER_") and
            (event == "PLAYER_LOGIN" or event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_LEAVING_WORLD" or event == "PLAYER_LOGOUT")) then
            local valid = FT.Call("C_EventUtils.IsEventValid", event)
            if valid ~= false then
                local ok = pcall(frame.RegisterEvent, frame, event)
                if not ok then
                    FT.Diagnostic("event_unavailable", event)
                end
            else
                FT.Diagnostic("event_unavailable", event)
            end
        end
    end
end
