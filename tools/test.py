#!/usr/bin/env python3
"""Run every required offline check without permitting missing or skipped suites."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT             = Path(__file__).resolve().parents[1]
LUA_MINIMUMS     = {"core": 18, "quests": 9, "loot": 10, "world": 10, "spells": 10, "talents": 17}
PYTHON_MINIMUMS  = {"test_export": 13, "test_gate": 8, "test_package": 3, "test_catalog": 21,
                    "test_watch_catalog": 23, "test_catalog_merge": 11, "test_gathering_catalog": 4, "test_desktop_exporter": 15,
                    "test_addon_installer": 14}
PYTHON_MINIMUM   = sum(PYTHON_MINIMUMS.values())
INTERPRETER_TEST = 'assert(_VERSION == "Lua 5.1" and type(setfenv) == "function", "Lua 5.1 with setfenv required"); io.write(_VERSION)'


class GateError(RuntimeError):
    pass


def find_lua(environment: dict[str, str] | None = None) -> tuple[str, str]:
    environment = os.environ if environment is None else environment
    requested   = environment.get("FOREVERTOME_LUA")
    candidates  = [requested] if requested else ["luajit", "lua5.1", "lua"]
    failures    = []
    for candidate in candidates:
        executable = shutil.which(candidate, path=environment.get("PATH"))
        if executable is None:
            failures.append(f"{candidate}: executable not found")
            continue
        try:
            probe = subprocess.run(
                [executable, "-e", INTERPRETER_TEST], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f"{candidate}: {error}")
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "Lua 5.1":
            return str(Path(executable).resolve()), probe.stdout.strip()
        failures.append(f"{candidate}: requires Lua 5.1 and setfenv")
    source = "FOREVERTOME_LUA" if requested else "PATH"
    raise GateError(f"No compatible Lua interpreter from {source}. " + "; ".join(failures))


def validate_lua_results(stdout: str, returncode: int) -> dict:
    if returncode != 0:
        raise GateError(f"Lua regression process exited with status {returncode}")
    summaries = re.findall(r"^(\d+) passed; (\d+) failed\s*$", stdout, re.MULTILINE)
    if len(summaries) != 1:
        raise GateError("Lua runner must emit exactly one execution summary")
    passed, failed = map(int, summaries[0])
    rows           = re.findall(r"^(PASS|FAIL) ([a-z_]+): (.+)$", stdout, re.MULTILINE)
    successes      = sum(status == "PASS" for status, _, _ in rows)
    failures       = sum(status == "FAIL" for status, _, _ in rows)
    if passed != successes or failed != failures or failed:
        raise GateError("Lua execution summary disagrees with individual test results or contains failures")
    counts = {name: sum(suite == name for _, suite, _ in rows) for name in LUA_MINIMUMS}
    for name, minimum in LUA_MINIMUMS.items():
        if counts[name] == 0:
            raise GateError(f"Missing required Lua suite results: {name}")
        if counts[name] < minimum:
            raise GateError(f"Lua suite {name} executed {counts[name]} tests; at least {minimum} are required")
    identities = [(suite, name) for _, suite, name in rows]
    if len(set(identities)) != len(identities):
        raise GateError("Duplicate Lua test identities cannot substitute for required execution")
    unexpected = set(suite for _, suite, _ in rows) - set(LUA_MINIMUMS)
    if unexpected:
        raise GateError("Unregistered Lua suites: " + ", ".join(sorted(unexpected)))
    return {"discovered": len(rows), "executed": len(rows), "passed": passed, "failed": failed,
            "skipped": 0, "suites": counts, "test_ids": [f"{suite}:{name}" for _, suite, name in rows]}


def run_lua(interpreter: str, root: Path = ROOT) -> dict:
    for name in LUA_MINIMUMS:
        if not (root / "tests" / f"{name}.lua").is_file():
            raise GateError(f"Required Lua suite missing: {name}")
    process = subprocess.run(
        [interpreter, "tests/run.lua"], cwd=root, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    print(process.stdout, end="", flush=True)
    if process.stderr:
        print(process.stderr, end="", file=sys.stderr, flush=True)
    return validate_lua_results(process.stdout, process.returncode)


def test_cases(suite: unittest.TestSuite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_cases(test)
        else:
            yield test


def validate_python_result(result: unittest.TestResult, expected: int) -> dict:
    if result.testsRun != expected:
        raise GateError(f"Python executed {result.testsRun} tests after discovering {expected}")
    if result.skipped:
        raise GateError(f"Required Python tests were skipped: {len(result.skipped)}")
    if result.expectedFailures or result.unexpectedSuccesses:
        raise GateError("Expected failures and unexpected successes are not permitted in the required gate")
    if not result.wasSuccessful():
        raise GateError(f"Python regressions failed: {len(result.failures)} failures, {len(result.errors)} errors")
    return {"discovered": expected, "executed": result.testsRun, "passed": result.testsRun,
            "failed": 0, "errors": 0, "skipped": 0}


def run_python(root: Path = ROOT) -> dict:
    for name in PYTHON_MINIMUMS:
        if not (root / "tests" / f"{name}.py").is_file():
            raise GateError(f"Required Python suite missing: {name}")
    loader = unittest.TestLoader()
    suite  = loader.discover(str(root / "tests"), pattern="test_*.py")
    cases  = list(test_cases(suite))
    if loader.errors:
        raise GateError("Python discovery errors:\n" + "\n".join(loader.errors))
    if len(cases) < PYTHON_MINIMUM:
        raise GateError(f"Python discovered {len(cases)} tests; at least {PYTHON_MINIMUM} are required")
    identifiers = [test.id() for test in cases]
    modules     = {test.__class__.__module__.split(".")[-1] for test in cases}
    missing = set(PYTHON_MINIMUMS) - modules
    if missing:
        raise GateError("Missing required Python suite results: " + ", ".join(sorted(missing)))
    counts = {name: sum(test.__class__.__module__.split(".")[-1] == name for test in cases) for name in PYTHON_MINIMUMS}
    for name, minimum in PYTHON_MINIMUMS.items():
        if counts[name] < minimum:
            raise GateError(f"Python suite {name} discovered {counts[name]} tests; at least {minimum} are required")
    if len(set(identifiers)) != len(identifiers):
        raise GateError("Python discovery produced duplicate test identities")
    print(f"Discovered {len(cases)} required Python tests", flush=True)
    result  = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = validate_python_result(result, len(cases))
    summary["test_ids"] = identifiers
    summary["suites"]   = counts
    return summary


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["required"], default="required")
    parser.add_argument("--report", type=Path, help="Write a JSON result report, including failed gate status")
    options = parser.parse_args(arguments)
    report  = {"suite": options.suite, "status": "failed", "python": sys.version.split()[0],
               "profile": "forever-beta-69893-source-v1", "live_client_validation": False}
    code    = 1
    try:
        if sys.version_info < (3, 10):
            raise GateError("Python 3.10 or later is required")
        interpreter, version = find_lua()
        os.environ["FOREVERTOME_LUA"] = interpreter
        report["interpreter"]         = {"executable": interpreter, "version": version}
        print(f"Required regression gate: Python {report['python']}; {version}; {interpreter}", flush=True)
        report["lua"]          = run_lua(interpreter)
        report["python_tests"] = run_python()
        report["status"]       = "passed"
        code                   = 0
        print(f"PASS required: {report['lua']['executed']} Lua and {report['python_tests']['executed']} Python tests; 0 skipped", flush=True)
    except (GateError, OSError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
        print(f"FAIL required: {error}", file=sys.stderr, flush=True)
    if options.report:
        try:
            options.report.parent.mkdir(parents=True, exist_ok=True)
            options.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"FAIL required: cannot write report: {error}", file=sys.stderr)
            return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
