local addonName, FT = ...
local frame        = CreateFrame("Frame")
local elapsed      = 0

frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", function(self, event, ...)
    if event == "ADDON_LOADED" then
        local name = ...
        if name == addonName and FT.Initialize(ForeverTomeDB) then
            FT.Register(self)
            self:UnregisterEvent("ADDON_LOADED")
            FT.Print("Recording ready. /ft status shows coverage; /reload saves observations to disk.")
        end
        return
    end
    if event == "PLAYER_ENTERING_WORLD" then
        FT.InWorld = true
    end
    FT.Dispatch(event, ...)
end)

frame:SetScript("OnUpdate", function(_, delta)
    elapsed = elapsed + delta
    if elapsed >= 0.1 then
        elapsed = 0
        FT.Tick()
    end
end)

SLASH_FOREVERTOME1 = "/ft"
SLASH_FOREVERTOME2 = "/forevertome"
SlashCmdList.FOREVERTOME = function(message)
    message = string.lower(string.match(message or "", "^%s*(.-)%s*$"))
    if message == "pause" or message == "resume" then
        FT.Pause(message == "pause")
    elseif message == "clear confirm" then
        if FT.Clear() then
            FT.Print("Local history cleared. Save again with /reload after recording.")
            FT.Dispatch("FT_BASELINE")
        end
        return
    elseif message == "clear" then
        FT.Print("After exporting your saved file, /ft clear confirm permanently clears local history.")
        return
    elseif message == "save" or message == "export" then
        FT.Print("Use /reload or log out to save. Run tools/export_saved_variables.py on WTF/Account/<account>/SavedVariables/ForeverTome.lua.")
        return
    elseif message ~= "" and message ~= "status" then
        FT.Print("Commands: status, pause, resume, save, export, clear.")
        return
    end
    local status = FT.Status()
    local state  = status.blocked or (status.paused and "paused" or "recording")
    FT.Print(string.format("%s | %d observations | %d sessions | about %.1f MiB | %s",
        state, status.records, status.sessions, status.estimated_bytes / 1048576, status.adapter_id or "unknown"))
end
