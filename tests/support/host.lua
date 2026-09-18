local Host = {}

local function equal(left, right, path)
    path = path or "value"
    assert(type(left) == type(right), path .. ": type differs (" .. type(left) .. " / " .. type(right) .. ")")
    if type(left) ~= "table" then
        assert(left == right, path .. ": " .. tostring(left) .. " ~= " .. tostring(right))
        return
    end
    for key, value in pairs(left) do
        equal(value, right[key], path .. "." .. tostring(key))
    end
    for key in pairs(right) do
        assert(left[key] ~= nil, path .. ": missing " .. tostring(key))
    end
end

function Host.new(saved, version, build, configure)
    local h = { FT = {}, state = { time = 100, map = 42, x = 0.45, y = 0.62 }, frames = {}, messages = {}, metadata = {} }
    local e = {
        assert = assert, error = error, ipairs = ipairs, pairs = pairs, next = next,
        pcall = pcall, select = select, tonumber = tonumber, tostring = tostring, type = type,
        unpack = unpack, getmetatable = getmetatable, setmetatable = setmetatable,
        math = math, string = string, table = table, SlashCmdList = {},
        WOW_PROJECT_ID = 99, ForeverTomeDB = saved,
        C_AddOns = {}, C_EventUtils = {}, C_Map = {}, C_QuestLog = {}, C_Item = {}, C_Container = {},
        C_CreatureInfo = {}, C_Spell = {}, C_TradeSkillUI = {}, C_MerchantFrame = {}, C_GossipInfo = {},
    }
    h.env = e
    e._G  = e
    e.C_AddOns.GetAddOnMetadata = function(name, field)
        assert(name == "ForeverTome", "metadata requested for unrelated addon")
        return h.metadata[field]
    end
    e.GetAddOnMetadata = e.C_AddOns.GetAddOnMetadata
    e.GetTime = function()
        return h.state.time
    end
    e.GetServerTime = function()
        return 1800000000 + math.floor(h.state.time)
    end
    e.GetBuildInfo = function()
        return version or "1.60.1", build or "69893", "Sep 17 2026", 16001
    end
    e.GetLocale = function()
        return "enUS"
    end
    e.UnitName = function(token)
        if token == "player" then
            return "Syntheticplayer"
        end
    end
    e.issecretvalue = function(value)
        return type(value) == "table" and rawget(value, "secret") == true
    end
    e.canaccessvalue = function(value)
        return not e.issecretvalue(value)
    end
    e.C_EventUtils.IsEventValid = function(event)
        assert(event ~= "COMBAT_LOG_EVENT_UNFILTERED", "restricted combat event registered")
        assert(not event:match("^FT_"), "internal event registered with client")
        return true
    end
    e.C_Map.GetBestMapForUnit = function(token)
        assert(token == "player", "NPC queried through player-only map API")
        return h.state.map
    end
    e.C_Map.GetPlayerMapPosition = function()
        if h.state.x == nil then
            return nil
        end
        return { GetXY = function()
            return h.state.x, h.state.y
        end }
    end
    e.C_Map.GetMapInfo = function()
        return { name = "Synthetic map", parentMapID = 1 }
    end
    e.GetZoneText = function()
        return "Synthetic zone"
    end
    e.GetSubZoneText = function()
        return "Synthetic subzone"
    end
    e.C_QuestLog.GetNumQuestLogEntries = function()
        return 0, 0
    end
    e.C_Container.GetContainerNumSlots = function()
        return 0
    end
    e.GetNumLootItems = function()
        return 0
    end
    e.DEFAULT_CHAT_FRAME = { AddMessage = function(_, message)
        table.insert(h.messages, message)
    end }
    e.CreateFrame = function()
        local frame = { registered = {}, scripts = {} }
        function frame:RegisterEvent(event)
            self.registered[event] = true
        end
        function frame:UnregisterEvent(event)
            self.registered[event] = nil
        end
        function frame:SetScript(name, callback)
            self.scripts[name] = callback
        end
        table.insert(h.frames, frame)
        return frame
    end
    if configure then
        configure(e)
    end
    for line in io.lines("ForeverTome/ForeverTome.toc") do
        local field, value = line:match("^## ([%w_]+):%s*(.-)%s*$")
        if field then
            h.metadata[field] = value
        end
        local file = line:match("^([%w_]+%.lua)%s*$")
        if file then
            local chunk = assert(loadfile("ForeverTome/" .. file))
            setfenv(chunk, e)
            chunk("ForeverTome", h.FT)
        end
    end
    function h:start()
        self:event("ADDON_LOADED", "UnrelatedAddon")
        assert(not self.FT.Status().initialized)
        self:event("ADDON_LOADED", "ForeverTome")
        self:event("PLAYER_LOGIN")
        self:event("PLAYER_ENTERING_WORLD", true, false)
        self:advance(0.5)
    end
    function h:event(name, ...)
        for _, frame in ipairs(self.frames) do
            if frame.registered[name] then
                frame.scripts.OnEvent(frame, name, ...)
            end
        end
    end
    function h:advance(seconds)
        local finish = self.state.time + seconds
        while self.state.time + 0.000001 < finish do
            local delta = math.min(0.1, finish - self.state.time)
            self.state.time = self.state.time + delta
            for _, frame in ipairs(self.frames) do
                if frame.scripts.OnUpdate then
                    frame.scripts.OnUpdate(frame, delta)
                end
            end
        end
    end
    function h:records(kind)
        local records = {}
        local savedDB = self.FT.Export()
        for _, session in ipairs(savedDB and savedDB.sessions or {}) do
            for _, record in ipairs(session.observations) do
                if not kind or record.kind == kind then
                    table.insert(records, record)
                end
            end
        end
        return records
    end
    function h:last(kind)
        local records = self:records(kind)
        return records[#records]
    end
    function h:assertEqual(actual, expected, message)
        equal(actual, expected, message)
    end
    function h:assertTrue(value, message)
        assert(value, message or "expected true")
    end
    function h:assertHealthy()
        local db = self.FT.Export()
        for _, entry in ipairs(db and db.sessions or {}) do
            for key in pairs(entry.diagnostics.counts) do
                assert(not key:match("^collector_error:"), "swallowed collector failure: " .. key)
            end
        end
    end
    return h
end

Host.equal = equal
return Host
