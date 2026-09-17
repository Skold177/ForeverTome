local _, FT = ...

local MAX_QUESTS     = 256
local MAX_PENDING    = 32
local MAX_ROWS       = 512
local MAX_OBJECTIVES = 64
local MAX_REWARDS    = 64
local DIALOGUE_GRACE = 2
local runs           = {}
local pending        = {}
local closed         = {}
local runCount       = 0
local pendingCount   = 0
local generation     = 0
local interaction    = nil
local dialogue       = nil
local lastScanState  = nil
local capacityNoted  = false

local infoFields = {
    title = "string", level = "number", suggestedGroup = "number", frequency = "number",
    isTask = "boolean", isBounty = "boolean", isStory = "boolean", isHidden = "boolean",
    isAutoComplete = "boolean", questClassification = "number", campaignID = "number",
    description = "string", objective_text = "string",
}

local objectiveFields = {
    text = "string", type = "string", finished = "boolean", numFulfilled = "number",
    numRequired = "number", objectiveType = "number",
}

local gossipFields = {
    questID = "number", title = "string", questLevel = "number", isTrivial = "boolean",
    frequency = "number", isComplete = "boolean", repeatable = "boolean", isLegendary = "boolean",
    isIgnored = "boolean", isImportant = "boolean", isMeta = "boolean", questInfoID = "number",
}

local optionFields = {
    gossipOptionID = "number", name = "string", icon = "number", status = "number",
    spellID = "number", flags = "number", orderIndex = "number", failureDescription = "string",
}

local function Enabled()
    return FT.Profile and FT.Profile.quest_mode == "modern"
end

local function ContentID(value)
    local number = FT.Value(value, "number")
    if number and number > 0 and number <= 2147483647 and number == math.floor(number) then
        return number
    end
end

local function Count(value, maximum)
    local number = FT.Value(value, "number")
    if not number or number < 0 or number ~= math.floor(number) then
        return nil, false
    end
    return math.min(number, maximum), number <= maximum
end

local function Fields(source, specification)
    local result = {}
    for key, valueType in pairs(specification) do
        result[key] = FT.Field(source, key, valueType)
    end
    return result
end

local function ArrayCount(source, maximum)
    if not FT.Value(source, "table") then
        return nil, false
    end
    if FT.Length then
        return Count(FT.Length(source), maximum)
    end
    local ok, length = pcall(function()
        return #source
    end)
    if ok then
        return Count(length, maximum)
    end
    return nil, false
end

local function SameFields(left, right, specification)
    if not left or not right then
        return left == right
    end
    for key in pairs(specification) do
        if left[key] ~= right[key] then
            return false
        end
    end
    return true
end

