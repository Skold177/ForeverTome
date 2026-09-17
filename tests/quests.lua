local function Fixture(Host, empty)
    local host  = Host.new()
    local state = {
        rows = empty and {} or { { questID = 501, title = "A New Threat", isHeader = false, level = 6 } },
        total = empty and 0 or 1, onQuest = not empty, title = "A New Threat",
        objectives = { { text = "Wolves slain: 0/5", type = "monster", finished = false, numFulfilled = 0, numRequired = 5 } },
        requested = 0,
    }
    host.env.C_QuestLog = {
        GetNumQuestLogEntries = function()
            return #state.rows, state.total
        end,
        GetInfo = function(index)
            return state.rows[index]
        end,
        GetQuestObjectives = function()
            return state.objectives
        end,
        IsComplete = function()
            return state.ready or false
        end,
        IsQuestFlaggedCompleted = function()
            return false
        end,
        IsOnQuest = function()
            return state.onQuest
        end,
        GetTitleForQuestID = function()
            return state.title
        end,
        RequestLoadQuestByID = function()
            state.requested = state.requested + 1
        end,
    }
    host.env.GetQuestLogQuestText = function(index)
        assert(index == 1, "quest log text must use its log index")
        return "The wolves have returned.", "Defeat five wolves."
    end
    return host, state
end

local function Refresh(host)
    host:event("QUEST_LOG_UPDATE")
    host:advance(0.5)
end

local function Progress(state, value, creature)
    state.objectives[1].numFulfilled = value
    state.objectives[1].text         = (creature or "Wolves") .. " slain: " .. value .. "/5"
end

local function DialogueFixture(host, state)
    state.dialogueQuestID = 501
    state.npcID          = 7001
    host.env.GetQuestID = function()
        return state.dialogueQuestID
    end
    host.env.GetTitleText = function()
        return state.title
    end
    host.env.GetQuestText = function()
        return "The wolves have returned."
    end
    host.env.GetObjectiveText = function()
        return "Defeat five wolves."
    end
    host.env.UnitGUID = function(token)
        if token == "npc" and state.npcID then
            return "Creature-0-1-2-3-" .. state.npcID .. "-000001"
        end
    end
    host.env.C_CreatureInfo.GetCreatureID = function()
        return state.npcID
    end
    host.env.UnitName = function()
        return "Quest giver"
    end
end

