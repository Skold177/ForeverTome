import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_catalog import make_database, make_session, source_bytes
from tools import watch_catalog as watch
from tools.catalog_history import history_id, validate_archive


class CatalogHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root      = Path(self.temporary.name)
        self.source    = self.root / "ForeverTome.lua"
        self.output    = self.root / "catalogs"
        self.watcher   = watch.CatalogWatcher(self.source, self.output)
        self.addCleanup(self.temporary.cleanup)

    def save(self, *sessions):
        database                 = make_database(*sessions)
        database["next_session"] = max((int(session["session"]["session_id"].rsplit("-", 1)[1])
                                        for session in sessions), default=0)
        self.source.write_bytes(source_bytes(database))

    def read(self, name):
        path = self.output / f"{name}.json"
        return json.loads(path.read_bytes())

    def test_history_retains_standalone_records_and_zero_record_sessions_after_clear(self):
        recorded = make_session(1, [
            ("coverage.gap", {"reason": "recording_paused"}),
            ("player.state", {"state_event": "SYNTHETIC"}),
            ("world.context", {"zone": "Synthetic zone"}),
            ("quest.log_scope", {"complete": False}),
        ])
        empty = make_session(2, [])
        empty["diagnostics"]["counts"]["synthetic:unavailable"] = 4
        empty["diagnostics"]["distinct"] = 2
        self.save(recorded, empty)
        self.watcher.sync()
        first = self.read("history")
        self.assertEqual(first["summary"]["observationCount"], 4)
        self.assertEqual(first["summary"]["sessionCount"], 2)
        self.assertFalse(any(self.read(category)["entries"] for category in watch.CATEGORIES))
        self.save()
        self.watcher.sync()
        history = self.read("history")
        self.assertEqual(history["records"], first["records"])
        self.assertEqual(history["sessions"], first["sessions"])
        self.assertEqual(self.read("latest")["summary"]["observationCount"], 0)
        self.assertEqual(self.read("database")["records"], history["records"])
        self.assertFalse(history["retention"]["legacyMigration"])
        self.assertEqual(history["retention"]["priorCoverage"], "unknown")

    def test_replaying_older_save_preserves_diagnostic_maxima_and_new_keys(self):
        old = make_session(1, [("item.metadata", {"item_id": 100})])
        new = copy.deepcopy(old)
        new["diagnostics"]["counts"].update({"synthetic:missing": 7, "new:failure": 3})
        new["diagnostics"]["distinct"] = 2
        self.save(new)
        self.watcher.sync()
        self.save(old)
        self.watcher.sync()
        for name in ("history", "database", "items"):
            self.assertEqual(self.read(name)["sessions"][0]["diagnostics"], new["diagnostics"])
        self.assertEqual(self.read("latest")["sessions"][0]["diagnostics"], old["diagnostics"])

    def test_legacy_migration_combines_category_evidence_and_complete_snapshots(self):
        self.output.mkdir()
        legacy_sessions = [
            make_session(1, [("item.metadata", {"item_id": 100}), ("player.state", {"state_event": "lost"})]),
            make_session(2, [("quest.log_scope", {"complete": False})]),
            make_session(3, [("world.context", {"zone": "Legacy zone"})]),
        ]
        documents = []
        for index, session in enumerate(legacy_sessions, 1):
            self.save(session)
            database, digest = watch.saved.read_stable(self.source)
            documents.append(watch.build_catalog(database, digest))
        category = watch.category_catalog(documents[0], "items")
        (self.output / "items.json").write_text(json.dumps(category), encoding="utf-8")
        (self.output / "catalog-legacy.json").write_text(json.dumps(documents[1]), encoding="utf-8")
        (self.output / "latest.json").write_text(json.dumps(documents[2]), encoding="utf-8")
        self.save()
        self.watcher.sync()
        history = self.read("history")
        types   = {row["type"] for row in history["records"]}
        self.assertEqual(types, {"item.metadata", "quest.log_scope", "world.context"})
        self.assertNotIn("player.state", types)
        self.assertTrue(history["retention"]["legacyMigration"])
        self.assertEqual(history["retention"]["priorCoverage"], "unknown")
        self.assertEqual({entry["name"] for entry in history["imports"]},
                         {"items.json", "catalog-legacy.json", "latest.json", "SavedVariables"})
        self.assertIsNone(watch.CatalogWatcher(self.source, self.output).sync())

    def test_deleted_categories_and_database_rebuild_from_archive_after_clear(self):
        self.save(make_session(1, [
            ("unit.sighting", {"creature_id": 300, "name": "Creature", "reaction": 2}),
            ("recipe.metadata", {"recipe_id": 400}),
            ("coverage.gap", {"reason": "recording_paused"}),
        ]))
        self.watcher.sync()
        records = self.read("history")["records"]
        self.save()
        self.watcher.sync()
        for name in (*watch.CATEGORIES, "database"):
            (self.output / f"{name}.json").unlink()
        restarted = watch.CatalogWatcher(self.source, self.output)
        restarted.sync()
        self.assertEqual(self.read("database")["records"], records)
        self.assertEqual([entry["nativeId"] for entry in self.read("recipes")["entries"]], [400])
        creatures = self.read("creatures")
        for name in ("creatures", "npcs", "monsters"):
            view = self.read(name)
            self.assertEqual(view["canonicalCategory"], "creatures")
            self.assertEqual(view["entries"], creatures["entries"])
        self.assertEqual(creatures["entries"][0]["kind"], "npc")
        self.assertNotIn("npcs", self.read("database")["catalog"])
        self.assertNotIn("monsters", self.read("database")["catalog"])
        self.assertIsNone(restarted.sync())

    def test_partial_publication_archives_observations_before_next_save_is_cleared(self):
        self.save(make_session(1, [("coverage.gap", {"reason": "recording_paused"})]))
        replace = watch.os.replace
        writes  = []

        def fail_projection(source, destination):
            writes.append(Path(destination).name)
            if Path(destination).name == "database.json":
                raise OSError("synthetic projection failure")
            return replace(source, destination)

        with patch.object(watch.os, "replace", side_effect=fail_projection):
            with self.assertRaises(OSError):
                self.watcher.sync()
        self.assertEqual(writes, ["history.json", "database.json"])
        self.assertFalse((self.output / "latest.json").exists())
        self.assertEqual(len(self.read("history")["records"]), 1)
        self.save()
        restarted = watch.CatalogWatcher(self.source, self.output)
        restarted.sync()
        self.assertEqual(len(self.read("history")["records"]), 1)
        self.assertEqual(self.read("database")["records"][0]["type"], "coverage.gap")
        self.assertEqual(self.read("latest")["summary"]["observationCount"], 0)
        self.assertIsNone(restarted.sync())

    def test_deleted_archive_recovers_standalone_evidence_from_database(self):
        self.save(make_session(1, [("quest.log_scope", {"complete": False})]))
        self.watcher.sync()
        self.save()
        self.watcher.sync()
        records = self.read("history")["records"]
        (self.output / "history.json").unlink()
        self.watcher.sync()
        self.assertEqual(self.read("history")["records"], records)
        self.assertTrue(any(entry["kind"] == "database_projection" for entry in self.read("history")["imports"]))

    def test_projection_error_still_preserves_every_observation_in_archive(self):
        self.save(make_session(1, [("coverage.gap", {"reason": "recording_paused"})]))
        with patch("tools.catalog_database.database_projection", side_effect=ValueError("synthetic projection error")):
            with self.assertRaisesRegex(ValueError, "synthetic projection error"):
                self.watcher.sync()
        self.assertEqual(self.read("history")["records"][0]["type"], "coverage.gap")
        self.save()
        self.watcher.sync()
        self.assertEqual(self.read("database")["records"][0]["type"], "coverage.gap")

    def test_malformed_database_evidence_is_rejected_without_archive_changes(self):
        self.save(make_session(1, [("item.metadata", {"item_id": 100})]))
        self.watcher.sync()
        invalid = self.read("database")
        invalid["records"] = None
        (self.output / "database.json").write_text(json.dumps(invalid), encoding="utf-8")
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.save()
        with self.assertRaises(ValueError):
            self.watcher.sync()
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, before)

    def test_malformed_archive_is_preserved_without_any_projection_writes(self):
        self.save(make_session(1, [("item.metadata", {"item_id": 100})]))
        self.watcher.sync()
        original = self.read("history")
        invalid  = copy.deepcopy(original)
        invalid["records"][0]["relatedIds"] = ["missing"]
        invalid["historyId"] = history_id(invalid)
        cases = [{"format": "foreign"}, {**original, "historyId": "0" * 64}, invalid]
        for value in cases:
            with self.subTest(value=value.get("historyId")):
                (self.output / "history.json").write_text(json.dumps(value), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in self.output.iterdir()}
                with self.assertRaises(ValueError):
                    watch.CatalogWatcher(self.source, self.output).sync()
                self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, before)

    def test_archive_rejects_conflicting_standalone_evidence_and_duplicate_records(self):
        self.save(make_session(1, [("player.state", {"state_event": "first"})]))
        self.watcher.sync()
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.save(make_session(1, [("player.state", {"state_event": "changed"})]))
        with self.assertRaisesRegex(ValueError, "Conflicting history observation"):
            self.watcher.sync()
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, before)
        invalid = self.read("history")
        invalid["records"].append(copy.deepcopy(invalid["records"][0]))
        invalid["historyId"] = history_id(invalid)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_archive(invalid)

    def test_all_new_outputs_are_required_for_unchanged_source_skip(self):
        self.save()
        self.watcher.sync()
        for name in ("history", "database", "creatures", "recipes", "professions", "maps", "currencies", "objects"):
            with self.subTest(name=name):
                (self.output / f"{name}.json").unlink()
                self.assertIsNotNone(self.watcher.sync())
                self.assertTrue((self.output / f"{name}.json").exists())
                self.assertIsNone(self.watcher.sync())


if __name__ == "__main__":
    unittest.main()
