import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forevertome_test_gate", ROOT / "tools" / "test.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

APPEND_ANCHOR = "    active.observations[#active.observations + 1] = owned"


def replace_once(path: Path, before: str, after: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(before) != 1:
        raise AssertionError(f"Mutation anchor must occur exactly once in {path.name}: {before!r}")
    path.write_text(source.replace(before, after, 1), encoding="utf-8")


class GateIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.interpreter, _ = gate.find_lua()

    def mutant(self, mutate):
        with tempfile.TemporaryDirectory(prefix="forevertome-mutation-") as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "ForeverTome", root / "ForeverTome")
            shutil.copytree(ROOT / "tests", root / "tests", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
            mutate(root)
            return subprocess.run(
                [self.interpreter, "tests/run.lua"], cwd=root, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=120,
            )

    def assert_detected(self, process, test_name, assertion_fragment):
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        lines = process.stdout.splitlines()
        label = "FAIL " + test_name
        self.assertIn(label, lines, process.stdout + process.stderr)
        index = lines.index(label)
        self.assertLess(index + 1, len(lines))
        self.assertIn(assertion_fragment, lines[index + 1], lines[index + 1])
        self.assertIn("tests/support/host.lua:", lines[index + 1], "Expected a domain assertion, not setup failure")
        self.assertRegex(process.stdout, r"\d+ passed; [1-9]\d* failed\s*$")
        self.assertIn("PASS ", process.stdout, "A setup crash does not demonstrate mutation detection")

    def test_mutant_nested_alias_is_detected(self):
        def mutate(root):
            replacement = "    if data then\n        owned.data = data\n    end\n" + APPEND_ANCHOR
            replace_once(root / "ForeverTome" / "Core.lua", APPEND_ANCHOR, replacement)

        self.assert_detected(
            self.mutant(mutate), "core: capture and export independently own nested observations", "mutated ~= Runes",
        )

    def test_mutant_wrong_quest_argument_is_detected(self):
        def mutate(root):
            replace_once(root / "ForeverTome" / "Compatibility.lua", "quest_accepted_arg = 1", "quest_accepted_arg = 2")

        self.assert_detected(
            self.mutant(mutate),
            "quests: quests: modern acceptance decodes argument one and repeated runs stay distinct", "999 ~= 501",
        )

    def test_mutant_metadata_rewrites_history_is_detected(self):
        def mutate(root):
            replacement = '''    if kind == "item.metadata" then
        for _, previous in ipairs(active.observations) do
            if previous.kind == "loot.visible" then
                previous.data.name = "mutated_previous"
                break
            end
        end
    end
''' + APPEND_ANCHOR
            replace_once(root / "ForeverTome" / "Core.lua", APPEND_ANCHOR, replacement)

        self.assert_detected(
            self.mutant(mutate), "loot: item metadata keeps link variants and enriches after loot closes",
            "mutated_previous ~= Test Hood",
        )

    def test_mutant_dropped_exported_field_is_detected(self):
        def mutate(root):
            before = "    return FT.Copy(database, FT.LIMITS.bytes * 2, FT.LIMITS.records * 200)"
            after  = '''    local exported = FT.Copy(database, FT.LIMITS.bytes * 2, FT.LIMITS.records * 200)
    for _, session in ipairs(exported.sessions) do
        for _, observation in ipairs(session.observations) do
            for _, objective in ipairs(observation.data.objectives or {}) do
                objective.finished = nil
            end
        end
    end
    return exported'''
            replace_once(root / "ForeverTome" / "Core.lua", before, after)

        self.assert_detected(
            self.mutant(mutate), "core: capture and export independently own nested observations", "missing finished",
        )

    def test_mutant_disabled_required_suite_cannot_report_success(self):
        def mutate(root):
            replace_once(root / "tests" / "run.lua", '{ "core", "quests", "loot", "world" }', '{ "core", "loot", "world" }')

        process = self.mutant(mutate)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        with self.assertRaisesRegex(gate.GateError, "Missing required Lua suite results: quests"):
            gate.validate_lua_results(process.stdout, process.returncode)

    def test_lua_exit_codes_empty_execution_and_missing_results_are_rejected(self):
        for stdout, returncode, expected in (
            ("34 passed; 0 failed\n", 7, "exited with status 7"),
            ("", 0, "exactly one execution summary"),
            ("0 passed; 0 failed\n", 0, "Missing required Lua suite"),
            ("34 passed; 0 failed\n", 0, "disagrees"),
        ):
            with self.subTest(stdout=stdout, returncode=returncode), self.assertRaisesRegex(gate.GateError, expected):
                gate.validate_lua_results(stdout, returncode)

    def test_explicit_invalid_interpreter_does_not_fall_back(self):
        environment = dict(os.environ)
        environment["FOREVERTOME_LUA"] = str(ROOT / "missing-interpreter-for-gate-test")
        with self.assertRaisesRegex(gate.GateError, "FOREVERTOME_LUA"):
            gate.find_lua(environment)
        environment["FOREVERTOME_LUA"] = sys.executable
        with self.assertRaisesRegex(gate.GateError, "requires Lua 5.1 and setfenv"):
            gate.find_lua(environment)

    def test_skips_unexpected_failures_and_incomplete_python_execution_are_rejected(self):
        result = unittest.TestResult()
        result.testsRun = 2
        result.skipped.append(("synthetic.test", "must not skip"))
        with self.assertRaisesRegex(gate.GateError, "were skipped"):
            gate.validate_python_result(result, 2)
        result.skipped.clear()
        result.expectedFailures.append(("synthetic.test", "not allowed"))
        with self.assertRaisesRegex(gate.GateError, "Expected failures"):
            gate.validate_python_result(result, 2)
        result.expectedFailures.clear()
        with self.assertRaisesRegex(gate.GateError, "executed 2 tests after discovering 3"):
            gate.validate_python_result(result, 3)


if __name__ == "__main__":
    unittest.main()
