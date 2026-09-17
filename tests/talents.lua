local function setup(h, count)
    local state = { config_id = 5, staged = false, nodes = {}, requests = {}, node_ids = {} }
    local e     = h.env
    for index = 1, count or 2 do
        state.node_ids[index] = index
        state.nodes[index] = {
            ID = index, posX = index * 100, posY = index * 200, flags = 0,
            entryIDs = { 100 + index }, entryIDsWithCommittedRanks = index == 1 and { 101 } or {},
            canPurchaseRank = true, canRefundRank = index == 1, isAvailable = true,
            isVisible = true, isDisplayError = false, ranksPurchased = index == 1 and 1 or 0,
            ranksIncreased = 0, entryIDToRanksIncreased = { [100 + index] = 0 },
            activeRank = index == 1 and 1 or 0, currentRank = index == 1 and 1 or 0,
            activeEntry = index == 1 and { entryID = 101, rank = 1 } or nil,
            maxRanks = 2, totalMaxRanks = 2, type = 0,
            visibleEdges = index == 1 and { { targetNode = 2, type = 1, visualStyle = 2, isActive = true } } or {},
            meetsEdgeRequirements = true, groupIDs = { 77 }, conditionIDs = { 50 },
            isCascadeRepurchasable = false,
        }
    end
    e.C_ClassTalents = {
        GetActiveConfigID = function()
            return state.config_id
        end,
    }
    e.C_Traits = {
        GetConfigInfo = function(id)
            return { ID = id, type = 1, name = "Private loadout title", treeIDs = { 8 }, usesSharedActionBars = true }
        end,
        ConfigHasStagedChanges = function()
            return state.staged
        end,
        GetTreeInfo = function(_, id)
            return { ID = id, gates = { { topLeftNodeID = 2, conditionID = 50 } },
                hideSingleRankNumbers = false, cannotRefund = false, rootNodeID = 1,
                uiTextureKit = "mage", titleText = "Synthetic class tree" }
        end,
        GetTreeNodes = function()
            return state.node_ids
        end,
        GetTreeHash = function()
            return { 0, 42, 255 }
        end,
        GetTreeCurrencyInfo = function(_, _, excludeStaged)
            assert(excludeStaged == true)
            return { { traitCurrencyID = 3, quantity = 4, spent = 1, maxQuantity = 5 } }
        end,
        GetGroupDisplayInfoByTreeID = function()
            return { { groupID = 77, treeID = 8, skillLineID = 237, orderIndex = 1, displayName = "Arcane", icon = 999 } }
        end,
        GetNodeInfo = function(_, id)
            return state.nodes[id]
        end,
        GetNodeCost = function()
            return { { ID = 3, amount = 1 } }
        end,
        GetEntryInfo = function(_, id)
            return { definitionID = id + 100, type = 0, maxRanks = 2, isAvailable = true, isDisplayError = false, conditionIDs = { 50 } }
        end,
        GetDefinitionInfo = function(id)
            return { spellID = id + 1000, overrideName = "Talent " .. id, overrideIcon = 500 }
        end,
        GetConditionInfo = function(id, conditionID)
            assert(id == state.config_id and conditionID == 50)
            return { condID = 50, isAlwaysMet = false, isMet = true, isGate = true,
                isSufficient = false, type = 1, playerLevel = 10, traitCurrencyID = 3,
                spentAmountRequired = 1, tooltipFormat = "Spend %d points" }
        end,
        GetTraitDescription = function(id, rank)
            return "Talent " .. id .. " rank " .. rank
        end,
    }
    h.FT.RequestSpell = function(id, related, force)
        state.requests[#state.requests + 1] = { spell_id = id, related = related, force = force }
    end
    return state
end

local function findMetadata(h, entity, id)
    local found
    for _, observation in ipairs(h:records("talent.metadata")) do
        if observation.data.entity_type == entity and observation.data.entity_id == id then
            found = observation
        end
    end
    return found
end

local suite = {
    { name = "class tree includes unselected entries ranks dependencies groups and spell references", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        h:start()
        h:advance(1)
        local snapshot = h:last("talent.snapshot")
        assert(snapshot.data.completeness == "complete" and snapshot.data.node_count == 2)
        assert(snapshot.data.has_staged_changes == false)
        assert(findMetadata(h, "config", 5).data.info.name == nil)
        local nodeInfo = findMetadata(h, "node", 1).data.info
        assert(nodeInfo.posX == 100 and nodeInfo.posY == 200)
        assert(nodeInfo.visibleEdges[1].targetNode == 2 and nodeInfo.costs[1].amount == 1)
        assert(findMetadata(h, "node", 2).data.info.ranksPurchased == 0)
        assert(findMetadata(h, "entry", 102).data.info.definitionID == 202)
        assert(findMetadata(h, "condition", 50).data.info.playerLevel == 10)
        assert(findMetadata(h, "group", 77).data.info.displayName == "Arcane")
        assert(#h:records("talent.rank") == 4 and #state.requests == 2)
        assert(state.requests[2].spell_id == 1202 and state.requests[2].related)
        assert(h.FT.TalentStatus().scanning == false)
        h:assertHealthy()
    end },
    { name = "unchanged events deduplicate metadata and manual dumps emit fresh build chunks", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(1)
        local metadataCount = #h:records("talent.metadata")
        local first         = h:last("talent.snapshot")
        h:event("TRAIT_NODE_CHANGED", 1)
        h:advance(1)
        assert(#h:records("talent.snapshot") == 1)
        h.FT.Dispatch("FT_CATALOG")
        h:advance(1)
        assert(#h:records("talent.snapshot") == 2)
        assert(#h:records("talent.metadata") == metadataCount)
        assert(h:last("talent.snapshot").data.previous_snapshot_id == first.observation_id)
        assert(h:last("talent.snapshot").capture.method == "manual_catalog")
        assert(h:last("talent.build").data.nodes[1].node_observation_id)
        local saved = h.FT.Export()
        local again = Host.new(saved)
        setup(again)
        again:start()
        assert(again.FT.Status().initialized and not again.FT.Status().blocked)
        h:assertHealthy()
    end },
    { name = "changed selections retain earlier builds and distinguish staged changes", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        h:start()
        h:advance(1)
        state.nodes[2].ranksPurchased = 1
        state.nodes[2].currentRank    = 1
        state.nodes[2].activeEntry    = { entryID = 102, rank = 1 }
        state.staged                 = true
        h:event("TRAIT_NODE_CHANGED_PARTIAL", 2, {})
        h:advance(1)
        local builds = h:records("talent.build")
        assert(#builds == 2 and builds[1].data.nodes[2].ranks_purchased == 0)
        assert(builds[2].data.nodes[2].ranks_purchased == 1)
        assert(#builds[2].data.nodes[2].committed_entry_ids == 0)
        assert(h:last("talent.snapshot").data.has_staged_changes == true)
        h:assertHealthy()
    end },
    { name = "secret fields and missing nodes stay partial without invented zero ranks", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        state.nodes[1].posX = { secret = true }
        state.nodes[2]      = { secret = true }
        h:start()
        h:advance(1)
        local snapshot = h:last("talent.snapshot")
        local nodeInfo = findMetadata(h, "node", 1)
        assert(snapshot.data.completeness == "partial")
        assert(nodeInfo.data.info.posX == nil and nodeInfo.missing_fields["data.info.posX"])
        assert(h:last("talent.build").data.nodes[2].ranks_purchased == nil)
        assert(h.FT.TalentStatus().completeness == "partial")
        h:assertHealthy()
    end },
    { name = "partial scans do not replace complete build history and recovery emits a baseline", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        h:start()
        h:advance(1)
        local savedNode = state.nodes[2]
        state.nodes[2] = nil
        h:event("TRAIT_CONFIG_UPDATED", 5)
        h:advance(1)
        assert(h:last("talent.snapshot").data.completeness == "partial")
        state.nodes[2] = savedNode
        h:event("TRAIT_CONFIG_UPDATED", 5)
        h:advance(1)
        assert(#h:records("talent.snapshot") == 3)
        assert(h:last("talent.snapshot").data.completeness == "complete")
        assert(h:last("talent.build").data.nodes[2].ranks_purchased == 0)
        h:assertHealthy()
    end },
    { name = "configuration changes during a scan mark it inconsistent then rescan", run = function(Host)
        local h     = Host.new()
        local state = setup(h, 12)
        h:start()
        h:advance(1)
        h.FT.CaptureTalents({ method = "catalog_scan" })
        state.config_id = 6
        h:event("ACTIVE_COMBAT_CONFIG_CHANGED", 6)
        h:advance(2)
        local snapshots = h:records("talent.snapshot")
        assert(snapshots[2].data.config_id == 5 and snapshots[2].data.completeness == "partial")
        assert(snapshots[2].missing_fields["data.consistency"] == "changed_during_scan")
        assert(snapshots[3].data.config_id == 6 and snapshots[3].data.completeness == "complete")
        h:assertHealthy()
    end },
    { name = "large trees are emitted in bounded build chunks", run = function(Host)
        local h = Host.new()
        setup(h, 65)
        h:start()
        h:advance(8)
        local builds = h:records("talent.build")
        assert(#builds == 3 and #builds[1].data.nodes == 32 and #builds[3].data.nodes == 1)
        assert(h:last("talent.snapshot").data.node_count == 65)
        assert(h:last("talent.snapshot").data.completeness == "complete")
        assert(h:last("talent.snapshot").data.chunk_count == 3)
        h:assertHealthy()
    end },
    { name = "clear discards stale metadata references and captures all talent data again", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(1)
        local before = #h:records("talent.metadata")
        local oldID  = h:last("talent.build").data.nodes[1].node_observation_id
        assert(h.FT.Clear())
        h.FT.Dispatch("FT_BASELINE")
        h:advance(1)
        assert(#h:records("talent.metadata") == before)
        assert(h:last("talent.build").data.nodes[1].node_observation_id ~= oldID)
        local again = Host.new(h.FT.Export())
        setup(again)
        again:start()
        assert(again.FT.Status().initialized and not again.FT.Status().blocked)
        h:assertHealthy()
    end },
    { name = "missing active config emits an explicit unavailable snapshot", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        state.config_id = nil
        h:start()
        h:advance(1)
        assert(h:last("talent.snapshot").data.completeness == "partial")
        assert(h:last("talent.snapshot").missing_fields["data.config_id"])
        assert(#h:records("talent.build") == 0 and #h:records("talent.metadata") == 0)
        h:assertHealthy()
    end },
    { name = "API failures become missing metadata and never invoke mutations", run = function(Host)
        local h = Host.new()
        setup(h)
        h.env.C_Traits.GetDefinitionInfo = function()
            error("Not available")
        end
        h.env.C_ClassTalents.LoadConfig = function()
            error("Must never load another config")
        end
        h.env.C_Traits.PurchaseRank = function()
            error("Must never change a talent")
        end
        h:start()
        h:advance(1)
        assert(h:last("talent.snapshot").data.completeness == "partial")
        assert(findMetadata(h, "definition", 201).missing_fields["data.info"])
        h:assertHealthy()
    end },
    { name = "unavailable lists are omitted and never asserted empty", run = function(Host)
        local h = Host.new()
        setup(h)
        h.env.C_Traits.GetConfigInfo = function()
            return { ID = 5, type = 1, usesSharedActionBars = true, treeIDs = { secret = true } }
        end
        h:start()
        h:advance(1)
        assert(findMetadata(h, "config", 5).data.info.treeIDs == nil)
        assert(h:last("talent.snapshot").data.tree_ids == nil)
        assert(h:last("talent.snapshot").data.expected_node_count == nil)
        assert(h:last("talent.snapshot").data.completeness == "partial")
        h:assertHealthy()
    end },
    { name = "scan status includes scheduled requests and pause cancels them", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(1)
        h.FT.Dispatch("FT_CATALOG")
        assert(h.FT.TalentStatus().scanning)
        h.FT.Pause(true)
        assert(not h.FT.TalentStatus().scanning)
        h:advance(1)
        assert(#h:records("talent.snapshot") == 1)
        h.FT.Pause(false)
        h:advance(1)
        assert(#h:records("talent.snapshot") == 2)
        h:assertHealthy()
    end },
    { name = "world transitions reuse static metadata and establish a fresh build", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(1)
        local count = #h:records("talent.metadata")
        h:event("PLAYER_LEAVING_WORLD")
        h:event("PLAYER_ENTERING_WORLD", false, false)
        h:advance(1)
        assert(#h:records("talent.metadata") == count)
        assert(#h:records("talent.snapshot") == 2)
        h:assertHealthy()
    end },
    { name = "storage and invalid record resets stop scans without swallowed failures", run = function(Host)
        for _, mode in ipairs({ "capacity", "invalid" }) do
            local h = Host.new()
            setup(h)
            h:start()
            h:advance(1)
            h.FT.ResetCollectors("user_clear")
            if mode == "capacity" then
                h.FT.LIMITS.records = h.FT.Status().records + 2
            else
                h.FT.LIMITS.record_bytes = 200
            end
            h.FT.CaptureTalents({ method = "catalog_scan" })
            assert(not h.FT.TalentStatus().scanning)
            h:assertHealthy()
        end
    end },
    { name = "unverified client profiles do not request talent APIs", run = function(Host)
        local h = Host.new(nil, "1.60.2", "unknown")
        setup(h)
        h.env.C_ClassTalents.GetActiveConfigID = function()
            error("Unsupported client must not query talents")
        end
        h:start()
        h.FT.Dispatch("FT_CATALOG")
        h:advance(1)
        assert(#h:records("talent.snapshot") == 0)
        assert(not h.FT.TalentStatus().scanning)
        h:assertHealthy()
    end },
    { name = "manual requests upgrade already queued automatic scans and spell refreshes", run = function(Host)
        local h     = Host.new()
        local state = setup(h)
        h:start()
        h:advance(1)
        h:event("TRAIT_NODE_CHANGED", 1)
        h.FT.Dispatch("FT_CATALOG")
        h:advance(1)
        assert(#h:records("talent.snapshot") == 2)
        assert(h:last("talent.snapshot").capture.method == "manual_catalog")
        assert(state.requests[#state.requests].force == true)
        h:assertHealthy()
    end },
    { name = "capacity resets at every tree phase stop without nil scan access", run = function(Host)
        for remaining = 0, 24 do
            local h = Host.new()
            setup(h)
            h.env.C_Traits.GetGroupDisplayInfoByTreeID = function()
                return {
                    { groupID = 77, treeID = 8, skillLineID = 237, orderIndex = 1, displayName = "Arcane", icon = 999 },
                    { groupID = 78, treeID = 8, skillLineID = 238, orderIndex = 2, displayName = "Fire", icon = 998 },
                }
            end
            h:start()
            h:advance(1)
            h.FT.ResetCollectors("user_clear")
            h.FT.LIMITS.records = h.FT.Status().records + remaining
            h.FT.CaptureTalents({ method = "catalog_scan" })
            h:advance(1)
            h:assertHealthy()
        end
    end },
}

suite.setup = setup
return suite
