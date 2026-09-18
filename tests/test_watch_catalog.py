import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_catalog import LINK_A, LINK_B, make_database, make_session, source_bytes


ROOT        = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "watch_catalog.py"
SPEC        = importlib.util.spec_from_file_location("forevertome_watch_catalog", MODULE_PATH)
watch       = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watch
SPEC.loader.exec_module(watch)


class CatalogWatcherTests(unittest.TestCase):
    def setUp(self):
        self.temporary  = tempfile.TemporaryDirectory()
        self.root       = Path(self.temporary.name)
        self.source     = self.root / "ForeverTome.lua"
        self.output_dir = self.root / "catalogs"
        self.raw        = source_bytes(make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Synthetic watcher item"}),
        ])))
        self.source.write_bytes(self.raw)
        self.watcher = watch.CatalogWatcher(self.source, self.output_dir)
        self.addCleanup(self.temporary.cleanup)

    def write_next_save(self):
        database = make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Synthetic watcher item"}),
            ("item.received", {"item_id": 100, "quantity": 2, "source_status": "unknown"}),
        ]))
        self.raw = source_bytes(database)
        self.source.write_bytes(self.raw)

    def test_first_sync_creates_categories_without_snapshots_and_restarted_sync_skips(self):
        document = self.watcher.sync()
        latest   = self.output_dir / "latest.json"
        files    = {path.name: path.read_bytes() for path in self.output_dir.glob("*.json")}
        modified = latest.stat().st_mtime_ns
        self.assertEqual(len(files), 8)
        self.assertEqual(json.loads(latest.read_text(encoding="utf-8")), document)
        for name, raw in files.items():
            if name in {f"{category}.json" for category in watch.CATEGORIES}:
                self.assertEqual(json.loads(raw), watch.category_catalog(document, Path(name).stem))
            else:
                self.assertEqual(json.loads(raw), document)
        self.assertIsNone(self.watcher.sync())
        self.assertIsNone(watch.CatalogWatcher(self.source, self.output_dir).sync())
        self.assertEqual(latest.stat().st_mtime_ns, modified)
        self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.glob("*.json")}, files)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_loot_links_survive_category_exports_and_subsequent_recording_clears(self):
        candidate = {"creature_id": 300, "guid": "Creature-0-1-2-3-300-000001", "reaction": 2}
        session   = make_session(1, [
            ("loot.opened", {"loot_session_id": "loot-1", "target_candidate": candidate}),
            ("loot.visible", {"item_id": 100, "link": LINK_A, "quantity": 1,
                              "loot_session_id": "loot-1", "source_status": "unknown",
                              "sources": [], "source_candidates": [candidate]}),
            ("item.received", {"item_id": 100, "link": LINK_A, "quantity": 1,
                               "loot_session_id": "loot-1", "loot_match_status": "candidate",
                               "source_status": "unknown", "source_candidates": [candidate]}),
        ])
        observations = session["observations"]
        observations[1]["related_observation_ids"] = [observations[0]["observation_id"]]
        observations[2]["related_observation_ids"] = [observations[1]["observation_id"]]
        self.source.write_bytes(source_bytes(make_database(session)))
        self.watcher.sync()
        next_database = make_database(make_session(2, [
            ("item.metadata", {"item_id": 101, "name": "New recording item"}),
        ]))
        next_database["next_session"] = 2
        self.source.write_bytes(source_bytes(next_database))
        self.watcher.sync()
        for category in ("items", "npcs", "monsters"):
            document = json.loads((self.output_dir / f"{category}.json").read_bytes())
            records  = {row["id"]: row for row in document["records"]}
            self.assertTrue(all(row["observation_id"] in records for row in observations))
            for entry in document["entries"]:
                if entry["nativeId"] in (100, 300):
                    facts = [fact for fact in entry["facts"] if fact["type"] == "loot.provenance"]
                    self.assertEqual(len(facts), 2)
                    self.assertTrue(all(fact["data"]["source_status"] == "unknown" for fact in facts))

    def test_new_save_appends_evidence_without_creating_snapshots(self):
        first = self.watcher.sync()
        self.write_next_save()
        second = self.watcher.sync()
        self.assertIsNotNone(second)
        self.assertNotEqual(first["source"]["sha256"], second["source"]["sha256"])
        self.assertEqual(second["summary"]["observationCount"], 2)
        self.assertFalse(list(self.output_dir.glob("catalog-*.json")))
        self.assertEqual(json.loads((self.output_dir / "latest.json").read_text(encoding="utf-8")), second)
        items = json.loads((self.output_dir / "items.json").read_bytes())
        self.assertEqual(len(items["entries"]), 1)
        self.assertEqual(len(items["records"]), 2)
        self.assertEqual(len(items["entries"][0]["sourceIds"]), 2)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertIsNone(self.watcher.sync())

    def test_category_files_preserve_unique_entities_variants_and_evidence(self):
        session = make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Variant A", "link": LINK_A,
                               "icon_id": 123, "stats": {"ARMOR": 9}}),
            ("item.metadata", {"item_id": 100, "name": "Variant A", "link": LINK_A,
                               "icon_id": 123, "stats": {"ARMOR": 9}}),
            ("item.metadata", {"item_id": 100, "name": "Variant B", "link": LINK_B,
                               "icon_id": 456, "stats": {"ARMOR": 12}}),
            ("unit.sighting", {"creature_id": 10, "name": "Hostile", "reaction": 2}),
            ("unit.sighting", {"creature_id": 11, "name": "Friendly", "reaction": 5}),
            ("unit.sighting", {"creature_id": 12, "name": "Neutral", "reaction": 4}),
            ("unit.sighting", {"creature_id": 13, "name": "Unreadable", "reaction": True}),
            ("spell.metadata", {"spell_id": 20, "name": "Spell"}),
            ("talent.metadata", {"entity_type": "node", "entity_id": 30, "info": {"name": "Talent"}}),
            ("quest.metadata", {"quest_id": 40, "title": "Quest"}),
        ])
        self.raw = source_bytes(make_database(session))
        self.source.write_bytes(self.raw)
        document = self.watcher.sync()
        for category in watch.CATEGORIES:
            with self.subTest(category=category):
                view = json.loads((self.output_dir / f"{category}.json").read_bytes())
                self.assertEqual(view, watch.category_catalog(document, category))
                self.assertEqual(view["exportId"], document["exportId"])
                self.assertEqual(view["source"], document["source"])
                self.assertEqual(view["contexts"], document["contexts"])
                self.assertEqual(len(view["entries"]), len({entry["key"] for entry in view["entries"]}))
                records = {record["id"] for record in view["records"]}
                for entry in view["entries"]:
                    self.assertTrue(set(entry["sourceIds"]) <= records)
        items    = json.loads((self.output_dir / "items.json").read_bytes())
        monsters = json.loads((self.output_dir / "monsters.json").read_bytes())
        npcs     = json.loads((self.output_dir / "npcs.json").read_bytes())
        self.assertEqual(len(items["entries"]), 1)
        self.assertEqual({variant["link"] for variant in items["entries"][0]["variants"]}, {LINK_A, LINK_B})
        self.assertEqual(items["entries"][0]["display"]["stats"], {"ARMOR": 9})
        self.assertEqual(items["entries"][0]["display"]["iconId"], 123)
        self.assertEqual({entry["nativeId"] for entry in monsters["entries"]}, {10, 12})
        self.assertEqual({entry["nativeId"] for entry in npcs["entries"]}, {10, 11, 12, 13})
        self.assertEqual(monsters["selection"]["method"], "observed_reaction")
        self.assertEqual(len(items["records"]), 3)

    def test_cleared_history_and_new_session_keep_previous_category_evidence(self):
        first = self.watcher.sync()
        self.source.write_bytes(source_bytes(make_database()))
        cleared = watch.CatalogWatcher(self.source, self.output_dir).sync()
        self.assertEqual(cleared["summary"]["observationCount"], 0)
        items = json.loads((self.output_dir / "items.json").read_bytes())
        self.assertEqual(items["entries"], first["catalog"]["items"])
        self.assertEqual(len(items["records"]), 1)
        session = make_session(2, [
            ("item.received", {"item_id": 100, "quantity": 3}),
            ("item.metadata", {"item_id": 200, "name": "New item"}),
        ])
        database                 = make_database(session)
        database["next_session"] = 2
        self.source.write_bytes(source_bytes(database))
        restarted = watch.CatalogWatcher(self.source, self.output_dir)
        latest    = restarted.sync()
        items     = json.loads((self.output_dir / "items.json").read_bytes())
        self.assertEqual({entry["nativeId"] for entry in items["entries"]}, {100, 200})
        self.assertEqual(items["entries"][0]["display"]["name"], "Synthetic watcher item")
        self.assertEqual(len(items["entries"][0]["sourceIds"]), 2)
        self.assertEqual(len(items["records"]), 3)
        self.assertEqual(len(items["sessions"]), 2)
        self.assertEqual(items["source"], latest["source"])
        self.assertEqual(latest["summary"]["observationCount"], 2)
        self.assertIsNone(restarted.sync())
        self.assertIsNone(watch.CatalogWatcher(self.source, self.output_dir).sync())
        self.assertFalse(list(self.output_dir.glob("catalog-*.json")))

    def test_overlapping_saves_merge_facts_variants_and_partial_retry_once(self):
        first = make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Variant A", "link": LINK_A}),
        ])
        second = make_session(2, [
            ("item.metadata", {"item_id": 100, "name": "Variant A", "link": LINK_A}),
            ("item.metadata", {"item_id": 100, "name": "Variant B", "link": LINK_B}),
        ])
        self.source.write_bytes(source_bytes(make_database(first)))
        self.watcher.sync()
        self.source.write_bytes(source_bytes(make_database(first, second)))
        replace = watch.os.replace

        def fail_latest(source, destination):
            if Path(destination).name == "latest.json":
                raise OSError("synthetic final publication failure")
            return replace(source, destination)

        with patch.object(watch.os, "replace", side_effect=fail_latest):
            with self.assertRaises(OSError):
                self.watcher.sync()
        watch.CatalogWatcher(self.source, self.output_dir).sync()
        items = json.loads((self.output_dir / "items.json").read_bytes())
        entry = items["entries"][0]
        self.assertEqual(len(items["records"]), 3)
        self.assertEqual(len(entry["sourceIds"]), 3)
        self.assertEqual(len(entry["facts"]), 2)
        self.assertEqual(sorted(len(fact["sourceIds"]) for fact in entry["facts"]), [1, 2])
        self.assertEqual(len(entry["variants"]), 2)
        self.assertEqual(sorted(len(variant["sourceIds"]) for variant in entry["variants"]), [1, 2])

    def test_monster_selection_includes_npc_evidence_across_cleared_saves(self):
        for serial, reaction in enumerate((5, 2, 5), 1):
            session = make_session(serial, [
                ("unit.sighting", {"creature_id": 10, "name": "Changing reaction", "reaction": reaction}),
            ])
            database                 = make_database(session)
            database["next_session"] = serial
            self.source.write_bytes(source_bytes(database))
            watch.CatalogWatcher(self.source, self.output_dir).sync()
        monsters = json.loads((self.output_dir / "monsters.json").read_bytes())
        npcs     = json.loads((self.output_dir / "npcs.json").read_bytes())
        self.assertEqual(monsters["entries"], npcs["entries"])
        self.assertEqual(monsters["records"], npcs["records"])
        self.assertEqual(len(monsters["records"]), 3)

    def test_conflicting_observation_rejects_entire_export_without_writes(self):
        self.watcher.sync()
        before = {path.name: path.read_bytes() for path in self.output_dir.iterdir()}
        self.source.write_bytes(source_bytes(make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Conflicting name"}),
        ]))))
        with self.assertRaisesRegex(ValueError, "[Cc]onflict"):
            self.watcher.sync()
        self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.iterdir()}, before)

    def test_conflicting_observation_cannot_move_between_categories(self):
        self.watcher.sync()
        before = {path.name: path.read_bytes() for path in self.output_dir.iterdir()}
        for kind, data in (("spell.metadata", {"spell_id": 200, "name": "Conflicting spell"}),
                           ("player.state", {"state_event": "SYNTHETIC"})):
            with self.subTest(kind=kind):
                self.source.write_bytes(source_bytes(make_database(make_session(1, [(kind, data)]))))
                with self.assertRaisesRegex(ValueError, "[Cc]onflict"):
                    self.watcher.sync()
                self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.iterdir()}, before)

    def test_upgrade_recovers_rotated_history_from_legacy_snapshots_and_latest(self):
        with patch.dict(watch.build_catalog.__globals__, {"GENERATOR_VERSION": "0.2.4"}):
            old = self.watcher.sync()
        snapshot = self.output_dir / f"catalog-20260101T000000Z-{old['exportId']}.json"
        snapshot.write_text(json.dumps(old), encoding="utf-8")
        before = snapshot.read_bytes()
        session = make_session(2, [("item.metadata", {"item_id": 200, "name": "Latest legacy item"})])
        database                 = make_database(session)
        database["next_session"] = 2
        with patch.dict(watch.build_catalog.__globals__, {"GENERATOR_VERSION": "0.2.4"}):
            legacy = watch.build_catalog(database, "b" * 64)
        for category in watch.CATEGORIES:
            (self.output_dir / f"{category}.json").write_text(
                json.dumps(watch.category_catalog(legacy, category)), encoding="utf-8")
        (self.output_dir / "latest.json").write_text(json.dumps(legacy), encoding="utf-8")
        self.source.write_bytes(source_bytes(make_database()))
        restarted = watch.CatalogWatcher(self.source, self.output_dir)
        document  = restarted.sync()
        items     = json.loads((self.output_dir / "items.json").read_bytes())
        self.assertEqual(document["summary"]["observationCount"], 0)
        self.assertEqual({entry["nativeId"] for entry in items["entries"]}, {100, 200})
        self.assertEqual(len(items["records"]), 2)
        self.assertEqual(snapshot.read_bytes(), before)
        self.assertEqual(list(self.output_dir.glob("catalog-*.json")), [snapshot])
        self.assertIsNone(restarted.sync())
        self.assertIsNone(watch.CatalogWatcher(self.source, self.output_dir).sync())

    def test_invalid_legacy_snapshot_is_preserved_before_any_writes(self):
        with patch.dict(watch.build_catalog.__globals__, {"GENERATOR_VERSION": "0.2.4"}):
            document = self.watcher.sync()
        snapshot = self.output_dir / "catalog-20260101T000000Z-invalid.json"
        for invalid in ({"format": "foreign"}, {**document, "catalog": []}):
            with self.subTest(invalid=invalid["format"]):
                snapshot.write_text(json.dumps(invalid), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in self.output_dir.iterdir()}
                with self.assertRaises(ValueError):
                    watch.CatalogWatcher(self.source, self.output_dir).sync()
                self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.iterdir()}, before)

    def test_category_records_include_related_closure_in_session_sequence_order(self):
        session = make_session(1, [
            ("player.state", {"state_event": "SYNTHETIC"}),
            ("world.context", {"zone": "Synthetic zone"}),
            ("unit.sighting", {"creature_id": 10, "name": "Hostile", "reaction": 2}),
            ("quest.turned_in", {"quest_id": 40}),
        ])
        rows = session["observations"]
        rows[1]["related_observation_ids"] = [rows[0]["observation_id"]]
        rows[2]["related_observation_ids"] = [rows[1]["observation_id"]]
        rows[2]["location"] = {
            "status": "available", "subject": "player", "coordinate_system": "ui_map_normalized",
            "ui_map_id": 1411, "x": 0.2, "y": 0.3,
        }
        self.raw = source_bytes(make_database(session))
        self.source.write_bytes(self.raw)
        document = self.watcher.sync()
        view     = watch.category_catalog(document, "monsters")
        self.assertEqual([row["sequence"] for row in view["records"]], [1, 2, 3])
        self.assertEqual(view["records"][2]["location"]["subject"], "player")
        self.assertEqual(view["records"][2]["location"]["mapX"], 20)
        self.assertEqual(view["sessions"], document["sessions"])
        self.assertEqual(watch.category_catalog(document, "quests")["records"][0]["sequence"], 4)

    def test_restart_repairs_missing_and_stale_categories_without_rewriting_latest(self):
        document = self.watcher.sync()
        latest   = self.output_dir / "latest.json"
        before   = latest.read_bytes()
        modified = latest.stat().st_mtime_ns
        (self.output_dir / "items.json").unlink()
        stale             = watch.category_catalog(document, "quests")
        stale["exportId"] = "f" * 64
        watch.atomic_write(self.output_dir / "quests.json", json.dumps(stale).encode("utf-8"))
        restarted = watch.CatalogWatcher(self.source, self.output_dir)
        self.assertEqual(restarted.sync(), document)
        for category in ("items", "quests"):
            self.assertEqual(json.loads((self.output_dir / f"{category}.json").read_bytes()),
                             watch.category_catalog(document, category))
        self.assertEqual(latest.read_bytes(), before)
        self.assertEqual(latest.stat().st_mtime_ns, modified)
        self.assertIsNone(restarted.sync())

    def test_generator_upgrade_rebuilds_unchanged_save_without_new_snapshots(self):
        with patch.dict(watch.build_catalog.__globals__, {"GENERATOR_VERSION": "0.2.2"}):
            first = self.watcher.sync()
        snapshot = self.output_dir / f"catalog-20260101T000000Z-{first['exportId']}.json"
        snapshot.write_text(json.dumps(first), encoding="utf-8")
        snapshots = {path.name: path.read_bytes() for path in self.output_dir.glob("catalog-*.json")}
        self.assertEqual(len(snapshots), 1)
        self.assertTrue(all(first["exportId"] in name for name in snapshots))
        restarted = watch.CatalogWatcher(self.source, self.output_dir)
        second    = restarted.sync()
        self.assertIsNotNone(second)
        self.assertEqual(second["source"], first["source"])
        self.assertNotEqual(second["generatorVersion"], first["generatorVersion"])
        self.assertNotEqual(second["exportId"], first["exportId"])
        self.assertEqual(len(list(self.output_dir.glob("catalog-*.json"))), 1)
        for name, raw in snapshots.items():
            self.assertEqual((self.output_dir / name).read_bytes(), raw)
        for category in watch.CATEGORIES:
            view = json.loads((self.output_dir / f"{category}.json").read_bytes())
            self.assertEqual(view["generatorVersion"], second["generatorVersion"])
            self.assertEqual(view["exportId"], second["exportId"])
        self.assertEqual(json.loads((self.output_dir / "latest.json").read_bytes()), second)
        self.assertIsNone(restarted.sync())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_unrelated_or_wrong_category_file_is_preserved_before_any_other_write(self):
        document = self.watcher.sync()
        path     = self.output_dir / "items.json"
        for foreign in (b"private unrelated content", json.dumps(watch.category_catalog(document, "quests")).encode("utf-8")):
            with self.subTest(foreign=foreign[:30]):
                watch.atomic_write(path, foreign)
                before = {entry.name: entry.read_bytes() for entry in self.output_dir.iterdir()}
                self.write_next_save()
                with self.assertRaises(ValueError):
                    self.watcher.sync()
                self.assertEqual({entry.name: entry.read_bytes() for entry in self.output_dir.iterdir()}, before)
                self.assertEqual(path.read_bytes(), foreign)

    def test_partial_category_publication_retains_latest_and_recovers_on_restart(self):
        first          = self.watcher.sync()
        latest         = self.output_dir / "latest.json"
        before         = latest.read_bytes()
        atomic_replace = watch.os.replace
        self.write_next_save()

        def fail_items(source, destination):
            if Path(destination).name == "items.json":
                raise OSError("synthetic category publication failure")
            return atomic_replace(source, destination)

        with patch.object(watch.os, "replace", side_effect=fail_items):
            with self.assertRaises(OSError):
                self.watcher.sync()
        self.assertEqual(latest.read_bytes(), before)
        spells = json.loads((self.output_dir / "spells.json").read_bytes())
        items  = json.loads((self.output_dir / "items.json").read_bytes())
        self.assertNotEqual(spells["exportId"], first["exportId"])
        self.assertEqual(items["exportId"], first["exportId"])
        self.assertFalse(list(self.output_dir.glob("*.tmp")))
        restarted = watch.CatalogWatcher(self.source, self.output_dir)
        second    = restarted.sync()
        self.assertEqual(second["summary"]["observationCount"], 2)
        for category in watch.CATEGORIES:
            self.assertEqual(json.loads((self.output_dir / f"{category}.json").read_bytes()),
                             watch.category_catalog(second, category))
        self.assertEqual(json.loads(latest.read_bytes()), second)
        self.assertIsNone(restarted.sync())

    def test_partial_or_executable_save_keeps_previous_json_and_recovers(self):
        self.watcher.sync()
        files = {path.name: path.read_bytes() for path in self.output_dir.iterdir()}
        for raw in (self.raw[:-10], self.raw + b"\nos.execute('exit 0')\n"):
            with self.subTest(source=raw[-30:]):
                self.source.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.watcher.sync()
                self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.iterdir()}, files)
                self.assertEqual(self.source.read_bytes(), raw)
        self.write_next_save()
        document = self.watcher.sync()
        self.assertEqual(document["summary"]["observationCount"], 2)

    def test_unrelated_latest_json_is_preserved(self):
        self.output_dir.mkdir()
        latest = self.output_dir / "latest.json"
        for raw in (b"private unrelated content", b'{"format":"another-tool","schemaVersion":1}'):
            with self.subTest(existing=raw):
                latest.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.watcher.sync()
                self.assertEqual(latest.read_bytes(), raw)
                self.assertEqual(list(self.output_dir.iterdir()), [latest])
                self.assertEqual(self.source.read_bytes(), self.raw)

    def test_failed_atomic_replace_keeps_previous_latest_and_cleans_temporary_file(self):
        self.watcher.sync()
        latest = self.output_dir / "latest.json"
        before = latest.read_bytes()
        self.write_next_save()
        with patch.object(watch.os, "replace", side_effect=OSError("synthetic replacement failure")):
            with self.assertRaises(OSError):
                self.watcher.sync()
        self.assertEqual(latest.read_bytes(), before)
        self.assertFalse(list(self.output_dir.glob("*.tmp")))
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.watcher.sync()["summary"]["observationCount"], 2)

    def test_failed_category_publication_keeps_all_previous_files_and_recovers(self):
        self.watcher.sync()
        before = {path.name: path.read_bytes() for path in self.output_dir.iterdir()}
        self.write_next_save()
        with patch.object(watch.os, "replace", side_effect=OSError("synthetic publication failure")):
            with self.assertRaises(OSError):
                self.watcher.sync()
        self.assertEqual({path.name: path.read_bytes() for path in self.output_dir.iterdir()}, before)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.watcher.sync()["summary"]["observationCount"], 2)

    def test_unchanged_source_recovers_latest_replaced_by_an_older_snapshot(self):
        first     = self.watcher.sync()
        latest    = self.output_dir / "latest.json"
        first_raw = latest.read_bytes()
        self.write_next_save()
        second = self.watcher.sync()
        watch.atomic_write(latest, first_raw)
        self.assertEqual(json.loads(latest.read_bytes()), first)
        recovered = self.watcher.sync()
        self.assertEqual(recovered, second)
        self.assertEqual(json.loads(latest.read_bytes()), second)
        self.assertIsNone(self.watcher.sync())

    def test_unchanged_source_rejects_foreign_latest_replacement(self):
        self.watcher.sync()
        latest  = self.output_dir / "latest.json"
        foreign = b'{"format":"different-tool","schemaVersion":1}'
        watch.atomic_write(latest, foreign)
        with self.assertRaises(ValueError):
            self.watcher.sync()
        self.assertEqual(latest.read_bytes(), foreign)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_source_changed_during_conversion_keeps_previous_latest_and_retries(self):
        self.watcher.sync()
        latest   = self.output_dir / "latest.json"
        before   = latest.read_bytes()
        build    = watch.build_catalog
        next_raw = self.raw
        self.write_next_save()

        def changed_after_build(database, digest):
            document = build(database, digest)
            self.source.write_bytes(next_raw)
            return document

        with patch.object(watch, "build_catalog", side_effect=changed_after_build):
            with self.assertRaisesRegex(ValueError, "changed during catalog conversion"):
                self.watcher.sync()
        self.assertEqual(latest.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), next_raw)
        self.write_next_save()
        self.assertEqual(self.watcher.sync()["summary"]["observationCount"], 2)

    def test_once_cli_completes_and_invalid_input_keeps_previous_output(self):
        command = [sys.executable, str(MODULE_PATH), str(self.source), "--output-dir", str(self.output_dir), "--once"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        latest = self.output_dir / "latest.json"
        before = latest.read_bytes()
        self.source.write_bytes(b"return {}")
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(latest.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), b"return {}")
        for interval in ("0", "-1", "nan", "inf"):
            with self.subTest(interval=interval):
                process = subprocess.run([*command, "--interval", interval], capture_output=True, text=True, timeout=30)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(latest.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
