import copy
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "export_saved_variables.py"
SPEC        = importlib.util.spec_from_file_location("forevertome_export", MODULE_PATH)
export      = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = export
SPEC.loader.exec_module(export)

IDENTITY = "0123456789abcdef0123456789abcdef"
FIXTURE  = r'''-- Saved after a normal logout. [1] comments match WoW output.
ForeverTomeDB = {
    ["schema_version"] = 1,
    ["synthetic"] = true,
    ["installation_id"] = "0123456789abcdef0123456789abcdef",
    ["next_session"] = 2,
    ["settings"] = { ["paused"] = false },
    ["record_count"] = 2,
    ["estimated_bytes"] = 1800,
    ["sessions"] = {
        {
            ["session"] = {
                ["session_id"] = "0123456789abcdef0123456789abcdef-1",
                ["product"] = "WF",
                ["client"] = { ["version"] = "1.60.1", ["build"] = "69893", ["locale"] = "enUS" },
                ["addon_version"] = "0.1.0",
                ["adapter_id"] = "forever-beta-69893-source-v1",
                ["capabilities"] = { ["quests"] = { ["status"] = "wf_unverified", ["enabled"] = true } },
            },
            ["observations"] = {
                {
                    ["session_id"] = "0123456789abcdef0123456789abcdef-1",
                    ["observation_id"] = "0123456789abcdef0123456789abcdef-1:1",
                    ["sequence"] = 1,
                    ["kind"] = "quest.dialogue",
                    ["elapsed_s"] = 0.25,
                    ["observed_at_server_s"] = 1790000000,
                    ["capture"] = { ["event"] = "QUEST_DETAIL" },
                    ["location"] = {
                        ["status"] = "available", ["subject"] = "player",
                        ["coordinate_system"] = "ui_map_normalized", ["ui_map_id"] = 42,
                        ["x"] = 0, ["y"] = 0.75,
                    },
                    ["data"] = {
                        ["quest_id"] = 123,
                        ["text"] = "Café — 森\nA \"quest\" and \\path; escaped caf\195\169",
                        ["choices"] = {}, ["rewards"] = {}, ["required_items"] = {},
                    },
                    ["evidence"] = { ["method"] = "api_snapshot" },
                    ["related_observation_ids"] = {},
                    ["missing_fields"] = {},
                }, -- [1]
                {
                    ["session_id"] = "0123456789abcdef0123456789abcdef-1",
                    ["observation_id"] = "0123456789abcdef0123456789abcdef-1:2",
                    ["sequence"] = 2,
                    ["kind"] = "quest.accepted",
                    ["elapsed_s"] = 1e1,
                    ["capture"] = { ["event"] = "QUEST_ACCEPTED" },
                    ["data"] = { ["quest_id"] = 123 },
                    ["evidence"] = { ["method"] = "direct_event" },
                    ["related_observation_ids"] = { "0123456789abcdef0123456789abcdef-1:1", },
                    ["missing_fields"] = {},
                }, -- [2]
            },
            ["diagnostics"] = { ["counts"] = {}, ["distinct"] = 0 },
        }, -- [1]
        {
            ["session"] = {
                ["session_id"] = "0123456789abcdef0123456789abcdef-2",
                ["product"] = "WF",
                ["client"] = { ["version"] = "1.60.1", ["build"] = "69893", ["locale"] = "frFR" },
                ["addon_version"] = "0.1.0",
                ["adapter_id"] = "forever-beta-69893-source-v1",
                ["capabilities"] = {},
            },
            ["observations"] = {},
            ["diagnostics"] = { ["counts"] = { ["api_error:UnitGUID"] = 2 }, ["distinct"] = 1 },
        }, -- [2]
    },
}
'''


