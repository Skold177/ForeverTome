local function setup(h)
    local e = h.env
    e.Enum  = e.Enum or {}
    e.Enum.SpellBookSpellBank = { Player = 0, Pet = 1 }
    e.Enum.SpellBookItemType  = { None = 0, Spell = 1, FutureSpell = 2, PetAction = 3, Flyout = 4 }
    e.C_SpellBook = {}
    h.state.spellbook = {
        { actionID = 101, spellID = 101, itemType = 1, isPassive = true, isOffSpec = false, name = "Quiet Focus", subName = "Passive", iconID = 9101 },
        { actionID = 102, spellID = 102, itemType = 2, isPassive = false, isOffSpec = false, name = "Future Flame", subName = "Rank 2", iconID = 9102 },
        { actionID = 103, spellID = 104, itemType = 1, isPassive = false, isOffSpec = true, name = "Overridden", subName = "", iconID = 9103 },
        { actionID = 777, itemType = 4, isPassive = false, isOffSpec = false, name = "Travel", subName = "", iconID = 9104 },
    }
    h.state.spellCost      = 50
    h.state.spellTextReady = true
    h.state.spellLoads     = 0
    e.C_SpellBook.GetNumSpellBookSkillLines = function()
        return 1
    end
    e.C_SpellBook.GetSpellBookSkillLineInfo = function(index)
        assert(index == 1)
        return { name = "Class", iconID = 1, itemIndexOffset = 0,
            numSpellBookItems = #h.state.spellbook, isGuild = false, shouldHide = true }
    end
    e.C_SpellBook.GetSpellBookItemInfo = function(slot, bank)
        if bank == 1 then
            return { actionID = 107, spellID = 107, itemType = 1, name = "Pet Bite", subName = "", iconID = 1,
                isPassive = false, isOffSpec = false }
        end
        assert(bank == 0)
        return h.state.spellbook[slot]
    end
    e.C_SpellBook.HasPetSpells = function()
        return 1, "PET"
    end
    e.C_SpellBook.GetSpellBookItemLevelLearned = function(slot)
        return slot == 2 and 40 or 1
    end
    e.C_SpellBook.IsSpellBookItemLowRank = function(slot)
        return slot == 3
    end
    e.C_SpellBook.IsSpellBookItemLooseFlyoutMember = function()
        return false
    end
    e.C_SpellBook.IsSpellKnown = function(id)
        return id ~= 102
    end
    e.C_SpellBook.FindBaseSpellByID = function(id)
        return id == 104 and 103 or id
    end
    e.C_SpellBook.FindSpellOverrideByID = function(id)
        return id == 103 and 104 or id
    end
    e.GetFlyoutInfo = function(id)
        assert(id == 777)
        return "Travel", "Known and future travel spells", 1, true
    end
    e.GetFlyoutSlotInfo = function(id, index)
        assert(id == 777 and index == 1)
        return 105, 106, false, "Unlearned travel", 2
    end
    e.C_Spell.GetSpellInfo = function(id)
        return { name = "Spell " .. id, spellID = id, iconID = id + 1, originalIconID = id + 2,
            castTime = 1500, minRange = 0, maxRange = 40 }
    end
    e.C_Spell.GetSpellDescription = function(id)
        return h.state.spellTextReady and "Description " .. id or ""
    end
    e.C_Spell.GetSpellSubtext = function()
        return "Rank 1"
    end
    e.C_Spell.IsSpellPassive = function(id)
        return id == 101
    end
    e.C_Spell.GetSpellPowerCost = function()
        return { { type = 0, name = "MANA", cost = h.state.spellCost, minCost = 50,
            costPercent = 10, costPerSec = 0, requiredAuraID = 0, hasRequiredAura = false } }
    end
    e.C_Spell.GetSpellCooldown = function()
        return { startTime = 95, duration = 10, isEnabled = true, isActive = true, modRate = 1 }
    end
    e.C_Spell.GetSpellCharges = function()
        return { currentCharges = 1, maxCharges = 2, cooldownStartTime = 95, cooldownDuration = 10,
            chargeModRate = 1, isActive = true }
    end
    e.C_Spell.RequestLoadSpellData = function()
        h.state.spellLoads = h.state.spellLoads + 1
    end
end

local function entries(h, bank)
    local result = {}
    for _, record in ipairs(h:records("spellbook.snapshot")) do
        if record.data.bank == bank then
            for _, entry in ipairs(record.data.entries or {}) do
                result[#result + 1] = entry
            end
        end
    end
    return result
end

local suite = {
    { name = "negative client cast-time sentinels stay separate from valid zero and fractional durations", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local original = h.env.C_Spell.GetSpellInfo
        h.env.C_Spell.GetSpellInfo = function(id)
            local data    = original(id)
            data.castTime = h.state.reportedCastTime
            return data
        end
        for index, duration in ipairs({ -1000000, 0, 1.25 }) do
            h.state.reportedCastTime = duration
            h.FT.RequestSpell(800 + index)
            h:advance(0.3)
            local metadata = h:last("spell.metadata")
            if duration < 0 then
                assert(metadata.data.castTime == nil and metadata.data.reported_cast_time_ms == duration)
                assert(metadata.data.cast_time_status == "invalid_result")
                assert(metadata.missing_fields["data.castTime"] == "invalid_result")
            else
                assert(metadata.data.castTime == duration and metadata.data.reported_cast_time_ms == nil)
                assert(metadata.data.cast_time_status == "available")
                assert(metadata.missing_fields["data.castTime"] == nil)
            end
        end
        h:assertHealthy()
    end },
    { name = "spell tooltips retain damage text alongside cast time mana range and current cooldowns", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.state.spellCost = 0
        h.env.GameTooltip = setmetatable({}, { __index = function()
            error("visible tooltip must not be touched")
        end })
        h.env.C_TooltipInfo = { GetSpellByID = function(id, isPet, showSubtext, dontOverride)
            assert(id == 800 and isPet == nil and showSubtext == true and dontOverride == true)
            return { lines = {
                { type = 0, leftText = "0 Mana", rightText = "40 yd range" },
                { type = 0, leftText = "1.5 sec cast" },
                { type = 0, leftText = "Deals 12 to 18 Fire damage over 6 sec." },
            } }
        end }
        h.env.C_Spell.GetSpellDescription = function()
            return "Deals 12 to 18 Fire damage over 6 sec."
        end
        h:event("UNIT_SPELLCAST_SUCCEEDED", "player", "synthetic-cast", 800)
        local source = h:last("spell.succeeded")
        h:advance(0.3)
        local metadata = h:last("spell.metadata")
        assert(metadata.data.spell_id == 800 and metadata.data.castTime == 1500)
        assert(metadata.data.minRange == 0 and metadata.data.maxRange == 40)
        assert(metadata.data.current_state.power_costs[1].cost == 0)
        assert(metadata.data.current_state.power_costs[1].costPerSec == 0)
        assert(metadata.data.current_state.cooldown.duration == 10)
        assert(metadata.data.current_state.charges.currentCharges == 1)
        assert(metadata.data.tooltip_status == "available")
        assert(metadata.data.tooltip_method == "C_TooltipInfo.GetSpellByID")
        assert(metadata.data.tooltip_context == "character_at_observation")
        assert(metadata.data.tooltip_lines[3].left_text == "Deals 12 to 18 Fire damage over 6 sec.")
        assert(metadata.data.tooltip_lines[1].type == 0 and metadata.data.tooltip_lines[1].index == 1)
        assert(metadata.data.damage == nil and metadata.data.base_cooldown_ms == nil)
        assert(metadata.related_observation_ids[1] == source.observation_id)
        h:assertHealthy()
    end },
    { name = "spell tooltips distinguish missing and readable empty data with immutable enrichment", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.env.C_TooltipInfo = { GetSpellByID = function()
            return h.state.spellTooltip
        end }
        h.FT.RequestSpell(800)
        h:advance(0.2)
        local first = h:last("spell.metadata")
        assert(first.data.tooltip_lines == nil and first.data.tooltip_status == "unavailable")
        assert(first.data.text_status == "available")
        assert(first.missing_fields["data.tooltip_lines"] == "not_ready_or_restricted")
        local before = #h:records("spell.metadata")
        h.state.spellTooltip = { lines = {} }
        h:event("SPELL_TEXT_UPDATE", 800)
        h:advance(0.3)
        local final = h:last("spell.metadata")
        assert(#h:records("spell.metadata") == before + 1)
        assert(final.data.tooltip_status == "available" and #final.data.tooltip_lines == 0)
        assert(final.missing_fields["data.tooltip_lines"] == nil)
        assert(first.data.tooltip_lines == nil and first.data.tooltip_status == "unavailable")
        assert(h.FT.SpellStatus().pending == 0)
        h:assertHealthy()
    end },
    { name = "spell tooltip sanitization bounds lines and rejects secret malformed and oversized fields", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local lines = {}
        for index = 1, 65 do
            lines[index] = { type = 0, leftText = "Line " .. index }
        end
        lines[1] = { type = 0, leftText = { secret = true }, rightText = "Readable side" }
        lines[2] = { type = 0, leftText = string.rep("x", 1025) }
        lines[3] = { type = { secret = true }, leftText = "Readable text" }
        lines[4] = { secret = true }
        lines[5] = { type = math.huge, leftText = 7, rightText = "Valid" }
        h.env.C_TooltipInfo = { GetSpellByID = function()
            return { lines = lines }
        end }
        h.FT.RequestSpell(800)
        h:advance(0.3)
        local data = h:last("spell.metadata").data
        assert(data.tooltip_status == "partial" and #data.tooltip_lines == 63)
        assert(data.tooltip_lines[1].left_text == nil and data.tooltip_lines[1].right_text == "Readable side")
        assert(data.tooltip_lines[2].left_text == nil and data.tooltip_lines[2].type == 0)
        assert(data.tooltip_lines[3].type == nil and data.tooltip_lines[3].left_text == "Readable text")
        assert(data.tooltip_lines[4].index == 5 and data.tooltip_lines[4].right_text == "Valid")
        assert(data.tooltip_lines[63].index == 64)
        assert(h:last("spell.metadata").missing_fields["data.tooltip_lines"] == "capacity_limit")
        assert(h.FT.SpellStatus().pending == 0)
        h:assertHealthy()
    end },
    { name = "unreadable spell tooltips exhaust three reads without mislabeling available description", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local reads = 0
        h.env.C_TooltipInfo = { GetSpellByID = function()
            reads = reads + 1
            return { secret = true }
        end }
        h.FT.RequestSpell(800)
        h:advance(8)
        assert(reads == 3 and h.FT.SpellStatus().pending == 0)
        assert(h.state.spellLoads == 2)
        local metadata    = h:last("spell.metadata")
        local unavailable = h:last("spell.metadata_unavailable")
        assert(metadata.data.text_status == "available" and metadata.data.tooltip_status == "unavailable")
        assert(metadata.data.tooltip_lines == nil and metadata.data.description == "Description 800")
        assert(unavailable.data.reason == "tooltip_not_ready_after_retries" and unavailable.data.attempts == 3)
        assert(unavailable.missing_fields["data.description"] == nil)
        assert(unavailable.missing_fields["data.tooltip_lines"] == "not_ready")
        h:advance(20)
        assert(reads == 3)
        h:assertHealthy()
    end },
    { name = "spell tooltip reads require supported profile API and a validated numeric spell ID", run = function(Host)
        for _, disabled in ipairs({ false, true }) do
            local h = Host.new()
            setup(h)
            h:start()
            h:advance(2)
            if disabled then
                h.env.C_TooltipInfo = { GetSpellByID = function()
                    error("profile-disabled tooltip API called")
                end }
                h.FT.Profile.spell_tooltips = false
            end
            h.FT.RequestSpell(800)
            h:advance(0.3)
            local metadata = h:last("spell.metadata")
            assert(metadata.data.tooltip_status == "unsupported" and metadata.data.tooltip_lines == nil)
            assert(metadata.missing_fields["data.tooltip_lines"] == "unsupported")
            local count = #h:records("spell.metadata")
            for _, id in ipairs({ 0, -1, 1.5, math.huge, "800", { secret = true } }) do
                h.FT.RequestSpell(id)
            end
            h:advance(8)
            assert(#h:records("spell.metadata") == count and h.FT.SpellStatus().pending == 0)
            h:assertHealthy()
        end
    end },
    { name = "full book retains passive future offspec overrides flyouts and pet spells", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local player = entries(h, "player")
        local pet    = entries(h, "pet")
        assert(#player == 4 and #pet == 1)
        assert(player[1].isPassive == true and player[1].is_known == true)
        assert(player[2].item_type == "FutureSpell" and player[2].is_known == false and player[2].levelLearned == 40)
        assert(player[3].actionID == 103 and player[3].spellID == 104 and player[3].isOffSpec == true)
        assert(player[3].is_low_rank == true)
        assert(player[4].flyout_slots[1].spell_id == 105 and player[4].flyout_slots[1].is_known == false)
        assert(pet[1].spellID == 107)
        local seen = {}
        for _, record in ipairs(h:records("spell.metadata")) do
            seen[record.data.spell_id] = true
            assert(record.related_observation_ids[1] ~= nil)
            assert(record.data.current_state.power_costs[1].cost == 50)
            assert(record.data.current_state.cooldown.duration == 10)
            assert(record.data.base_cooldown_ms == nil and record.data.base_cooldown_status == "unsupported_client_contract")
        end
        for id = 101, 107 do
            assert(seen[id], "Missing observed spell " .. id)
        end
        assert(not seen[777], "Flyout ID was treated as a spell")
        assert(h:last("spellbook.scan").data.completeness == "complete")
        assert(#h:records("spell.learned") == 0)
        h:assertHealthy()
    end },
    { name = "manual dumps refresh contextual costs and keep scheduled scans visible", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local before = #h:records("spell.metadata")
        h.state.spellCost = 17
        h.env.SlashCmdList.FOREVERTOME("dump")
        assert(h.FT.SpellStatus().scanning)
        h:advance(2)
        assert(#h:records("spell.metadata") > before)
        assert(h:last("spell.metadata").data.current_state.power_costs[1].cost == 17)
        assert(h:last("spellbook.scan").capture.method == "manual_catalog")
        assert(not h.FT.SpellStatus().scanning and h.FT.SpellStatus().pending == 0)
        h:assertHealthy()
    end },
    { name = "late spell text preserves origin and immutable earlier records", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.state.spellTextReady = false
        local source = h.FT.Emit("spell.succeeded", { spell_id = 800 }, "UNIT_SPELLCAST_SUCCEEDED", "direct_event")
        h.FT.RequestSpell(800, source)
        h:advance(0.2)
        local first = h:last("spell.metadata")
        assert(first.data.spell_id == 800 and first.data.description == "")
        local origin = first.data.metadata_origin.location.x
        h.state.x              = 0.8
        h.state.spellTextReady  = true
        h:event("SPELL_TEXT_UPDATE", 800)
        h:advance(0.3)
        local last = h:last("spell.metadata")
        assert(last.data.spell_id == 800 and last.data.description == "Description 800")
        assert(last.related_observation_ids[1] == source)
        assert(last.data.metadata_origin.location.x == origin and last.location.x == 0.8)
        assert(first.data.description == "" and first.data.text_status == "pending")
        assert(h.FT.SpellStatus().pending == 0)
        h:assertHealthy()
    end },
    { name = "metadata retries terminate then late successful loads can resolve text", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.state.spellTextReady = false
        h.FT.RequestSpell(810, nil)
        h:advance(8)
        assert(h.FT.SpellStatus().pending == 0 and h.state.spellLoads == 2)
        assert(h:last("spell.metadata_unavailable").data.spell_id == 810)
        assert(h:last("spell.metadata_unavailable").data.attempts == 3)
        h:event("SPELL_DATA_LOAD_RESULT", 99999, true)
        assert(h.FT.SpellStatus().pending == 0)
        h.state.spellTextReady = true
        h:event("SPELL_DATA_LOAD_RESULT", 810, true)
        h:advance(0.3)
        assert(h:last("spell.metadata").data.spell_id == 810)
        assert(h:last("spell.metadata").data.text_status == "available")
        h:assertHealthy()
    end },
    { name = "secret state and missing APIs remain unknown rather than empty lists", run = function(Host)
        local h = Host.new()
        setup(h)
        h.env.C_SpellBook.HasPetSpells = nil
        h.env.C_Spell.GetSpellPowerCost = function()
            return { secret = true }
        end
        h.env.C_Spell.GetSpellCharges = function()
            return { currentCharges = { secret = true }, maxCharges = 2 }
        end
        h:start()
        h:advance(2)
        local pet = h:records("spellbook.snapshot")[2]
        assert(pet.data.bank == "pet" and pet.data.bank_status == "unavailable" and pet.data.entries == nil)
        assert(h:last("spellbook.scan").data.pet_count == nil)
        assert(h:last("spellbook.scan").data.completeness == "partial")
        local metadata = h:last("spell.metadata")
        assert(metadata.data.current_state.power_costs == nil)
        assert(metadata.missing_fields["data.current_state.power_costs"] ~= nil)
        assert(metadata.data.current_state.charges.currentCharges == nil)
        assert(metadata.data.current_state.charges.maxCharges == 2)
        h:assertHealthy()
    end },
    { name = "known empty pet book is distinct from unavailable pet book", run = function(Host)
        local h = Host.new()
        setup(h)
        h.env.C_SpellBook.HasPetSpells = function()
            return nil
        end
        h:start()
        h:advance(2)
        local pet = h:records("spellbook.snapshot")[2]
        assert(pet.data.bank_status == "available" and #pet.data.entries == 0)
        assert(h:last("spellbook.scan").data.pet_count == 0)
        assert(h:last("spellbook.scan").data.completeness == "complete")
        h:assertHealthy()
    end },
    { name = "membership changes never invent learning and gaps reset comparisons", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.state.spellbook[1].spellID = 108
        h:event("SPELLS_CHANGED")
        h:advance(2)
        local delta = h:last("spellbook.changed")
        assert(delta.data.added_spell_ids[1] == 108 and delta.data.removed_spell_ids[1] == 101)
        assert(delta.evidence.method == "snapshot_difference" and #h:records("spell.learned") == 0)
        h.FT.Pause(true)
        h.state.spellbook[1].spellID = 109
        h.FT.Pause(false)
        h:advance(2)
        assert(#h:records("spellbook.changed") == 1)
        h:event("LEARNED_SPELL_IN_SKILL_LINE", 109, 1, false)
        assert(h:last("spell.learned").data.spell_id == 109)
        assert(h:last("spell.learned").evidence.method == "direct_event")
        h:assertHealthy()
    end },
    { name = "mid scan events invalidate comparisons without fabricated game events", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        h.FT.Dispatch("FT_CATALOG")
        h:advance(0.4)
        h:event("PET_BAR_UPDATE")
        h:advance(2)
        local partial
        for _, record in ipairs(h:records("spellbook.scan")) do
            if record.data.completeness == "partial" then
                partial = record
            end
            assert(record.capture.event ~= "SPELLS_CHANGED")
        end
        assert(partial and partial.missing_fields["data.entries"] == "changed_during_scan")
        assert(h:last("spellbook.scan").capture.method == "spellbook_rescan")
        assert(h:last("spellbook.scan").data.completeness == "complete")
        h:assertHealthy()
    end },
    { name = "zone changes preserve pending cast origins and avoid catalog duplication", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        local before = #h:records("spellbook.snapshot")
        h.state.spellTextReady = false
        local source = h.FT.Emit("spell.succeeded", { spell_id = 830 }, "UNIT_SPELLCAST_SUCCEEDED", "direct_event")
        h.FT.RequestSpell(830, source)
        h:advance(0.2)
        h:event("ZONE_CHANGED")
        h.state.spellTextReady = true
        h:event("SPELL_TEXT_UPDATE", 830)
        h:advance(2)
        assert(#h:records("spellbook.snapshot") == before)
        local last = h:last("spell.metadata")
        assert(last.data.spell_id == 830 and last.related_observation_ids[1] == source)
        assert(h.FT.SpellStatus().pending == 0)
        h:assertHealthy()
    end },
    { name = "request queue cap is explicit and worker CPU is bounded", run = function(Host)
        local h = Host.new()
        setup(h)
        h:start()
        h:advance(2)
        for id = 10000, 11030 do
            h.FT.RequestSpell(id, nil)
        end
        assert(h.FT.SpellStatus().pending == 1024)
        assert(h.FT.SpellStatus().metadata_dropped == 7)
        assert(h:last("spell.metadata_unavailable").data.reason == "capacity_limit")
        local before = #h:records("spell.metadata")
        h:advance(0.11)
        local after = #h:records("spell.metadata")
        assert(after > before and after - before <= 8)
        assert(h.FT.Clear())
        h:event("SPELL_DATA_LOAD_RESULT", 11000, true)
        h:advance(0.5)
        assert(#h:records("spell.metadata") == 0)
        h:assertHealthy()
    end },
}

suite.setup = setup
return suite