return {
    {
        name = "quests: receipt ambiguity lasts thirty seconds after a delayed turnin",
        run = function(Host)
            local host = Fixture(Host, true)
            host:start()
            host:event("QUEST_ACCEPTED", 501)
            local first = host:last("quest.accepted")
            host:event("QUEST_REMOVED", 501, false)
            host:advance(29)
            host:event("QUEST_TURNED_IN", 501, 40, 0)
            local turnin         = host:last("quest.turned_in")
            local runID, turninID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, first.data.quest_run_id)
            host:assertEqual(turninID, turnin.observation_id)
            host:event("QUEST_ACCEPTED", 501)
            local second = host:last("quest.accepted")
            host:assertTrue(second.data.quest_run_id ~= first.data.quest_run_id)
            host:advance(2)
            runID, turninID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, nil)
            host:assertEqual(turninID, nil)
            host:advance(29)
            runID, turninID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, second.data.quest_run_id)
            host:assertEqual(turninID, nil)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: abandoning and reaccepting cannot discard an earlier receipt ambiguity window",
        run = function(Host)
            local host = Fixture(Host, true)
            host:start()
            host:event("QUEST_ACCEPTED", 501)
            host:event("QUEST_TURNED_IN", 501, 40, 0)
            host:advance(1)
            host:event("QUEST_ACCEPTED", 501)
            local runID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, nil)
            host:event("QUEST_REMOVED", 501, false)
            host:event("QUEST_ACCEPTED", 501)
            local latest = host:last("quest.accepted")
            runID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, nil)
            host:advance(30)
            local turninID
            runID, turninID = host.FT.QuestRewardContext(501)
            host:assertEqual(runID, latest.data.quest_run_id)
            host:assertEqual(turninID, nil)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: reward dialogue survives a long closed panel and links delayed turnin",
        run = function(Host)
            local host, state = Fixture(Host)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_COMPLETE")
            local reward = host:last("quest.dialogue")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:advance(43)
            host:event("QUEST_REMOVED", 501, false)
            local removal = host:last("quest.removed")
            host:event("QUEST_TURNED_IN", 501, 380, 50)
            local turnin = host:last("quest.turned_in")
            host:assertEqual(turnin.data.quest_run_id, reward.data.quest_run_id)
            host:assertEqual(turnin.data.dialogue_npc.creature_id, 7001)
            host:assertEqual(turnin.data.dialogue_context, "quest_run_reward_dialogue")
            host:assertEqual(turnin.data.npc, nil)
            host:assertEqual(turnin.missing_fields.npc, "unknown_source")
            host:assertEqual(turnin.related_observation_ids[1], removal.observation_id)
            host:assertEqual(turnin.related_observation_ids[2], reward.observation_id)
            host:assertEqual(turnin.data.xp_reward, 380)
            host:assertEqual(turnin.data.money_reward, 50)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: unrelated dialogue does not erase the current run reward history",
        run = function(Host)
            for _, nextEvent in ipairs({ "GOSSIP_SHOW", "QUEST_GREETING", "QUEST_DETAIL", "QUEST_COMPLETE" }) do
                local host, state = Fixture(Host)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_COMPLETE")
                local reward = host:last("quest.dialogue")
                host:event("QUEST_FINISHED")
                state.dialogueQuestID = 502
                state.npcID          = 7002
                host:event(nextEvent)
                host:event("QUEST_FINISHED")
                state.npcID = nil
                host:advance(43)
                host:event("QUEST_TURNED_IN", 501, 380, 50)
                local turnin = host:last("quest.turned_in")
                host:assertEqual(turnin.data.dialogue_npc.creature_id, 7001)
                host:assertEqual(turnin.data.interaction_id, reward.data.interaction_id)
                host:assertEqual(turnin.related_observation_ids[1], reward.observation_id)
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: delayed turnin preserves an unrelated pending acceptance offer",
        run = function(Host)
            for _, cached in ipairs({ false, true }) do
                local host, state = Fixture(Host, true)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_ACCEPTED", 501)
                local reward
                if cached then
                    host:event("QUEST_COMPLETE")
                    reward = host:last("quest.dialogue")
                end
                host:event("QUEST_FINISHED")
                state.npcID = nil
                host:advance(43)
                state.dialogueQuestID = 502
                state.npcID          = 7002
                host:event("QUEST_DETAIL")
                local offer = host:last("quest.dialogue")
                host:event("QUEST_FINISHED")
                state.npcID = nil
                host:event("QUEST_TURNED_IN", 501, 40, 0)
                local turnin = host:last("quest.turned_in")
                host:assertEqual(turnin.related_observation_ids, reward and { reward.observation_id } or {})
                host:event("QUEST_ACCEPTED", 502)
                local accepted = host:last("quest.accepted")
                host:assertEqual(accepted.data.quest_id, 502)
                host:assertEqual(accepted.data.dialogue_npc.creature_id, 7002)
                host:assertEqual(accepted.data.interaction_id, offer.data.interaction_id)
                host:assertEqual(accepted.data.dialogue_context, "recent_dialogue")
                host:assertEqual(accepted.related_observation_ids, { offer.observation_id })
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: a new run cannot inherit a previous run reward dialogue",
        run = function(Host)
            local host, state = Fixture(Host)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_COMPLETE")
            local reward = host:last("quest.dialogue")
            host:event("QUEST_FINISHED")
            host:event("QUEST_REMOVED", 501, false)
            host:event("QUEST_ACCEPTED", 501)
            state.npcID = nil
            host:event("QUEST_TURNED_IN", 501, 380, 50)
            local turnin = host:last("quest.turned_in")
            host:assertTrue(turnin.data.quest_run_id ~= reward.data.quest_run_id)
            host:assertEqual(turnin.data.dialogue_npc, nil)
            host:assertEqual(turnin.data.dialogue_context, nil)
            host:assertEqual(#turnin.related_observation_ids, 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: reset discards run reward history even if the quest remains in the log",
        run = function(Host)
            for _, reason in ipairs({ "pause", "world_transition", "collector_error", "user_clear" }) do
                local host, state = Fixture(Host)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_COMPLETE")
                host:event("QUEST_FINISHED")
                state.npcID = nil
                host.FT.ResetCollectors(reason)
                Refresh(host)
                host:event("QUEST_TURNED_IN", 501, 380, 50)
                local turnin = host:last("quest.turned_in")
                host:assertEqual(turnin.data.dialogue_npc, nil)
                host:assertEqual(turnin.data.dialogue_context, nil)
                host:assertEqual(#turnin.related_observation_ids, 0)
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: latest same-run reward dialogue replaces older reward context",
        run = function(Host)
            local host, state = Fixture(Host)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_COMPLETE")
            local first = host:last("quest.dialogue")
            host:event("QUEST_FINISHED")
            state.npcID = 7002
            host:event("QUEST_COMPLETE")
            local latest = host:last("quest.dialogue")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:advance(43)
            host:event("QUEST_TURNED_IN", 501, 380, 50)
            local turnin = host:last("quest.turned_in")
            host:assertEqual(turnin.data.dialogue_npc.creature_id, 7002)
            host:assertEqual(turnin.related_observation_ids[1], latest.observation_id)
            host:assertEqual(first.data.npc.creature_id, 7001)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: acceptance links an open offer without treating it as historical NPC data",
        run = function(Host)
            local host, state = Fixture(Host, true)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_DETAIL")
            local offer = host:last("quest.dialogue")
            host:advance(3)
            host:event("QUEST_ACCEPTED", 501)
            host:event("QUEST_FINISHED")
            local accepted = host:last("quest.accepted")
            host:assertEqual(accepted.data.npc.creature_id, 7001)
            host:assertEqual(accepted.data.dialogue_npc, nil)
            host:assertEqual(accepted.data.interaction_id, offer.data.interaction_id)
            host:assertEqual(accepted.related_observation_ids[1], offer.observation_id)
            host:assertEqual(accepted.evidence.method, "direct_event")
            host:assertHealthy()
        end,
    },
    {
        name = "quests: closing dialogue before acceptance retains explicitly historical giver context",
        run = function(Host)
            for _, closing in ipairs({ "QUEST_FINISHED", "GOSSIP_CLOSED" }) do
                local host, state = Fixture(Host, true)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_DETAIL")
                local offer = host:last("quest.dialogue")
                host:advance(3)
                host:event(closing, false)
                state.npcID = nil
                host:advance(0.5)
                host:event("QUEST_ACCEPTED", 501)
                local accepted = host:last("quest.accepted")
                host:assertEqual(accepted.data.npc, nil)
                host:assertEqual(accepted.missing_fields.npc, "unknown_source")
                host:assertEqual(accepted.data.dialogue_npc.creature_id, 7001)
                host:assertEqual(accepted.data.interaction_id, offer.data.interaction_id)
                host:assertEqual(accepted.related_observation_ids[1], offer.observation_id)
                host:assertEqual(offer.data.npc.creature_id, 7001)
                host:event("QUEST_ACCEPTED", 501)
                host:assertEqual(host:last("quest.accepted").data.dialogue_npc, nil)
                host:assertEqual(#host:last("quest.accepted").related_observation_ids, 0)
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: repeated close notifications cannot extend canceled offer expiry",
        run = function(Host)
            local host, state = Fixture(Host, true)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_DETAIL")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:advance(1.5)
            host:event("GOSSIP_CLOSED", false)
            host:advance(1)
            host:event("QUEST_ACCEPTED", 501)
            local accepted = host:last("quest.accepted")
            host:assertEqual(accepted.data.dialogue_npc, nil)
            host:assertEqual(accepted.data.interaction_id, nil)
            host:assertEqual(#accepted.related_observation_ids, 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: unrelated quests and newer interactions cannot inherit an old giver",
        run = function(Host)
            for _, nextEvent in ipairs({ "QUEST_DETAIL", "GOSSIP_SHOW", "QUEST_GREETING", "QUEST_ACCEPTED" }) do
                local host, state = Fixture(Host, true)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_DETAIL")
                host:event("QUEST_FINISHED")
                state.dialogueQuestID = 502
                state.npcID          = nil
                host:event(nextEvent, 502)
                host:event("QUEST_FINISHED")
                host:event("QUEST_ACCEPTED", 501)
                local accepted = host:last("quest.accepted")
                host:assertEqual(accepted.data.npc, nil)
                host:assertEqual(accepted.data.dialogue_npc, nil)
                host:assertEqual(#accepted.related_observation_ids, 0)
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: a different live NPC is never paired with the previous dialogue",
        run = function(Host)
            local host, state = Fixture(Host, true)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_DETAIL")
            host:event("QUEST_FINISHED")
            state.npcID = 7002
            host:event("QUEST_ACCEPTED", 501)
            local accepted = host:last("quest.accepted")
            host:assertEqual(accepted.data.npc.creature_id, 7002)
            host:assertEqual(accepted.data.dialogue_npc, nil)
            host:assertEqual(accepted.data.interaction_id, nil)
            host:assertEqual(#accepted.related_observation_ids, 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: turnin after reward closure links both dialogue and removal",
        run = function(Host)
            local host, state = Fixture(Host)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_COMPLETE")
            local reward = host:last("quest.dialogue")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:event("QUEST_REMOVED", 501, false)
            local removal = host:last("quest.removed")
            host:event("QUEST_TURNED_IN", 501, 40, 0)
            local turnin = host:last("quest.turned_in")
            host:assertEqual(turnin.data.dialogue_npc.creature_id, 7001)
            host:assertEqual(turnin.data.npc, nil)
            host:assertEqual(turnin.related_observation_ids[1], removal.observation_id)
            host:assertEqual(turnin.related_observation_ids[2], reward.observation_id)
            host:assertEqual(turnin.data.quest_run_id, removal.data.quest_run_id)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: offer and reward dialogue phases cannot substitute for each other",
        run = function(Host)
            local host, state = Fixture(Host)
            DialogueFixture(host, state)
            host:start()
            host:event("QUEST_DETAIL")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:event("QUEST_TURNED_IN", 501, 40, 0)
            host:assertEqual(#host:last("quest.turned_in").related_observation_ids, 0)
            host:assertEqual(host:last("quest.turned_in").data.dialogue_npc, nil)
            state.npcID = 7001
            host:event("QUEST_COMPLETE")
            host:event("QUEST_FINISHED")
            state.npcID = nil
            host:event("QUEST_ACCEPTED", 501)
            host:assertEqual(#host:last("quest.accepted").related_observation_ids, 0)
            host:assertEqual(host:last("quest.accepted").data.dialogue_npc, nil)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: reset boundaries discard dialogue references",
        run = function(Host)
            for _, reason in ipairs({ "pause", "world_transition", "collector_error", "user_clear" }) do
                local host, state = Fixture(Host, true)
                DialogueFixture(host, state)
                host:start()
                host:event("QUEST_DETAIL")
                host:event("QUEST_FINISHED")
                state.npcID = nil
                host.FT.ResetCollectors(reason)
                host:event("QUEST_ACCEPTED", 501)
                local accepted = host:last("quest.accepted")
                host:assertEqual(accepted.data.dialogue_npc, nil)
                host:assertEqual(accepted.data.interaction_id, nil)
                host:assertEqual(#accepted.related_observation_ids, 0)
                host:assertHealthy()
            end
        end,
    },
    {
        name = "quests: login establishes a baseline without inventing acceptance",
        run = function(Host)
            local host = Fixture(Host)
            host:start()
            host:advance(0.5)
            host:assertEqual(#host:records("quest.accepted"), 0)
            host:assertEqual(#host:records("quest.baseline"), 1)
            local snapshot = host:last("quest.snapshot")
            host:assertEqual(snapshot.data.start_reason, "baseline")
            host:assertEqual(snapshot.data.complete, true)
            host:assertEqual(snapshot.data.metadata.description, "The wolves have returned.")
            host:assertEqual(snapshot.data.historically_completed, false)
            host:assertEqual(snapshot.data.objectives[1].numFulfilled, 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: modern acceptance decodes argument one and repeated runs stay distinct",
        run = function(Host)
            local host, state = Fixture(Host, true)
            host:start()
            host:advance(0.5)
            state.rows    = { { questID = 501, title = state.title, isHeader = false } }
            state.total   = 1
            state.onQuest = true
            host:event("QUEST_ACCEPTED", 501, 999)
            host:advance(0.5)
            local first = host:last("quest.accepted")
            host:assertEqual(first.data.quest_id, 501)
            host:assertEqual(host:last("quest.snapshot").data.quest_run_id, first.data.quest_run_id)
            host:event("QUEST_REMOVED", 501, false)
            host:assertEqual(host:last("quest.removed").data.reason, "unknown")
            host:event("QUEST_ACCEPTED", 501)
            host:advance(0.5)
            local second = host:last("quest.accepted")
            host:assertTrue(second.data.quest_run_id ~= first.data.quest_run_id)
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            host:assertEqual(#host:records("quest.accepted"), 2)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: localized counter text changes yield a linked delta and duplicate updates coalesce",
        run = function(Host)
            local host, state = Fixture(Host)
            host:start()
            host:advance(0.5)
            local baseline = host:last("quest.snapshot")
            Progress(state, 2)
            host:event("QUEST_LOG_UPDATE")
            host:event("QUEST_LOG_UPDATE")
            host:advance(0.5)
            local delta = host:last("quest.objective_delta")
            host:assertEqual(delta.data.amount, 2)
            host:assertEqual(delta.data.before.numFulfilled, 0)
            host:assertEqual(delta.data.after.numFulfilled, 2)
            host:assertEqual(delta.related_observation_ids[1], baseline.observation_id)
            host:assertEqual(baseline.data.objectives[1].numFulfilled, 0)
            host:assertEqual(baseline.data.objectives[1].text, "Wolves slain: 0/5")
            Refresh(host)
            host:assertEqual(#host:records("quest.objective_delta"), 1)
            host:assertEqual(#host:records("quest.snapshot"), 2)
            Progress(state, 1)
            Refresh(host)
            host:assertEqual(host:last("quest.objective_delta").data.amount, -1)
            host:assertEqual(host:records("quest.snapshot")[1].data.objectives[1].numFulfilled, 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: layout changes and missing objective reads require fresh baselines",
        run = function(Host)
            local host, state = Fixture(Host)
            host:start()
            host:advance(0.5)
            local firstRevision = host:last("quest.snapshot").data.layout_revision
            Progress(state, 2, "Spiders")
            Refresh(host)
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            host:assertTrue(host:last("quest.snapshot").data.layout_revision > firstRevision)
            local objectives = state.objectives
            state.objectives = nil
            Refresh(host)
            host:assertEqual(host:last("quest.snapshot").data.complete, false)
            host:assertEqual(host:last("quest.snapshot").missing_fields.objectives, "not_ready")
            state.objectives = objectives
            Progress(state, 4, "Spiders")
            Refresh(host)
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            host:assertEqual(host:last("quest.snapshot").data.baseline, true)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: a collapsed or missing log row never means abandonment",
        run = function(Host)
            local host, state = Fixture(Host)
            host:start()
            host:advance(0.5)
            state.rows = { { isHeader = true, isCollapsed = true, title = "Zone" } }
            Progress(state, 1)
            Refresh(host)
            host:assertEqual(host:last("quest.log_scope").data.complete, false)
            host:assertEqual(#host:records("quest.removed"), 0)
            host:assertEqual(host:last("quest.objective_delta").data.amount, 1)
            state.onQuest = nil
            Refresh(host)
            state.rows    = { { questID = 501, title = state.title, isHeader = false } }
            state.onQuest = true
            Progress(state, 3)
            Refresh(host)
            host:assertEqual(#host:records("quest.objective_delta"), 1)
            host:assertEqual(#host:records("quest.removed"), 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: reward dialogue is an offer and an explicit turnin is a separate event",
        run = function(Host)
            local host = Fixture(Host)
            host.env.GetQuestID = function()
                return 501
            end
            host.env.GetTitleText = function()
                return "A New Threat"
            end
            host.env.GetRewardText = function()
                return "Thank you."
            end
            host.env.GetNumQuestRewards = function()
                return 1
            end
            host.env.GetNumQuestChoices = function()
                return 1
            end
            host.env.GetQuestItemInfo = function(kind)
                return "A reward", 100, 1, 1, false, kind == "reward" and 101 or 102, 0
            end
            host.env.GetQuestItemLink = function(kind)
                return "item:" .. (kind == "reward" and "101" or "102")
            end
            host:start()
            host:advance(0.5)
            host:event("QUEST_COMPLETE")
            host:event("QUEST_FINISHED")
            host:assertEqual(#host:records("quest.turned_in"), 0)
            local dialogue = host:last("quest.dialogue")
            host:assertEqual(dialogue.data.rewards[1].item_id, 101)
            host:assertEqual(dialogue.data.choices[1].item_id, 102)
            host:assertEqual(dialogue.data.rewards[1].usable, false)
            host:event("QUEST_REMOVED", 501, false)
            local removal = host:last("quest.removed")
            host:event("QUEST_TURNED_IN", 501, 0, 25)
            local turnin = host:last("quest.turned_in")
            host:assertEqual(turnin.data.xp_reward, 0)
            host:assertEqual(turnin.data.money_reward, 25)
            host:assertEqual(turnin.data.quest_run_id, removal.data.quest_run_id)
            host:assertEqual(turnin.related_observation_ids[1], removal.observation_id)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: reset cancels stale comparisons and scheduled captures",
        run = function(Host)
            local host, state = Fixture(Host)
            host:start()
            host:advance(0.5)
            local previousRun = host:last("quest.snapshot").data.quest_run_id
            Progress(state, 2)
            host:event("QUEST_LOG_UPDATE")
            host.FT.ResetCollectors("test_coverage_gap")
            host:advance(0.5)
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            Refresh(host)
            host:assertTrue(host:last("quest.snapshot").data.quest_run_id ~= previousRun)
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: delayed metadata appends linked evidence without rewriting prior observations",
        run = function(Host)
            local host, state = Fixture(Host)
            state.rows[1].title = nil
            state.title         = nil
            host:start()
            host:advance(0.5)
            local before = host:last("quest.snapshot")
            host:assertEqual(before.missing_fields.title, "not_ready")
            host:assertEqual(state.requested, 1)
            state.title = "Resolved quest title"
            host:event("QUEST_DATA_LOAD_RESULT", 999, true)
            host:assertEqual(#host:records("quest.metadata"), 0)
            host:event("QUEST_DATA_LOAD_RESULT", 501, true)
            local metadata = host:last("quest.metadata")
            host:assertEqual(metadata.data.title, "Resolved quest title")
            host:assertEqual(metadata.related_observation_ids[1], before.observation_id)
            host:assertEqual(before.data.metadata.title, nil)
            host:advance(0.5)
            host:assertEqual(host:last("quest.snapshot").data.metadata.title, "Resolved quest title")
            host:assertEqual(#host:records("quest.objective_delta"), 0)
            host:assertEqual(host:records("quest.snapshot")[1].data.metadata.title, nil)
            host:assertHealthy()
        end,
    },
    {
        name = "quests: a successful load with unreadable metadata still retries and terminates",
        run = function(Host)
            local host, state = Fixture(Host)
            state.rows[1].title = nil
            state.title         = nil
            host:start()
            host:event("QUEST_DATA_LOAD_RESULT", 501, true)
            host:assertEqual(host:last("quest.metadata").missing_fields.title, "not_ready")
            host:advance(11)
            host:assertEqual(state.requested, 2)
            host:advance(11)
            host:assertEqual(#host:records("quest.metadata_unavailable"), 1)
            host:advance(20)
            host:assertEqual(state.requested, 2)
            host:assertEqual(#host:records("quest.metadata_unavailable"), 1)
            host:assertHealthy()
        end,
    },
}