class SavedVariablesTests(unittest.TestCase):
    def test_realistic_multisession_unicode_and_empty_shapes(self):
        database = export.parse_saved_variables(FIXTURE.encode("utf-8"))
        first    = database["sessions"][0]["observations"][0]
        self.assertEqual(first["data"]["text"], 'Café — 森\nA "quest" and \\path; escaped café')
        self.assertEqual(first["location"]["x"], 0)
        self.assertEqual(first["missing_fields"], {})
        self.assertEqual(first["related_observation_ids"], [])
        self.assertEqual(first["data"]["rewards"], [])
        self.assertEqual(database["sessions"][1]["observations"], [])
        self.assertEqual(database["sessions"][1]["session"]["capabilities"], {})
        self.assertTrue(database["synthetic"])

    def test_rejects_executable_content_without_running_it(self):
        expressions = ("os.execute('echo unsafe')", "function() end", "setmetatable({}, {})", "ForeverTomeDB", "1 + 2")
        for expression in expressions:
            with self.subTest(expression=expression), self.assertRaises(export.ExportError):
                export.parse_saved_variables(FIXTURE.replace('["record_count"] = 2', '["record_count"] = ' + expression))
        for suffix in ("os.execute('echo unsafe')", "ForeverTomeDB = {}", "return ForeverTomeDB"):
            with self.subTest(suffix=suffix), self.assertRaises(export.ExportError):
                export.parse_saved_variables(FIXTURE + suffix)

    def test_duplicate_keys_and_json_key_collisions(self):
        for mutation in (
            FIXTURE.replace('["record_count"] = 2,', '["record_count"] = 2, record_count = 2,'),
            FIXTURE.replace('["choices"] = {}', '["choices"] = { 1, [1] = 2 }'),
            FIXTURE.replace('["data"] = {', '["data"] = { [1] = true, ["1"] = false,', 1),
        ):
            with self.subTest(mutation=mutation[:80]), self.assertRaises(export.ExportError):
                export.parse_saved_variables(mutation)

    def test_file_string_depth_and_node_limits(self):
        for limits in (
            replace(export.Limits(), file_bytes=10),
            replace(export.Limits(), string_bytes=4),
            replace(export.Limits(), depth=3),
            replace(export.Limits(), nodes=20),
            replace(export.Limits(), sessions=1),
            replace(export.Limits(), observations=1),
        ):
            with self.subTest(limits=limits), self.assertRaises(export.ExportError):
                export.parse_saved_variables(FIXTURE, limits)

    def test_truncated_malformed_and_invalid_utf8_inputs(self):
        inputs = (
            FIXTURE[:-10], FIXTURE + "--[[unfinished", FIXTURE.replace('"69893"', '"\\999"'),
            FIXTURE.replace('"69893"', '"\\q"'), FIXTURE.replace('"69893"', '"unterminated'),
            FIXTURE.replace('["elapsed_s"] = 0.25', '["elapsed_s"] = 1e999'),
            FIXTURE.replace('["elapsed_s"] = 0.25', '["elapsed_s"] = ' + "9" * 1000),
            b"ForeverTomeDB = { text = '\xff' }", b"", "return {}",
        )
        for source in inputs:
            with self.subTest(source=str(source)[:50]), self.assertRaises(export.ExportError):
                export.parse_saved_variables(source)

    def test_schema_and_identity_failures(self):
        for mutation in (
            FIXTURE.replace('["schema_version"] = 1', '["schema_version"] = 2'),
            FIXTURE.replace('["kind"] = "quest.accepted"', '["kind"] = "future.kind"'),
            FIXTURE.replace('["record_count"] = 2', '["record_count"] = 3'),
            FIXTURE.replace('["sequence"] = 2', '["sequence"] = 3'),
            FIXTURE.replace('["elapsed_s"] = 1e1', '["elapsed_s"] = 0.1'),
            FIXTURE.replace('["x"] = 0', '["x"] = 1.5'),
            FIXTURE.replace('["related_observation_ids"] = {}', '["related_observation_ids"] = {"unknown"}'),
            FIXTURE.replace('["choices"] = {}', '["choices"] = {[2] = "gap"}'),
            FIXTURE.replace('["choices"] = {}', '["choices"] = false'),
            FIXTURE.replace('["choices"] = {}', '["choices"] = "malformed"'),
            FIXTURE.replace('["event"] = "QUEST_DETAIL"', '["event"] = 1'),
            FIXTURE.replace('["method"] = "api_snapshot"', '["method"] = ""'),
            FIXTURE.replace('["locale"] = "enUS"', '["locale"] = false'),
            FIXTURE.replace('["enabled"] = true', '["enabled"] = "yes"'),
        ):
            with self.subTest(mutation=mutation[:80]), self.assertRaises(export.ExportError):
                export.parse_saved_variables(mutation)

    def test_long_comments_long_strings_and_identifier_keys(self):
        source = FIXTURE.replace('-- Saved after a normal logout. [1] comments match WoW output.', '--[=[\nlong comment\n]=]')
        source = source.replace('["adapter_id"] = "forever-beta-69893-source-v1"', 'adapter_id = [=[forever-beta-69893-source-v1]=]')
        self.assertEqual(export.parse_saved_variables(source)["record_count"], 2)

    def test_catalog_arrays_preserve_empty_and_unavailable_shapes(self):
        source = FIXTURE.replace('"quest.dialogue"', '"talent.metadata"', 1)
        source = source.replace('["choices"] = {}', '''["choices"] = {},
            ["entity_type"] = "node", ["entity_id"] = 7,
            ["entryIDs"] = { 11, 12 }, ["visibleEdges"] = {},
            ["conditionIDs"] = {}, ["groupIDs"] = {},
            ["entryIDsWithCommittedRanks"] = {}, ["costs"] = {},
            ["subTreeSelectionNodeIDs"] = {}, ["tree_hash"] = {},
            ["info_status"] = "available"''', 1)
        database = export.parse_saved_variables(source)
        node     = database["sessions"][0]["observations"][0]["data"]
        self.assertEqual(node["entryIDs"], [11, 12])
        for field in ("visibleEdges", "conditionIDs", "groupIDs", "entryIDsWithCommittedRanks",
                      "costs", "subTreeSelectionNodeIDs", "tree_hash"):
            self.assertEqual(node[field], [], field)
        self.assertNotIn("nodeIDs", node)
        unavailable = FIXTURE.replace('"quest.dialogue"', '"spellbook.scan"', 1)
        unavailable = unavailable.replace('["choices"] = {}', '["choices"] = {}, ["completeness"] = "unavailable"', 1)
        scan        = export.parse_saved_variables(unavailable)["sessions"][0]["observations"][0]["data"]
        self.assertEqual(scan["completeness"], "unavailable")
        self.assertNotIn("entries", scan)
        self.assertNotIn("skill_lines", scan)

    def test_nested_missing_reasons_do_not_become_catalog_arrays(self):
        source = FIXTURE.replace('"quest.dialogue"', '"spellbook.snapshot"', 1)
        source = source.replace('["choices"] = {}', '''["choices"] = {}, ["entries"] = {
            { ["item_type"] = "Flyout", ["missing_fields"] = {
                ["flyout_slots"] = "not_ready_or_unsupported" } } }''', 1)
        database = export.parse_saved_variables(source)
        entry    = database["sessions"][0]["observations"][0]["data"]["entries"][0]
        self.assertNotIn("flyout_slots", entry)
        self.assertEqual(entry["missing_fields"], {"flyout_slots": "not_ready_or_unsupported"})
        for malformed in ('false', '{}', '{ "invalid" }'):
            with self.subTest(malformed=malformed), self.assertRaises(export.ExportError):
                export.parse_saved_variables(source.replace('"not_ready_or_unsupported"', malformed))

    def test_catalog_rejects_sparse_and_mixed_array_shapes(self):
        for field in ("treeIDs", "nodeIDs", "entryIDs", "visibleEdges", "nodes", "skill_lines",
                      "entries", "flyout_slots", "power_costs", "added_spell_ids", "removed_spell_ids"):
            for value in ('{ [2] = 12 }', '{ [1] = 12, status = "unavailable" }', 'false'):
                with self.subTest(field=field, value=value), self.assertRaises(export.ExportError):
                    source = FIXTURE.replace('["choices"] = {}', f'["choices"] = {{}}, ["{field}"] = {value}', 1)
                    export.parse_saved_variables(source)

    def test_cli_json_and_jsonl_preserve_source_and_original_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root   = Path(directory)
            source = root / "ForeverTome.lua"
            output = root / "export.json"
            lines  = root / "export.jsonl"
            source.write_text(FIXTURE, encoding="utf-8")
            before = source.read_bytes()
            self.assertEqual(export.main([str(source), "--output", str(output)]), 0)
            self.assertEqual(export.main([str(source), "--output", str(lines), "--format", "jsonl"]), 0)
            parsed  = json.loads(output.read_text(encoding="utf-8"))
            records = [json.loads(line) for line in lines.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(parsed, export.parse_saved_variables(before))
            self.assertEqual([row["observation"] for row in records if row["type"] == "observation"], parsed["sessions"][0]["observations"])
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(export.main([str(source), "--output", str(source)]), 1)
            self.assertEqual(export.main([str(source), "--output", str(output)]), 1)
            self.assertEqual(source.read_bytes(), before)

    def test_sqlite_idempotence_conflict_and_transaction_rollback(self):
        database = export.parse_saved_variables(FIXTURE)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "evidence.sqlite"
            self.assertEqual(export.import_sqlite(database, destination), 2)
            self.assertEqual(export.import_sqlite(database, destination), 0)
            changed = copy.deepcopy(database)
            changed["sessions"][0]["observations"][1]["data"]["quest_id"] = 999
            with self.assertRaisesRegex(export.ExportError, "Conflicting observation"):
                export.import_sqlite(changed, destination)
            changed["sessions"][0]["session"]["client"]["build"] = "other"
            with self.assertRaisesRegex(export.ExportError, "Conflicting session"):
                export.import_sqlite(changed, destination)
            changed = copy.deepcopy(database)
            fresh   = copy.deepcopy(changed["sessions"][1])
            fresh["session"]["session_id"] = IDENTITY + "-3"
            changed["sessions"].insert(0, fresh)
            changed["sessions"][1]["observations"][1]["data"]["quest_id"] = 999
            with self.assertRaises(export.ExportError):
                export.import_sqlite(changed, destination)
            with closing(sqlite3.connect(destination)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM ft_observations").fetchone()[0], 2)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM ft_sessions").fetchone()[0], 2)
                original = json.loads(connection.execute("SELECT record_json FROM ft_observations WHERE sequence = 2").fetchone()[0])
                self.assertEqual(original["data"]["quest_id"], 123)

    def test_actual_addon_reload_savedvariables_json_sqlite_round_trip(self):
        script = r'''
local Host = dofile("tests/support/host.lua")
local h    = Host.new()
local e    = h.env
e.Enum = {
    SpellBookSpellBank = { Player = 0, Pet = 1 },
    SpellBookItemType = { Spell = 1, FutureSpell = 2, PetAction = 3, Flyout = 4 },
}
e.C_SpellBook = {}
e.C_SpellBook.GetNumSpellBookSkillLines = function()
    return 1
end
e.C_SpellBook.GetSpellBookSkillLineInfo = function()
    return { name = "Synthetic spell category", iconID = 10, itemIndexOffset = 0,
        numSpellBookItems = 2, isGuild = false, shouldHide = false }
end
e.C_SpellBook.GetSpellBookItemInfo = function(slot, bank)
    assert(bank == 0)
    return { actionID = 1000 + slot, spellID = 1000 + slot, itemType = slot,
        isPassive = slot == 1, isOffSpec = false, name = "Spell " .. slot,
        subName = "Synthetic rank", iconID = 10 + slot, skillLineIndex = 1 }
end
e.C_SpellBook.IsSpellKnown = function(spellID)
    return spellID == 1001
end
e.C_SpellBook.GetSpellBookItemLevelLearned = function(slot)
    return slot == 1 and 1 or 60
end
e.C_SpellBook.HasPetSpells = function()
    return 0, "PET"
end
e.HasPetSpells = e.C_SpellBook.HasPetSpells
e.C_Spell.GetSpellInfo = function(spellID)
    return { spellID = spellID, name = "Spell " .. spellID, iconID = 10,
        originalIconID = 11, castTime = 0, minRange = 0, maxRange = 40 }
end
e.C_Spell.GetSpellDescription = function(spellID)
    return "Spell description " .. spellID
end
e.C_Spell.GetSpellPowerCost = function()
    return {}
end
e.C_Spell.GetSpellCooldown = function()
    return { startTime = 0, duration = 0, isEnabled = true, modRate = 1 }
end
e.C_Spell.IsSpellDataCached = function()
    return true
end
e.C_Spell.IsSpellPassive = function(spellID)
    return spellID == 1001
end
e.C_ClassTalents = {}
e.C_ClassTalents.GetActiveConfigID = function()
    return 7
end
e.C_Traits = {}
e.C_Traits.GetConfigInfo = function()
    return { ID = 7, type = 1, treeIDs = { 9 }, name = "PRIVATE_LOADOUT_NAME",
        usesSharedActionBars = false, characterName = "PRIVATE_CHARACTER_NAME" }
end
e.C_Traits.ConfigHasStagedChanges = function()
    return false
end
e.C_Traits.GetTreeInfo = function()
    return { ID = 9, gates = {}, rootNodeID = 11, hideSingleRankNumbers = false,
        cannotRefund = false, uiTextureKit = "synthetic", titleText = "Synthetic talents" }
end
e.C_Traits.GetTreeHash = function()
    return { 0, 1, 255 }
end
e.C_Traits.GetTreeNodes = function()
    return { 11, 12 }
end
e.C_Traits.GetTreeCurrencyInfo = function()
    return {}
end
e.C_Traits.GetGroupDisplayInfoByTreeID = function()
    return {}
end
e.C_Traits.GetNodeInfo = function(_, nodeID)
    local selected = nodeID == 11
    local entryID  = nodeID + 90
    return { ID = nodeID, posX = 100, posY = nodeID * 10, type = 0, flags = 0,
        entryIDs = { entryID }, entryIDsWithCommittedRanks = selected and { entryID } or {},
        activeEntry = selected and { entryID = entryID, rank = 1 } or nil,
        nextEntry = { entryID = entryID, rank = selected and 2 or 1 },
        currentRank = selected and 1 or 0, activeRank = selected and 1 or 0,
        ranksPurchased = selected and 1 or 0, ranksIncreased = 0, maxRanks = 2, totalMaxRanks = 2,
        entryIDToRanksIncreased = { [entryID] = 0 },
        canPurchaseRank = true, canRefundRank = selected, isAvailable = true, isVisible = true,
        isDisplayError = false, meetsEdgeRequirements = true, isCascadeRepurchasable = false,
        visibleEdges = selected and { { targetNode = 12, type = 1, visualStyle = 0, isActive = true } } or {},
        groupIDs = {}, conditionIDs = {} }
end
e.C_Traits.GetNodeCost = function()
    return {}
end
e.C_Traits.GetEntryInfo = function(_, entryID)
    return { definitionID = entryID + 100, type = 0, maxRanks = 2,
        isAvailable = true, isDisplayError = false, conditionIDs = {} }
end
e.C_Traits.GetDefinitionInfo = function(definitionID)
    return { spellID = definitionID + 800, overrideName = "Synthetic talent " .. definitionID }
end
e.C_Traits.GetTraitDescription = function(entryID, rank)
    return "Talent " .. entryID .. " rank " .. rank
end
h:start()
h.env.SlashCmdList.FOREVERTOME("dump")
h:advance(5)
e.GetQuestID = function()
    return 501
end
e.UnitGUID = function(token)
    if token == "npc" then
        return "Creature-0-1-2-3-7001-000001"
    end
end
e.C_CreatureInfo.GetCreatureID = function()
    return 7001
end
h:event("QUEST_DETAIL")
h:event("QUEST_FINISHED")
e.UnitGUID = nil
h:event("QUEST_ACCEPTED", 501)
e.UnitGUID = function(token)
    if token == "npc" then
        return "Creature-0-1-2-3-7001-000001"
    end
end
h:event("QUEST_COMPLETE")
h:event("QUEST_FINISHED")
e.UnitGUID = nil
h:advance(43)
h:event("QUEST_REMOVED", 501, false)
h:event("QUEST_TURNED_IN", 501, 380, 50)
h:advance(11)
h:event("QUEST_LOOT_RECEIVED", 501, "item:11584", 10)
h:event("QUEST_LOOT_RECEIVED", 501, "item:247846", 1)
h:assertHealthy()
h.FT.Emit("item.metadata", { item_id = 123, name = "Caf\195\169", description = "First\nSecond" }, "ITEM_DATA_LOAD_RESULT")
h:event("PLAYER_LOGOUT")
local saved = assert(h.FT.Export())
saved.synthetic = true
local restored = Host.new(saved)
restored:start()
restored:advance(1)
restored:assertHealthy()
local database = assert(restored.FT.Export())
local function serialize(value)
    if type(value) == "string" then
        return string.format("%q", value)
    elseif type(value) == "number" or type(value) == "boolean" then
        return tostring(value)
    end
    assert(type(value) == "table")
    local values = {}
    for key, child in pairs(value) do
        table.insert(values, "[" .. serialize(key) .. "]=" .. serialize(child))
    end
    return "{" .. table.concat(values, ",") .. "}"
end
io.write("ForeverTomeDB = " .. serialize(database))
'''
        interpreter = os.environ.get("FOREVERTOME_LUA") or shutil.which("luajit") or shutil.which("lua5.1") or shutil.which("lua")
        self.assertIsNotNone(interpreter, "Lua 5.1 or LuaJIT is required; set FOREVERTOME_LUA to its executable")
        process = subprocess.run([interpreter, "-"], input=script.encode("utf-8"), capture_output=True,
                                 cwd=MODULE_PATH.parents[1], timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", errors="replace"))
        database = export.parse_saved_variables(process.stdout)
        self.assertEqual(len(database["sessions"]), 2)
        self.assertTrue(database["synthetic"])
        original = next(row for row in database["sessions"][0]["observations"] if row["kind"] == "item.metadata")
        self.assertEqual(original["data"], {"item_id": 123, "name": "Café", "description": "First\nSecond"})
        observations = database["sessions"][0]["observations"]
        accepted     = next(row for row in observations if row["kind"] == "quest.accepted")
        dialogue     = next(row for row in observations if row["kind"] == "quest.dialogue")
        self.assertEqual(accepted["data"]["dialogue_npc"]["creature_id"], 7001)
        self.assertNotIn("npc", accepted["data"])
        self.assertEqual(accepted["missing_fields"]["npc"], "unknown_source")
        self.assertEqual(accepted["related_observation_ids"], [dialogue["observation_id"]])
        self.assertEqual(accepted["data"]["interaction_id"], dialogue["data"]["interaction_id"])
        reward_dialogue = next(row for row in observations if row["kind"] == "quest.dialogue" and row["data"]["phase"] == "QUEST_COMPLETE")
        turnin          = next(row for row in observations if row["kind"] == "quest.turned_in")
        receipts        = [row for row in observations if row["kind"] == "quest.reward_received"]
        self.assertEqual(turnin["data"]["dialogue_npc"]["creature_id"], 7001)
        self.assertEqual(turnin["data"]["dialogue_context"], "quest_run_reward_dialogue")
        self.assertIn(reward_dialogue["observation_id"], turnin["related_observation_ids"])
        self.assertEqual([(row["data"]["item_id"], row["data"]["quantity"]) for row in receipts], [(11584, 10), (247846, 1)])
        for receipt in receipts:
            self.assertEqual(receipt["capture"]["event"], "QUEST_LOOT_RECEIVED")
            self.assertEqual(receipt["evidence"]["method"], "direct_event")
            self.assertEqual(receipt["data"]["quest_id"], 501)
            self.assertEqual(receipt["data"]["quest_run_id"], turnin["data"]["quest_run_id"])
            self.assertEqual(receipt["related_observation_ids"], [turnin["observation_id"], reward_dialogue["observation_id"]])
        metadata     = [row["data"] for row in observations if row["kind"] == "talent.metadata"]
        nodes        = {row["entity_id"]: row["info"] for row in metadata if row["entity_type"] == "node"}
        self.assertEqual(set(nodes), {11, 12})
        self.assertEqual(nodes[11]["visibleEdges"][0]["targetNode"], 12)
        self.assertEqual(nodes[12]["visibleEdges"], [])
        self.assertEqual(nodes[12]["currentRank"], 0)
        self.assertEqual(nodes[12]["entryIDs"], [102])
        self.assertEqual(nodes[12]["entryIDsWithCommittedRanks"], [])
        self.assertEqual(nodes[12]["entry_rank_increases"], [{"entry_id": 102, "ranks_increased": 0}])
        self.assertEqual(nodes[12]["conditionIDs"], [])
        self.assertEqual(nodes[12]["costs"], [])
        definitions = {row["entity_id"]: row["info"] for row in metadata if row["entity_type"] == "definition"}
        self.assertEqual(definitions[202]["spellID"], 1002)
        ranks = {(row["data"]["entry_id"], row["data"]["rank"]): row["data"]["description"]
                 for row in observations if row["kind"] == "talent.rank"}
        self.assertEqual(ranks[102, 2], "Talent 102 rank 2")
        snapshots = [row["data"] for row in observations if row["kind"] == "talent.snapshot"]
        self.assertTrue(any(row["tree_ids"] == [9] and row["node_count"] == 2
                            and row["completeness"] == "complete" for row in snapshots))
        spellbook = [row["data"] for row in observations if row["kind"] == "spellbook.snapshot"]
        player    = next(row for row in spellbook if row["bank"] == "player")
        pet       = next(row for row in spellbook if row["bank"] == "pet")
        entries   = {row["spellID"]: row for row in player["entries"]}
        self.assertEqual(player["skill_lines"][0]["name"], "Synthetic spell category")
        self.assertTrue(entries[1001]["isPassive"])
        self.assertTrue(entries[1001]["is_known"])
        self.assertEqual(entries[1002]["item_type"], "FutureSpell")
        self.assertFalse(entries[1002]["is_known"])
        self.assertEqual(entries[1002]["levelLearned"], 60)
        self.assertEqual(pet["entries"], [])
        spells = {row["data"]["spell_id"]: row["data"] for row in observations if row["kind"] == "spell.metadata"}
        self.assertTrue(spells[1001]["is_passive"])
        self.assertEqual(spells[1002]["description"], "Spell description 1002")
        self.assertEqual(spells[1002]["current_state"]["power_costs"], [])
        self.assertEqual(spells[1002]["current_state"]["cooldown"]["duration"], 0)
        restored      = database["sessions"][1]["observations"]
        unknown_tree  = next(row for row in restored if row["kind"] == "talent.snapshot")
        unknown_books = [row["data"] for row in restored if row["kind"] == "spellbook.snapshot"]
        self.assertNotIn("tree_ids", unknown_tree["data"])
        self.assertNotIn("expected_node_count", unknown_tree["data"])
        self.assertIn("data.config_id", unknown_tree["missing_fields"])
        self.assertEqual({row["bank"] for row in unknown_books}, {"player", "pet"})
        for book in unknown_books:
            self.assertEqual(book["bank_status"], "unavailable")
            self.assertNotIn("entries", book)
            self.assertNotIn("skill_lines", book)
        self.assertNotIn("PRIVATE_LOADOUT_NAME", export.canonical(database))
        self.assertNotIn("PRIVATE_CHARACTER_NAME", export.canonical(database))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "runtime.sqlite"
            output      = Path(directory) / "runtime.json"
            lines       = Path(directory) / "runtime.jsonl"
            export.write_export(database, output, "json", "synthetic")
            export.write_export(database, lines, "jsonl", "synthetic")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), database)
            observations = [row for session in database["sessions"] for row in session["observations"]]
            records      = [json.loads(line) for line in lines.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["observation"] for row in records if row["type"] == "observation"], observations)
            self.assertEqual(export.import_sqlite(database, destination), database["record_count"])
            self.assertEqual(export.import_sqlite(database, destination), 0)
            with closing(sqlite3.connect(destination)) as connection:
                rows = connection.execute("SELECT record_json FROM ft_observations ORDER BY session_id, sequence").fetchall()
                self.assertEqual([json.loads(row[0]) for row in rows], observations)


if __name__ == "__main__":
    unittest.main()
