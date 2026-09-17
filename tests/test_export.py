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
h:start()
h.FT.Emit("item.metadata", { item_id = 123, name = "Caf\195\169", description = "First\nSecond" }, "ITEM_DATA_LOAD_RESULT")
h:event("PLAYER_LOGOUT")
local saved = assert(h.FT.Export())
saved.synthetic = true
local restored = Host.new(saved)
restored:start()
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
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "runtime.sqlite"
            output      = Path(directory) / "runtime.json"
            export.write_export(database, output, "json", "synthetic")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), database)
            self.assertEqual(export.import_sqlite(database, destination), database["record_count"])
            self.assertEqual(export.import_sqlite(database, destination), 0)


if __name__ == "__main__":
    unittest.main()
