return {
    { name = "capture and export independently own nested observations", run = function(Host)
        local h = Host.new()
        h:start()
        local data = { objectives = { { text = "Runes é中", count = 0, finished = false } } }
        local id   = h.FT.Emit("coverage.gap", data, "QUEST_LOG_UPDATE", "api_snapshot")
        data.objectives[1].text = "mutated"
        local first = h:last("coverage.gap")
        h:assertEqual(first.data.objectives[1], { text = "Runes é中", count = 0, finished = false })
        h:assertEqual(first.observation_id, id)
        local exported = h.FT.Export()
        exported.sessions[1].observations[#exported.sessions[1].observations].data.objectives[1].count = 999
        h:assertEqual(h:last("coverage.gap"), first)
        h:assertHealthy()
    end },
    { name = "rejects cycles metatables secrets nonfinite functions and oversized values", run = function(Host)
        local h = Host.new()
        h:start()
        local cycle = {}
        cycle.self  = cycle
        local invalid = {
            cycle, { fn = function()
                return nil
            end }, { nan = 0 / 0 }, { inf = math.huge },
            { secret = true }, setmetatable({}, {}), { text = string.rep("x", 65537) },
        }
        local before = h:records()
        for _, data in ipairs(invalid) do
            h:assertEqual(h.FT.Emit("coverage.gap", data, "QUEST_LOG_UPDATE"), nil)
        end
        h:assertEqual(h:records(), before)
        h:assertHealthy()
    end },
    { name = "reload preserves prefix and session IDs do not collide", run = function(Host)
        local h = Host.new()
        h:start()
        h:event("PLAYER_LOGOUT")
        local saved  = h.FT.Export()
        local prefix = saved.sessions[1]
        local second = Host.new(saved)
        second:start()
        local restored = second.FT.Export()
        Host.equal(restored.sessions[1], prefix)
        assert(restored.sessions[1].session.session_id ~= restored.sessions[2].session.session_id)
        for _, entry in ipairs(restored.sessions) do
            for index, record in ipairs(entry.observations) do
                assert(record.sequence == index)
                assert(record.observation_id == record.session_id .. ":" .. index)
            end
        end
        second:assertHealthy()
    end },
    { name = "future malformed sparse and reused IDs remain recoverable", run = function(Host)
        local h = Host.new()
        h:start()
        for _, mutate in ipairs({
            function(db)
                db.schema_version = 999
            end,
            function(db)
                db.next_session = 0
            end,
            function(db)
                db.sessions[1].observations[1] = nil
            end,
            function(db)
                db.sessions[1].observations[1].data.bad = math.huge
            end,
            function(db)
                db.synthetic = nil
            end,
            function(db)
                db.sessions[1].session.client = nil
            end,
            function(db)
                db.sessions[1].diagnostics.counts = "broken"
            end,
            function(db)
                db.extra = string.rep("x", 100000)
            end,
        }) do
            local saved = h.FT.Export()
            mutate(saved)
            local reader = Host.new(saved)
            reader:event("ADDON_LOADED", "ForeverTome")
            assert(reader.env.ForeverTomeDB == saved)
            assert(not reader.FT.Status().initialized)
            assert(reader.FT.Status().blocked == "unsupported_or_invalid_saved_data")
        end
    end },
    { name = "capacity stops visibly and never evicts committed history", run = function(Host)
        local h = Host.new()
        h:start()
        local before = h:records()
        h.FT.LIMITS.records = #before
        assert(not h.FT.Emit("coverage.gap", { reason = "test" }, "QUEST_LOG_UPDATE"))
        h:assertEqual(h:records(), before)
        assert(h.FT.Status().blocked == "capacity_limit")
        assert(h.FT.Export().sessions[1].diagnostics.counts["capacity_limit:observations"] == 1)
        assert(#h.messages >= 2)
    end },
    { name = "zero coordinates remain real and missing coordinates stay missing", run = function(Host)
        local h = Host.new()
        h:start()
        h.state.x = 0
        h.state.y = 0
        h.FT.Emit("coverage.gap", {}, "QUEST_LOG_UPDATE")
        h:assertEqual(h:last("coverage.gap").location.x, 0)
        h.state.x = nil
        h.FT.Emit("coverage.gap", {}, "QUEST_LOG_UPDATE")
        local location = h:last("coverage.gap").location
        assert(location.status == "unavailable" and location.reason == "no_position" and location.x == nil)
        h:assertHealthy()
    end },
    { name = "pause cancels callbacks and resumes with an explicit gap", run = function(Host)
        local h = Host.new()
        h:start()
        local called = false
        h.FT.Schedule("stale", 1, function()
            called = true
        end)
        h.FT.Pause(true)
        local count = #h:records()
        h:advance(2)
        h:event("PLAYER_DEAD")
        assert(#h:records() == count)
        h.FT.Pause(false)
        h:advance(1)
        assert(not called)
        assert(#h:records("coverage.gap") == 2)
        assert(h:last("world.context").capture.event == nil)
        h:assertHealthy()
    end },
    { name = "unsupported build does not register content capture", run = function(Host)
        local h = Host.new(nil, "1.60.2", "99999")
        h:start()
        h:event("QUEST_ACCEPTED", 501)
        h:event("LOOT_OPENED", true, false)
        assert(#h:records("quest.accepted") == 0 and #h:records("loot.opened") == 0)
        assert(h.FT.Export().sessions[1].session.product == "UNKNOWN")
        assert(not h.frames[1].registered.COMBAT_LOG_EVENT_UNFILTERED)
        h:assertHealthy()
    end },
    { name = "one failing collector cannot stop independent handlers", run = function(Host)
        local h = Host.new()
        h:start()
        local captured = false
        h.FT.On("TEST_EVENT", function()
            error("injected collector fault")
        end)
        h.FT.On("TEST_EVENT", function()
            captured = true
        end)
        h.FT.Dispatch("TEST_EVENT")
        assert(captured)
        assert(h.FT.Export().sessions[1].diagnostics.counts["collector_error:TEST_EVENT"] == 1)
    end },
    { name = "explicit clear retains serial identity and begins a new session", run = function(Host)
        local h = Host.new()
        h:start()
        local old = h.FT.Status().session_id
        assert(h.FT.Clear())
        assert(old ~= h.FT.Status().session_id)
        assert(#h.FT.Export().sessions == 1)
    end },
    { name = "restoration rejects invalid semantic fields without changing history", run = function(Host)
        local h = Host.new()
        h:start()
        for _, mutate in ipairs({
            function(db)
                db.sessions[1].observations[1].elapsed_s = -1
            end,
            function(db)
                db.sessions[1].observations[1].kind = "future.kind"
            end,
            function(db)
                db.sessions[1].observations[1].capture = { "not_a_map" }
            end,
            function(db)
                db.sessions[1].observations[1].capture.event = 123
            end,
            function(db)
                db.sessions[1].observations[1].evidence.method = false
            end,
            function(db)
                db.sessions[1].observations[1].related_observation_ids = { "missing" }
            end,
            function(db)
                db.sessions[1].observations[1].missing_fields.bad = 1
            end,
            function(db)
                db.sessions[1].observations[1].location = {
                    status = "available", subject = "player", coordinate_system = "ui_map_normalized",
                    ui_map_id = 0, x = 0.5, y = 0.5,
                }
            end,
            function(db)
                db.sessions[1].session.client.interface_version = "invalid"
            end,
            function(db)
                db.sessions[1].session.capabilities.quests = { "invalid" }
            end,
        }) do
            local saved = h.FT.Export()
            mutate(saved)
            local expected = assert(h.FT.Copy(saved, h.FT.LIMITS.bytes * 2, h.FT.LIMITS.records * 200))
            local reader   = Host.new(saved)
            reader:event("ADDON_LOADED", "ForeverTome")
            assert(not reader.FT.Status().initialized)
            assert(reader.FT.Status().blocked == "unsupported_or_invalid_saved_data")
            Host.equal(saved, expected)
        end
    end },
    { name = "transient failure restarts passive sampling with a labeled baseline", run = function(Host)
        local h = Host.new()
        h:start()
        h.FT.On("FAULT", function()
            error("transient failure")
        end)
        h.FT.Dispatch("FAULT")
        h:advance(6)
        assert(#h:records("location.sample") >= 1)
        local gap = h:last("coverage.gap")
        assert(gap.data.reason == "collector_error" and gap.capture.method == "collector_recovery")
        assert(h:last("world.context").capture.event == nil)
    end },
    { name = "reserved session bytes participate in restore capacity", run = function(Host)
        local h = Host.new()
        h:start()
        local saved  = h.FT.Export()
        local reader = Host.new(saved)
        reader.FT.LIMITS.bytes = saved.estimated_bytes - 1
        reader:event("ADDON_LOADED", "ForeverTome")
        assert(not reader.FT.Status().initialized)
        assert(reader.env.ForeverTomeDB == saved)
    end },
    { name = "scheduler callbacks defer newly queued work until the next tick", run = function(Host)
        local h = Host.new()
        h:start()
        h.FT.ResetCollectors("test_boundary")
        local calls = {}
        h.FT.Schedule("parent", 0, function()
            calls[#calls + 1] = "parent"
            for index = 1, 16 do
                local name = "child" .. index
                h.FT.Schedule(name, 0, function()
                    calls[#calls + 1] = name
                end)
            end
        end)
        h.FT.Tick()
        h:assertEqual(calls, { "parent" })
        for tick = 1, 4 do
            h.FT.Tick()
            h:assertEqual(#calls, 1 + tick * 4)
        end
        h.FT.Tick()
        h:assertEqual(#calls, 17)
        h:assertHealthy()
    end },
    { name = "scheduler reset invalidates the rest of an already selected batch", run = function(Host)
        local h = Host.new()
        h:start()
        h.FT.ResetCollectors("test_boundary")
        local previous = 0
        local fresh    = 0
        for index = 1, 4 do
            h.FT.Schedule("original" .. index, 0, function()
                previous = previous + 1
                h.FT.ResetCollectors("test_boundary")
                h.FT.Schedule("fresh", 0, function()
                    fresh = fresh + 1
                end)
            end)
        end
        h.FT.Tick()
        h:assertEqual(previous, 1)
        h:assertEqual(fresh, 0)
        h.FT.Tick()
        h:assertEqual(previous, 1)
        h:assertEqual(fresh, 1)
        h:assertHealthy()
    end },
    { name = "a callback can safely reschedule its own key once per tick", run = function(Host)
        local h = Host.new()
        h:start()
        h.FT.ResetCollectors("test_boundary")
        local count = 0
        local function repeatTask()
            count = count + 1
            if count < 8 then
                h.FT.Schedule("repeat", 0, repeatTask)
            end
        end
        h.FT.Schedule("repeat", 0, repeatTask)
        for tick = 1, 8 do
            h.FT.Tick()
            h:assertEqual(count, tick)
        end
        h.FT.Tick()
        h:assertEqual(count, 8)
        h:assertHealthy()
    end },
}
