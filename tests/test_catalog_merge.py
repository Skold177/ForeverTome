import copy
import hashlib
import unittest

from test_catalog import LINK_A, LINK_B, catalog, make_database, make_session, source_bytes
from tools.catalog_merge import merge_category, validate_history
from tools.watch_catalog import CATEGORIES, category_catalog


def category_view(category, *sessions):
    database = make_database(*sessions)
    database["next_session"] = max((int(session["session"]["session_id"].rsplit("-", 1)[1])
                                    for session in sessions), default=0)
    digest   = hashlib.sha256(source_bytes(database)).hexdigest()
    document = catalog.build_catalog(database, digest)
    return category_catalog(document, category)


class CategoryMergeTests(unittest.TestCase):
    def test_append_deduplicates_entities_facts_variants_and_records(self):
        metadata = {"item_id": 100, "name": "Original", "link": LINK_A, "stats": {"ARMOR": 9}}
        first    = make_session(1, [("item.metadata", metadata)])
        second   = make_session(2, [
            ("item.metadata", metadata),
            ("item.metadata", {"item_id": 100, "name": "Other variant", "link": LINK_B}),
            ("item.metadata", {"item_id": 200, "name": "New item"}),
        ])
        previous = category_view("items", first)
        current  = category_view("items", first, second)
        before   = copy.deepcopy((previous, current))
        result   = merge_category(previous, current)
        entries  = {entry["nativeId"]: entry for entry in result["entries"]}
        self.assertEqual(len(result["records"]), 4)
        self.assertEqual(set(entries), {100, 200})
        self.assertEqual(len(entries[100]["sourceIds"]), 3)
        self.assertEqual(len(entries[100]["facts"]), 2)
        self.assertEqual(len(entries[100]["variants"]), 2)
        original = next(fact for fact in entries[100]["facts"] if fact["data"] == metadata)
        self.assertEqual(len(original["sourceIds"]), 2)
        self.assertEqual(result, merge_category(result, current))
        self.assertEqual((previous, current), before)
        self.assertEqual(merge_category(None, current), current)

    def test_new_recordings_and_empty_saves_preserve_prior_evidence(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Old"}),
        ]))
        current  = category_view("items", make_session(2, [
            ("item.metadata", {"item_id": 200, "name": "New"}),
        ], locale="frFR"))
        result   = merge_category(previous, current)
        empty    = category_view("items")
        cleared  = merge_category(result, empty)
        self.assertEqual(len(result["contexts"]), 2)
        self.assertEqual(len(result["sessions"]), 2)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(len(result["entries"]), 2)
        for field in ("contexts", "sessions", "records", "entries"):
            self.assertEqual(cleared[field], result[field])
        for field in ("source", "exportId", "generatorVersion", "semantics"):
            self.assertEqual(cleared[field], empty[field])

    def test_all_entity_categories_retain_entries_through_empty_saves(self):
        session = make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item"}),
            ("unit.sighting", {"creature_id": 10, "name": "Hostile", "reaction": 2}),
            ("spell.metadata", {"spell_id": 20, "name": "Spell"}),
            ("talent.metadata", {"entity_type": "node", "entity_id": 30, "info": {"name": "Talent"}}),
            ("quest.metadata", {"quest_id": 40, "title": "Quest"}),
            ("recipe.metadata", {"recipe_id": 50, "name": "Recipe"}),
            ("profession.snapshot", {"professionID": 60, "professionName": "Profession"}),
            ("merchant.offer", {"currency_id": 70, "currency_name": "Currency"}),
            ("unit.sighting", {"source_guid": "GameObject-0-1-2-3-80-000001", "name": "Object"}),
        ])
        session["observations"][0]["location"] = {
            "status": "available", "subject": "player", "coordinate_system": "ui_map_normalized",
            "ui_map_id": 1411, "x": 0.2, "y": 0.3,
        }
        for category in CATEGORIES:
            if category == "gathering":
                continue
            with self.subTest(category=category):
                previous = category_view(category, session)
                result   = merge_category(previous, category_view(category))
                self.assertEqual(len(result["entries"]), 1)
                self.assertEqual(result["entries"], previous["entries"])

    def test_display_and_details_use_richest_observed_metadata(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Rich metadata", "icon_id": 123,
                               "stats": {"ARMOR": 9}, "stats_status": "available"}),
        ]))
        current  = category_view("items", make_session(2, [
            ("item.received", {"item_id": 100, "name": "Receipt name", "quantity": 1}),
        ]))
        result   = merge_category(previous, current)
        entry    = result["entries"][0]
        self.assertEqual(entry["display"], previous["entries"][0]["display"])
        self.assertEqual(entry["details"], previous["entries"][0]["details"])
        self.assertEqual(entry["displaySourceId"], previous["entries"][0]["displaySourceId"])
        self.assertEqual(len(entry["facts"]), 2)
        self.assertEqual(merge_category(current, previous)["entries"][0]["display"], entry["display"])

    def test_same_session_accepts_updated_diagnostics_and_related_closure(self):
        first   = make_session(1, [
            ("player.state", {"state_event": "SYNTHETIC"}),
            ("item.metadata", {"item_id": 100, "name": "Item"}),
        ])
        rows    = first["observations"]
        rows[1]["related_observation_ids"] = [rows[0]["observation_id"]]
        second  = copy.deepcopy(first)
        second["diagnostics"]["counts"]["synthetic:missing"] = 2
        previous = category_view("items", first)
        current  = category_view("items", second)
        result   = merge_category(previous, current)
        self.assertEqual(result["sessions"], current["sessions"])
        self.assertEqual(result["records"], previous["records"])
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(merge_category(result, previous)["sessions"], current["sessions"])

    def test_conflicting_raw_observations_headers_and_contexts_are_rejected(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item", "link": LINK_A}),
        ]))
        conflicts = [
            ("record", lambda view: view["records"][0]["data"].update(name="Changed")),
            ("header", lambda view: view["sessions"][0]["data"].update(addon_version="other")),
            ("context", lambda view: view["contexts"][0]["client"].update(locale="frFR")),
            ("entity", lambda view: view["entries"][0].update(nativeId=200)),
            ("fact", lambda view: view["entries"][0]["facts"][0]["data"].update(name="Changed")),
            ("variant", lambda view: view["entries"][0]["variants"][0].update(link=LINK_B)),
        ]
        for label, mutate in conflicts:
            with self.subTest(identity=label):
                current = copy.deepcopy(previous)
                mutate(current)
                with self.assertRaises(ValueError):
                    merge_category(previous, current)

    def test_derived_record_changes_do_not_conflict_with_unchanged_evidence(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item"}),
        ]))
        current  = copy.deepcopy(previous)
        current["records"][0]["entities"].append({"key": "new-projection", "role": "new", "path": "data"})
        result = merge_category(previous, current)
        self.assertEqual(result["records"], current["records"])

    def test_boolean_and_numeric_payloads_are_distinct_evidence(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item", "crafting_reagent": True}),
        ]))
        current  = copy.deepcopy(previous)
        current["records"][0]["data"]["crafting_reagent"] = 1
        with self.assertRaisesRegex(ValueError, "Conflicting category observation"):
            merge_category(previous, current)

    def test_gathering_preserves_casts_and_accepts_new_spell_names(self):
        first = make_session(1, [
            ("spell.succeeded", {"spell_id": 2366, "actor": "player"}),
        ])
        first["observations"][0]["capture"]  = {"event": "UNIT_SPELLCAST_SUCCEEDED"}
        first["observations"][0]["evidence"] = {"method": "direct_event"}
        previous = category_view("gathering", first)
        metadata = make_session(2, [("spell.metadata", {"spell_id": 2366, "name": "Herbalism"})])
        current  = category_view("gathering", first, metadata)
        result   = merge_category(previous, current)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["spellName"], "Herbalism")
        second = make_session(3, [("spell.succeeded", {"spell_id": 2575, "actor": "player"})])
        second["observations"][0]["capture"]  = {"event": "UNIT_SPELLCAST_SUCCEEDED"}
        second["observations"][0]["evidence"] = {"method": "direct_event"}
        result = merge_category(result, category_view("gathering", second))
        self.assertEqual(len(result["entries"]), 2)
        self.assertEqual({entry["profession"] for entry in result["entries"]}, {"herbalism", "mining"})
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["entries"], merge_category(result, category_view("gathering"))["entries"])

    def test_malformed_existing_evidence_is_rejected(self):
        current = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item"}),
        ]))
        previous = copy.deepcopy(current)
        previous["records"] = []
        with self.assertRaises(ValueError):
            merge_category(previous, current)
        previous = copy.deepcopy(current)
        previous["entries"][0]["facts"].append(copy.deepcopy(previous["entries"][0]["facts"][0]))
        with self.assertRaises(ValueError):
            merge_category(previous, current)

    def test_history_rejects_record_conflicts_that_change_category(self):
        previous = category_view("items", make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item"}),
        ]))
        database = make_database(make_session(1, [
            ("spell.metadata", {"spell_id": 100, "name": "Spell"}),
        ]))
        digest   = hashlib.sha256(source_bytes(database)).hexdigest()
        current  = catalog.build_catalog(database, digest)
        with self.assertRaisesRegex(ValueError, "Conflicting category observation"):
            validate_history([previous], current)

    def test_history_accepts_overlap_and_preserved_evidence_after_clear(self):
        database = make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Item"}),
            ("spell.metadata", {"spell_id": 100, "name": "Spell"}),
        ]))
        digest   = hashlib.sha256(source_bytes(database)).hexdigest()
        current  = catalog.build_catalog(database, digest)
        previous = [category_catalog(current, category) for category in CATEGORIES]
        validate_history(previous, current)
        empty = catalog.build_catalog(make_database(), "0" * 64)
        validate_history(previous, empty)


if __name__ == "__main__":
    unittest.main()
