import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_catalog import make_database, make_session, source_bytes
from tools import desktop_exporter as desktop


class CallbackWatcher:
    def __init__(self, callback):
        self.callback = callback

    def sync(self):
        return self.callback()


class DesktopExporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary   = tempfile.TemporaryDirectory()
        self.root        = Path(self.temporary.name)
        self.source      = self.root / "ForeverTome.lua"
        self.output_dir  = self.root / "catalog"
        self.controllers = []
        self.releases    = []
        self.source.write_bytes(source_bytes(make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Desktop test item", "stats": {"ARMOR": 4}}),
        ]))))
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.stop_workers)

    def stop_workers(self):
        for controller in self.controllers:
            controller.stop()
        for release in self.releases:
            release.set()
        for controller in self.controllers:
            if controller._thread is not None:
                controller._thread.join(3)
                self.assertFalse(controller.running)

    def controller(self, callback=None, interval=0.02):
        if callback is None:
            controller = desktop.ExporterController(interval=interval)
        else:
            def factory(source, output_dir):
                self.assertEqual(source, self.source.resolve())
                self.assertEqual(output_dir, self.output_dir.resolve())
                return CallbackWatcher(callback)

            controller = desktop.ExporterController(watcher_factory=factory, interval=interval)
        self.controllers.append(controller)
        return controller

    def wait_event(self, controller, kind):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            event = controller.events.get(timeout=max(0.01, deadline - time.monotonic()))
            if event["type"] == kind:
                return event
        self.fail(f"No {kind} event received")

    def finish(self, controller):
        controller._thread.join(3)
        self.assertFalse(controller.running)

    def write_catalog(self):
        document = {"exportId": "test-export", "summary": {"observationCount": 12, "transactionCount": 3}}
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "latest.json").write_text(json.dumps(document), encoding="utf-8")
        for index, category in enumerate(desktop.CATEGORIES):
            view = {"exportId": document["exportId"], "category": category, "entries": [{}] * index}
            (self.output_dir / f"{category}.json").write_text(json.dumps(view), encoding="utf-8")
        return document

    def test_once_exports_real_save_and_leaves_source_unchanged(self):
        original   = self.source.read_bytes()
        controller = self.controller()
        controller.start(self.source, self.output_dir, watch=False)
        result = self.wait_event(controller, "exported")
        self.finish(controller)
        self.assertEqual(result["summary"]["observationCount"], 1)
        self.assertEqual(result["categoryCounts"]["items"], 1)
        self.assertEqual(set(result["categoryCounts"]), set(desktop.CATEGORIES))
        self.assertEqual(result["output_dir"], str(self.output_dir.resolve()))
        self.assertIn("T", result["saved_at"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse(controller._thread.daemon)
        self.assertEqual(controller.events.get_nowait()["type"], "stopped")

    def test_first_unchanged_sync_reads_existing_summary_and_counts(self):
        document   = self.write_catalog()
        controller = self.controller(lambda: None)
        controller.start(self.source, self.output_dir, watch=False)
        result = self.wait_event(controller, "current")
        self.finish(controller)
        self.assertEqual(result["summary"], document["summary"])
        self.assertEqual(result["exportId"], document["exportId"])
        self.assertEqual(result["categoryCounts"], dict(zip(desktop.CATEGORIES, range(7))))

    def test_stop_during_conversion_is_nonblocking_and_finishes_only_current_work(self):
        entered    = threading.Event()
        release    = threading.Event()
        document   = self.write_catalog()
        calls      = []
        self.releases.append(release)

        def convert():
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(3))
            return document

        controller = self.controller(convert)
        controller.start(self.source, self.output_dir)
        self.assertTrue(entered.wait(3))
        controller.stop()
        self.assertTrue(controller.running)
        self.assertEqual(calls, [1])
        release.set()
        self.wait_event(controller, "exported")
        self.finish(controller)
        self.assertEqual(calls, [1])

    def test_rejects_concurrent_start_and_can_restart_after_stop(self):
        entered = threading.Event()
        release = threading.Event()
        self.write_catalog()
        self.releases.append(release)

        def convert():
            entered.set()
            self.assertTrue(release.wait(3))
            return None

        controller = self.controller(convert)
        controller.start(self.source, self.output_dir)
        self.assertTrue(entered.wait(3))
        with self.assertRaisesRegex(RuntimeError, "already running"):
            controller.start(self.source, self.output_dir)
        controller.stop()
        release.set()
        self.finish(controller)
        controller.start(self.source, self.output_dir, watch=False)
        self.finish(controller)
        events = []
        while not controller.events.empty():
            events.append(controller.events.get_nowait()["type"])
        self.assertEqual(events.count("stopped"), 2)
        self.assertEqual(events.count("current"), 2)

    def test_stop_wakes_long_interval_without_another_sync(self):
        self.write_catalog()
        calls = []

        def unchanged():
            calls.append(1)
            return None

        controller = self.controller(unchanged, interval=60)
        controller.start(self.source, self.output_dir)
        self.wait_event(controller, "current")
        controller.stop()
        self.finish(controller)
        self.assertEqual(calls, [1])

    def test_watch_retries_errors_without_repeating_events_and_reports_recovery(self):
        self.write_catalog()
        attempts = []

        def convert():
            attempts.append(time.monotonic())
            if len(attempts) <= 3:
                raise OSError("Save is temporarily unavailable")
            return None

        controller = self.controller(convert)
        controller.start(self.source, self.output_dir)
        error = self.wait_event(controller, "error")
        self.assertTrue(error["retrying"])
        result = controller.events.get(timeout=3)
        self.assertEqual(result["type"], "current")
        controller.stop()
        self.finish(controller)
        self.assertGreaterEqual(len(attempts), 4)
        self.assertGreaterEqual(attempts[3] - attempts[0], 0.045)

    def test_once_failure_does_not_retry(self):
        attempts = []

        def convert():
            attempts.append(1)
            raise OSError("Save file not found")

        controller = self.controller(convert)
        controller.start(self.source, self.output_dir, watch=False)
        error = self.wait_event(controller, "error")
        self.finish(controller)
        self.assertEqual(error["message"], "Save file not found")
        self.assertFalse(error["retrying"])
        self.assertEqual(attempts, [1])

    def test_constructor_failure_surfaces_and_stops_worker(self):
        def factory(source, output_dir):
            raise ValueError("Source and output paths must differ")

        controller = desktop.ExporterController(watcher_factory=factory)
        self.controllers.append(controller)
        controller.start(self.source, self.output_dir, watch=False)
        error = self.wait_event(controller, "error")
        self.finish(controller)
        self.assertIn("must differ", error["message"])

    def test_current_summary_rejects_mismatched_category_generation(self):
        self.write_catalog()
        (self.output_dir / "spells.json").write_text(json.dumps({
            "exportId": "older-export", "category": "spells", "entries": [],
        }), encoding="utf-8")
        controller = self.controller(lambda: None)
        controller.start(self.source, self.output_dir, watch=False)
        error = self.wait_event(controller, "error")
        self.finish(controller)
        self.assertIn("do not match", error["message"])

    def test_invalid_existing_summary_reports_error_without_queueing_display_data(self):
        for field in ("observationCount", "transactionCount"):
            for value in (None, True, False, -1, 2.5, "3"):
                with self.subTest(field=field, value=value):
                    document = self.write_catalog()
                    if value is None:
                        document["summary"].pop(field)
                    else:
                        document["summary"][field] = value
                    (self.output_dir / "latest.json").write_text(json.dumps(document), encoding="utf-8")
                    controller = self.controller(lambda: None)
                    controller.start(self.source, self.output_dir, watch=False)
                    self.finish(controller)
                    events = []
                    while not controller.events.empty():
                        events.append(controller.events.get_nowait())
                    self.assertEqual([event["type"] for event in events], ["working", "error", "stopped"])
                    self.assertIn(field, events[1]["message"])

    def test_invalid_intervals_cannot_start_busy_loop(self):
        for interval in (0, -1, float("nan"), float("inf"), "2"):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                desktop.ExporterController(interval=interval)


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root      = Path(self.temporary.name)
        self.path      = self.root / "preferences" / "settings.json"
        self.addCleanup(self.temporary.cleanup)

    def test_default_preferences_live_under_local_app_data(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root)}):
            self.assertEqual(desktop.settings_path(), self.root / "ForeverTomeExporter" / "settings.json")
            desktop.save_settings(Path("source.lua"), Path("catalog"))
            self.assertEqual(desktop.load_settings(), {"source": "source.lua", "output_dir": "catalog"})

    def test_missing_corrupt_unreadable_and_wrongly_typed_preferences_are_ignored(self):
        self.assertEqual(desktop.load_settings(self.path), {})
        self.path.parent.mkdir()
        for contents in ("{broken", "[]", '{"source": 1, "output_dir": null}', " " * 65537):
            self.path.write_text(contents, encoding="utf-8")
            self.assertEqual(desktop.load_settings(self.path), {})
        self.path.write_text("{}", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError("Not readable")):
            self.assertEqual(desktop.load_settings(self.path), {})
        self.path.write_text('{"source": "recording.lua", "output_dir": " ", "autorun": true}', encoding="utf-8")
        self.assertEqual(desktop.load_settings(self.path), {"source": "recording.lua"})

    def test_saving_preferences_preserves_unicode_paths_and_only_path_preferences(self):
        source = self.root / "Données" / "ForeverTome.lua"
        output = self.root / "JSON exports"
        desktop.save_settings(source, output, self.path)
        self.assertEqual(desktop.load_settings(self.path), {"source": str(source), "output_dir": str(output)})
        self.assertEqual(list(self.path.parent.glob(".settings-*")), [])

    def test_failed_atomic_replace_preserves_previous_preferences_and_cleans_temp(self):
        desktop.save_settings(Path("first.lua"), Path("first-catalog"), self.path)
        original = self.path.read_bytes()
        with patch.object(desktop.os, "replace", side_effect=PermissionError("Settings locked")):
            with self.assertRaisesRegex(PermissionError, "Settings locked"):
                desktop.save_settings(Path("second.lua"), Path("second-catalog"), self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob(".settings-*")), [])


if __name__ == "__main__":
    unittest.main()
