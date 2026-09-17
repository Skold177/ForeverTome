local Host     = dofile("tests/support/host.lua")
local passed   = 0
local failed   = 0
local required = { "core", "quests", "loot", "world", "spells", "talents" }

for _, name in ipairs(required) do
    local ok, suite = pcall(dofile, "tests/" .. name .. ".lua")
    if not ok or type(suite) ~= "table" or #suite == 0 then
        error("Required suite missing/empty: " .. name .. " " .. tostring(suite))
    end
    for _, test in ipairs(suite) do
        assert(type(test.name) == "string" and type(test.run) == "function", "invalid test entry")
        local success, reason = pcall(test.run, Host)
        if success then
            passed = passed + 1
            io.write("PASS " .. name .. ": " .. test.name .. "\n")
        else
            failed = failed + 1
            io.write("FAIL " .. name .. ": " .. test.name .. "\n" .. tostring(reason) .. "\n")
        end
    end
end

assert(passed + failed >= 20, "Test discovery unexpectedly decreased")
io.write(string.format("%d passed; %d failed\n", passed, failed))
if failed > 0 then
    os.exit(1)
end