local function Related(first, second)
    local result = {}
    if first then
        result[#result + 1] = first
    end
    if second then
        result[#result + 1] = second
    end
    return result
end

local function QuestGap(reason, event)
    if not capacityNoted then
        capacityNoted = true
        FT.Emit("coverage.gap", { collectors = { "quests" }, reason = reason }, event, "api_snapshot")
    end
end

local function NewRun(questID, reason, event)
    if not runs[questID] and runCount >= MAX_QUESTS then
        QuestGap("capacity_limit", event)
        return nil
    end
    if not runs[questID] then
        runCount = runCount + 1
    end
    local run = {
        id = FT.NewContext("quest"), questID = questID, start_reason = reason,
        revision = 0, metadata = {},
    }
    runs[questID]   = run
    closed[questID] = nil
    if reason == "baseline" then
        run.origin = FT.Emit("quest.baseline", {
            quest_id = questID, quest_run_id = run.id, start_reason = reason,
        }, event, "api_snapshot", nil, { acceptance = "not_observed" })
    end
    return run
end

local RequestData

local function ScheduleDataTimeouts()
    local epoch = generation
    FT.Schedule("quest_data_timeouts", 1, function()
        if epoch ~= generation then
            return
        end
        local expired = {}
        for questID, request in pairs(pending) do
            if FT.Now() - request.requested >= 10 then
                expired[#expired + 1] = questID
            end
        end
        for index = 1, #expired do
            local questID = expired[index]
            local request = pending[questID]
            if request and request.attempts < 2 then
                RequestData(questID)
            elseif request then
                pending[questID] = nil
                pendingCount    = pendingCount - 1
                FT.Emit("quest.metadata_unavailable", { quest_id = questID, reason = "not_ready" },
                    { method = "metadata_timeout" }, "api_snapshot", request.references,
                    { metadata = "not_ready" })
            end
            if epoch ~= generation then
                return
            end
        end
        if pendingCount > 0 then
            ScheduleDataTimeouts()
        end
    end)
end

RequestData = function(questID, observationID)
    if not FT.Profile.quest_data_load then
        return
    end
    local request = pending[questID]
    if not request then
        if pendingCount >= MAX_PENDING then
            QuestGap("capacity_limit", { method = "quest_metadata_capacity" })
            return
        end
        request = { attempts = 0, references = {}, generation = generation }
        pending[questID] = request
        pendingCount    = pendingCount + 1
    end
    if observationID and #request.references < 8 then
        request.references[#request.references + 1] = observationID
    end
    if request.attempts >= 2 or (request.requested and FT.Now() - request.requested < 10) then
        return
    end
    request.attempts  = request.attempts + 1
    request.requested = FT.Now()
    FT.Call("C_QuestLog.RequestLoadQuestByID", questID)
    ScheduleDataTimeouts()
end

local function ReadObjectives(questID)
    local source          = FT.Call("C_QuestLog.GetQuestObjectives", questID)
    local count, complete = ArrayCount(source, MAX_OBJECTIVES)
    local objectives      = {}
    local missing         = {}
    if not count then
        return nil, false, { objectives = "not_ready" }
    end
    if not complete then
        missing.objectives = "capacity_limit"
    end
    for index = 1, count do
        local raw       = FT.Field(source, index, "table")
        local objective = Fields(raw, objectiveFields)
        objective.index = index
        for key, valueType in pairs(objectiveFields) do
            if key ~= "objectiveType" and objective[key] == nil then
                complete = false
                missing["objectives." .. index .. "." .. key] = "not_ready"
            end
        end
        objectives[#objectives + 1] = objective
    end
    return objectives, complete, missing
end

local function LayoutText(text)
    if text then
        return (string.gsub(text, "%d+(%s*/%s*%d+)", "#%1"))
    end
end

local function Comparable(before, after)
    if #before ~= #after then
        return false
    end
    for index = 1, #before do
        local left  = before[index]
        local right = after[index]
        if left.type ~= right.type or left.objectiveType ~= right.objectiveType
            or left.numRequired ~= right.numRequired or LayoutText(left.text) ~= LayoutText(right.text) then
            return false
        end
    end
    return true
end

local function SameObjectives(before, after)
    if not before or not after then
        return before == after
    end
    if #before ~= #after then
        return false
    end
    for index = 1, #before do
        if not SameFields(before[index], after[index], objectiveFields) then
            return false
        end
    end
    return true
end

local function Snapshot(run, rawInfo, capture, logIndex)
    local metadata                      = Fields(rawInfo or run.metadata, infoFields)
    local objectives, complete, missing = ReadObjectives(run.questID)
    local ready                         = FT.Value(FT.Call("C_QuestLog.IsComplete", run.questID), "boolean")
    local historical                    = FT.Value(FT.Call("C_QuestLog.IsQuestFlaggedCompleted", run.questID), "boolean")
    local previous                      = run.snapshot
    local comparable                    = complete and previous and previous.complete and Comparable(previous.objectives, objectives)
    if logIndex then
        local description, objectiveText = FT.Call("GetQuestLogQuestText", logIndex)
        metadata.description    = FT.Value(description, "string")
        metadata.objective_text = FT.Value(objectiveText, "string")
    end
    if not metadata.title then
        metadata.title = FT.Value(FT.Call("C_QuestLog.GetTitleForQuestID", run.questID), "string")
    end
    if metadata.title == nil then
        missing.title = "not_ready"
    end
    if metadata.description == nil then
        missing.description = "not_ready"
    end
    if metadata.objective_text == nil then
        missing.objective_text = "not_ready"
    end
    if ready == nil then
        missing.ready = "not_ready"
    end
    if historical == nil then
        missing.historically_completed = "not_ready"
    end
    if complete and not comparable then
        run.revision = run.revision + 1
    end
    local changed = not previous or previous.complete ~= complete or previous.ready ~= ready
        or previous.historical ~= historical or not SameObjectives(previous.objectives, objectives)
        or not SameFields(run.metadata, metadata, infoFields)
    if not changed then
        return
    end
    local snapshotID = FT.Emit("quest.snapshot", {
        quest_id = run.questID, quest_run_id = run.id, start_reason = run.start_reason,
        layout_revision = run.revision, objectives = objectives, complete = complete,
        metadata = metadata, ready = ready, historically_completed = historical,
        baseline = not comparable,
    }, capture, "api_snapshot", Related(run.origin), missing)
    if not snapshotID then
        run.snapshot = nil
        return
    end
    if comparable then
        for index = 1, #objectives do
            local before = previous.objectives[index]
            local after  = objectives[index]
            if before.numFulfilled ~= after.numFulfilled or before.finished ~= after.finished then
                FT.Emit("quest.objective_delta", {
                    quest_id = run.questID, quest_run_id = run.id, layout_revision = run.revision,
                    objective_index = index, before = before, after = after,
                    amount = after.numFulfilled - before.numFulfilled,
                }, capture, "snapshot_diff", Related(previous.observationID, snapshotID))
            end
        end
    end
    if ready ~= nil and (not previous or previous.ready ~= ready) then
        FT.Emit("quest.ready", {
            quest_id = run.questID, quest_run_id = run.id, ready = ready,
        }, capture, "api_snapshot", Related(snapshotID))
    end
    run.metadata = metadata
    run.snapshot = {
        objectives = objectives, complete = complete, ready = ready, historical = historical,
        observationID = snapshotID,
    }
    if not complete or metadata.title == nil then
        RequestData(run.questID, snapshotID)
    end
end

local function Scan(capture)
    if not Enabled() then
        return
    end
    local rawCount, rawTotal = FT.Call("C_QuestLog.GetNumQuestLogEntries")
    local count, complete    = Count(rawCount, MAX_ROWS)
    local total              = FT.Value(rawTotal, "number")
    local visible            = {}
    local visibleCount       = 0
    capture.sampled_elapsed_s = FT.Now()
    if count then
        for index = 1, count do
            local info     = FT.Call("C_QuestLog.GetInfo", index)
            local isHeader = FT.Field(info, "isHeader", "boolean")
            local questID  = ContentID(FT.Field(info, "questID", "number"))
            if isHeader == true then
                if FT.Field(info, "isCollapsed", "boolean") ~= false then
                    complete = false
                end
            elseif isHeader == false and questID then
                if not visible[questID] then
                    visible[questID] = true
                    visibleCount    = visibleCount + 1
                    local run = runs[questID] or NewRun(questID, "baseline", capture)
                    if run then
                        Snapshot(run, info, capture, index)
                    end
                end
            else
                complete = false
            end
        end
    end
    complete = complete and total ~= nil and total == visibleCount
    for questID, run in pairs(runs) do
        if not visible[questID] then
            local onQuest = FT.Value(FT.Call("C_QuestLog.IsOnQuest", questID), "boolean")
            if onQuest == true then
                Snapshot(run, nil, capture)
            else
                run.snapshot = nil
            end
        end
    end
    local state = tostring(count) .. ":" .. tostring(total) .. ":" .. visibleCount .. ":" .. tostring(complete)
    if lastScanState ~= state then
        lastScanState = state
        FT.Emit("quest.log_scope", {
            shown_entries = count, reported_quests = total, readable_quests = visibleCount,
            complete = complete, scope = "visible_log", direct_refresh_of_known_quests = true,
        }, capture, "api_snapshot", nil, complete and nil or { enumeration = "not_observed" })
    end
end

local function ScheduleScan(event)
    if not Enabled() then
        return
    end
    local capture = { event = event, method = "deferred_read", trigger_elapsed_s = FT.Now() }
    local epoch   = generation
    FT.Schedule("quest_scan", 0.35, function()
        if epoch == generation then
            Scan(capture)
        end
    end)
end

local function ReadRewards(kind, countAPI, missing)
    if not FT.Profile.quest_rewards then
        missing[kind] = "unsupported"
        return nil
    end
    local count, complete = Count(FT.Call(countAPI), MAX_REWARDS)
    local rewards         = {}
    if not count then
        missing[kind] = "not_ready"
        return nil
    end
    if not complete then
        missing[kind] = "capacity_limit"
    end
    for index = 1, count do
        local name, texture, quantity, quality, usable, itemID, flags = FT.Call("GetQuestItemInfo", kind, index)
        local link                                                    = FT.Value(FT.Call("GetQuestItemLink", kind, index), "string")
        rewards[#rewards + 1] = {
            index = index, item_id = ContentID(itemID) or FT.ItemID(link), item_link = link,
            name = FT.Value(name, "string"), texture = FT.Value(texture, "number"),
            quantity = FT.Value(quantity, "number"), quality = FT.Value(quality, "number"),
            usable = FT.Value(usable, "boolean"), context_flags = FT.Value(flags, "number"),
        }
        if not rewards[#rewards].item_id then
            missing[kind .. "." .. index .. ".item_id"] = "not_ready"
        end
        if rewards[#rewards].quantity == nil then
            missing[kind .. "." .. index .. ".quantity"] = "not_ready"
        end
    end
    return rewards
end

local function EnrichItems(items, observationID)
    if items and FT.RequestItem then
        for index = 1, #items do
            local item = items[index]
            if item.item_id then
                FT.RequestItem(item.item_id, item.item_link, observationID)
            end
        end
    end
end

local function CloseInteraction()
    interaction = nil
    if dialogue and not dialogue.closed_at then
        dialogue.closed_at = FT.Now()
    end
end

local function EventContext(questID, phase)
    local recent    = dialogue
    local npc       = FT.Unit("npc")
    local contextID = npc and interaction
    local reference
    local dialogueNPC
    dialogue = nil
    if recent and recent.quest_id == questID and recent.phase == phase
        and (not recent.closed_at or FT.Now() - recent.closed_at <= DIALOGUE_GRACE)
        and (not npc or not recent.npc or npc.guid == recent.npc.guid) then
        contextID = recent.interaction_id
        reference = recent.observation_id
        if not npc and recent.npc then
            dialogueNPC = recent.npc
        end
    end
    return npc, contextID, reference, dialogueNPC
end

local function Dialogue(event, questStartItemID)
    if not Enabled() or not FT.Profile.quest_dialogue then
        return
    end
    interaction = interaction or FT.NewContext("quest_dialogue")
    dialogue    = nil
    local missing = {}
    local questID = ContentID(FT.Call("GetQuestID"))
    local data    = {
        interaction_id = interaction, quest_id = questID, phase = event,
        quest_run_id = questID and runs[questID] and runs[questID].id,
        npc = FT.Unit("npc"), title = FT.Value(FT.Call("GetTitleText"), "string"),
    }
    if not questID then
        missing.quest_id = "not_ready"
    end
    if not data.npc then
        missing.npc = "unknown_source"
    end
    if event == "QUEST_DETAIL" then
        data.text               = FT.Value(FT.Call("GetQuestText"), "string")
        data.objective_text     = FT.Value(FT.Call("GetObjectiveText"), "string")
        data.quest_start_item_id = ContentID(questStartItemID)
    elseif event == "QUEST_PROGRESS" then
        data.text           = FT.Value(FT.Call("GetProgressText"), "string")
        data.required_items = ReadRewards("required", "GetNumQuestItems", missing)
        data.required_money = FT.Value(FT.Call("GetQuestMoneyToGet"), "number")
    elseif event == "QUEST_COMPLETE" then
        data.text = FT.Value(FT.Call("GetRewardText"), "string")
    end
    if event == "QUEST_DETAIL" or event == "QUEST_COMPLETE" then
        data.rewards      = ReadRewards("reward", "GetNumQuestRewards", missing)
        data.choices      = ReadRewards("choice", "GetNumQuestChoices", missing)
        data.reward_money = FT.Value(FT.Call("GetRewardMoney"), "number")
        data.reward_xp    = FT.Value(FT.Call("GetRewardXP"), "number")
    end
    if data.text == nil then
        missing.text = "not_ready"
    end
    local observationID = FT.Emit("quest.dialogue", data, event, "api_snapshot", nil, missing)
    if observationID and questID then
        dialogue = {
            quest_id = questID, phase = event, npc = data.npc,
            interaction_id = interaction, observation_id = observationID,
        }
    end
    EnrichItems(data.rewards, observationID)
    EnrichItems(data.choices, observationID)
    EnrichItems(data.required_items, observationID)
end

local function GossipArray(api, key, specification, missing)
    local source          = FT.Call(api)
    local count, complete = ArrayCount(source, MAX_QUESTS)
    local quests          = {}
    if not count then
        missing[key] = "not_ready"
        return nil
    end
    if not complete then
        missing[key] = "capacity_limit"
    end
    for index = 1, count do
        local raw   = FT.Field(source, index, "table")
        local quest = Fields(raw, specification)
        quest.index = index
        quests[#quests + 1] = quest
        if specification == gossipFields and not ContentID(quest.questID) then
            quest.questID = nil
            missing[key .. "." .. index .. ".questID"] = "not_ready"
        end
    end
    return quests
end

local function Gossip(event)
    if not Enabled() or not FT.Profile.quest_gossip then
        return
    end
    interaction = interaction or FT.NewContext("quest_dialogue")
    dialogue    = nil
    local missing = {}
    local data    = {
        interaction_id = interaction, interaction_type = "gossip", npc = FT.Unit("npc"),
        text = FT.Value(FT.Call("C_GossipInfo.GetText"), "string"),
        available_quests = GossipArray("C_GossipInfo.GetAvailableQuests", "available_quests", gossipFields, missing),
        active_quests = GossipArray("C_GossipInfo.GetActiveQuests", "active_quests", gossipFields, missing),
        options = GossipArray("C_GossipInfo.GetOptions", "options", optionFields, missing),
    }
    if not data.npc then
        missing.npc = "unknown_source"
    end
    if data.text == nil then
        missing.text = "not_ready"
    end
    FT.Emit("interaction.snapshot", data, event, "api_snapshot", nil, missing)
end

local function GreetingQuests(active, missing)
    local countAPI        = active and "GetNumActiveQuests" or "GetNumAvailableQuests"
    local field           = active and "active_quests" or "available_quests"
    local count, complete = Count(FT.Call(countAPI), MAX_QUESTS)
    local quests          = {}
    if not count then
        missing[field] = "not_ready"
        return nil
    end
    if not complete then
        missing[field] = "capacity_limit"
    end
    for index = 1, count do
        local quest = { index = index }
        if active then
            local title, isComplete = FT.Call("GetActiveTitle", index)
            quest.questID    = ContentID(FT.Call("GetActiveQuestID", index))
            quest.title      = FT.Value(title, "string")
            quest.isComplete = FT.Value(isComplete, "boolean")
        else
            local trivial, frequency, repeatable, legendary, questID, important, meta, infoID = FT.Call("GetAvailableQuestInfo", index)
            quest.questID     = ContentID(questID)
            quest.title       = FT.Value(FT.Call("GetAvailableTitle", index), "string")
            quest.isTrivial   = FT.Value(trivial, "boolean")
            quest.frequency   = FT.Value(frequency, "number")
            quest.repeatable  = FT.Value(repeatable, "boolean")
            quest.isLegendary = FT.Value(legendary, "boolean")
            quest.isImportant = FT.Value(important, "boolean")
            quest.isMeta      = FT.Value(meta, "boolean")
            quest.questInfoID = FT.Value(infoID, "number")
        end
        if not quest.questID then
            missing[field .. "." .. index .. ".questID"] = "not_ready"
        end
        quests[#quests + 1] = quest
    end
    return quests
end

local function Greeting(event)
    if not Enabled() or not FT.Profile.quest_dialogue then
        return
    end
    interaction = interaction or FT.NewContext("quest_dialogue")
    dialogue    = nil
    local missing = {}
    local data    = {
        interaction_id = interaction, interaction_type = "quest_greeting", npc = FT.Unit("npc"),
        text = FT.Value(FT.Call("GetGreetingText"), "string"),
        available_quests = GreetingQuests(false, missing), active_quests = GreetingQuests(true, missing),
    }
    if not data.npc then
        missing.npc = "unknown_source"
    end
    if data.text == nil then
        missing.text = "not_ready"
    end
    FT.Emit("interaction.snapshot", data, event, "api_snapshot", nil, missing)
end

local function ClosedRun(questID)
    local entry = closed[questID]
    if entry and FT.Now() - entry.elapsed <= 30 then
        return entry
    end
    closed[questID] = nil
end

local function CloseRun(questID, run)
    if run then
        runs[questID] = nil
        runCount      = runCount - 1
        closed[questID] = { run = run, elapsed = FT.Now() }
    end
    local count = 0
    for id, entry in pairs(closed) do
        count = count + 1
        if FT.Now() - entry.elapsed > 30 or count > MAX_QUESTS then
            closed[id] = nil
        end
    end
    return closed[questID]
end

FT.On("QUEST_ACCEPTED", function(event, first, second)
    if not Enabled() then
        return
    end
    local argument = FT.Profile.quest_accepted_arg
    local questID
    if argument == 1 then
        questID = ContentID(first)
    elseif argument == 2 then
        questID = ContentID(second)
    end
    if not questID then
        return
    end
    local run = NewRun(questID, "accepted", event)
    if run then
        local npc, contextID, reference, dialogueNPC = EventContext(questID, "QUEST_DETAIL")
        run.origin = FT.Emit("quest.accepted", {
            quest_id = questID, quest_run_id = run.id, interaction_id = contextID,
            npc = npc, dialogue_npc = dialogueNPC,
        }, event, "direct_event", Related(reference), not npc and { npc = "unknown_source" } or nil)
        ScheduleScan(event)
    end
end)

FT.On("QUEST_TURNED_IN", function(event, rawQuestID, xpReward, moneyReward)
    if not Enabled() or not FT.Profile.quest_turned_in then
        return
    end
    local questID = ContentID(rawQuestID)
    if not questID then
        return
    end
    local recent                                 = ClosedRun(questID)
    local run                                    = runs[questID] or (recent and recent.run)
    local npc, contextID, reference, dialogueNPC = EventContext(questID, "QUEST_COMPLETE")
    local missing                                = {}
    if not run then
        missing.quest_run_id = "not_observed"
    end
    if not npc then
        missing.npc = "unknown_source"
    end
    local id = FT.Emit("quest.turned_in", {
        quest_id = questID, quest_run_id = run and run.id, xp_reward = FT.Value(xpReward, "number"),
        money_reward = FT.Value(moneyReward, "number"), interaction_id = contextID,
        npc = npc, dialogue_npc = dialogueNPC,
    }, event, "direct_event", Related(recent and recent.removal, reference),
        missing)
    if runs[questID] then
        recent = CloseRun(questID, run)
    end
    if recent then
        recent.turnin = id
    end
end)

FT.On("QUEST_REMOVED", function(event, rawQuestID, wasReplayQuest)
    if not Enabled() or not FT.Profile.quest_removed then
        return
    end
    local questID = ContentID(rawQuestID)
    if not questID then
        return
    end
    local recent = ClosedRun(questID)
    local run    = runs[questID] or (recent and recent.run)
    local id     = FT.Emit("quest.removed", {
        quest_id = questID, quest_run_id = run and run.id, reason = "unknown",
        was_replay_quest = FT.Value(wasReplayQuest, "boolean"),
    }, event, "direct_event", Related(recent and recent.turnin),
        not run and { quest_run_id = "not_observed" } or nil)
    if runs[questID] then
        recent = CloseRun(questID, run)
    end
    if recent then
        recent.removal = id
    end
end)

FT.On("QUEST_DATA_LOAD_RESULT", function(event, rawQuestID, rawSuccess)
    if not Enabled() or not FT.Profile.quest_data_load then
        return
    end
    local questID = ContentID(rawQuestID)
    local success = FT.Value(rawSuccess, "boolean")
    local request = questID and pending[questID]
    if not request or request.generation ~= generation or success == nil then
        return
    end
    if success then
        local title = FT.Value(FT.Call("C_QuestLog.GetTitleForQuestID", questID), "string")
        FT.Emit("quest.metadata", { quest_id = questID, title = title, load_success = success },
            event, "api_snapshot", request.references, not title and { title = "not_ready" } or nil)
        if title and pending[questID] == request then
            pending[questID] = nil
            pendingCount    = pendingCount - 1
        end
        ScheduleScan(event)
    end
end)

FT.On("QUEST_LOG_UPDATE", ScheduleScan)
FT.On("QUEST_WATCH_UPDATE", ScheduleScan)
FT.On("PLAYER_ENTERING_WORLD", ScheduleScan)
FT.On("FT_BASELINE", ScheduleScan)
FT.On("QUEST_DETAIL", Dialogue)
FT.On("QUEST_PROGRESS", Dialogue)
FT.On("QUEST_COMPLETE", Dialogue)
FT.On("GOSSIP_SHOW", Gossip)
FT.On("QUEST_GREETING", Greeting)

FT.On("QUEST_FINISHED", CloseInteraction)

FT.On("GOSSIP_CLOSED", function(event, continuing)
    if FT.Value(continuing, "boolean") ~= true then
        CloseInteraction()
    end
end)

FT.OnReset(function()
    generation    = generation + 1
    runs          = {}
    closed        = {}
    pending       = {}
    runCount      = 0
    pendingCount  = 0
    interaction   = nil
    dialogue      = nil
    lastScanState = nil
    capacityNoted = false
end)
