import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT        = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_catalog.py"
SPEC        = importlib.util.spec_from_file_location("forevertome_catalog", MODULE_PATH)
catalog     = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = catalog
SPEC.loader.exec_module(catalog)

EXPORT_PATH = ROOT / "tools" / "export_saved_variables.py"
EXPORT_SPEC = importlib.util.spec_from_file_location("catalog_test_export", EXPORT_PATH)
export      = importlib.util.module_from_spec(EXPORT_SPEC)
sys.modules[EXPORT_SPEC.name] = export
EXPORT_SPEC.loader.exec_module(export)

IDENTITY = "abcdef0123456789abcdef0123456789"
SHA256   = hashlib.sha256(b"synthetic catalog fixture").hexdigest()
LINK_A   = "|cffffffff|Hitem:100:0:0:0:0:0:0:1|h[Synthetic sword]|h|r"
LINK_B   = "|cffffffff|Hitem:100:0:0:0:0:0:0:2|h[Synthetic sword]|h|r"
BUCKETS  = {"items", "quests", "npcs", "spells", "talents", "recipes", "maps", "professions", "currencies"}
ACTIONS  = {
    "quest.accepted", "quest.turned_in", "quest.reward_received", "quest.removed",
    "quest.objective_delta", "quest.ready", "item.received", "inventory.delta",
    "spell.succeeded", "spell.learned", "recipe.learned", "craft.result",
    "loot.opened", "loot.closed", "loot.slot_cleared", "merchant.opened",
    "merchant.closed", "player.state", "spellbook.changed", "gathering.attempt",
}


def make_session(serial, records, **client_fields):
    session_id = f"{IDENTITY}-{serial}"
    client     = {"version": "1.60.1", "build": "69893", "locale": "enUS"}
    client.update(client_fields)
    observations = []
    for sequence, (kind, data) in enumerate(records, 1):
        observations.append({
            "session_id": session_id, "observation_id": f"{session_id}:{sequence}",
            "sequence": sequence, "kind": kind, "elapsed_s": sequence / 4,
            "capture": {"event": "SYNTHETIC_EVENT"}, "data": copy.deepcopy(data),
            "evidence": {"method": "synthetic_fixture"}, "missing_fields": {},
            "related_observation_ids": [],
        })
    return {
        "session": {
            "session_id": session_id, "product": "WF", "client": client,
            "addon_version": "0.2.2", "adapter_id": "forever-beta-69893-source-v1",
            "capabilities": {"item_metadata": {"status": "wf_unverified", "enabled": True}},
        },
        "observations": observations,
        "diagnostics": {"counts": {"synthetic:missing": 1}, "distinct": 1},
    }


def make_database(*sessions):
    entries = list(sessions)
    count   = sum(len(session["observations"]) for session in entries)
    return {
        "schema_version": 1, "synthetic": True, "installation_id": IDENTITY,
        "next_session": len(entries), "settings": {"paused": False},
        "record_count": count, "estimated_bytes": count * 512, "sessions": entries,
    }


def lua_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "{" + ",".join(lua_value(entry) for entry in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{lua_value(key)}]={lua_value(entry)}" for key, entry in value.items()) + "}"
    raise TypeError(f"Unsupported fixture value: {type(value).__name__}")


def source_bytes(database):
    document = "ForeverTomeDB = " + lua_value(database) + "\n"
    return document.encode("utf-8")


class CatalogTests(unittest.TestCase):
    def assert_references(self, document):
        rows     = document["transactions"] + document["observations"]
        records  = {row["id"]: row for row in rows}
        contexts = {entry["id"] for entry in document["contexts"]}
        sessions = {entry["id"]: entry for entry in document["sessions"]}
        entities = {entry["key"]: entry for bucket in document["catalog"].values() for entry in bucket}
        self.assertEqual(len(rows), len(records))
        self.assertEqual(sum(len(bucket) for bucket in document["catalog"].values()), len(entities))
        for row in rows:
            self.assertIn(row["contextId"], contexts)
            self.assertEqual(row["contextId"], sessions[row["sessionId"]]["contextId"])
            self.assertTrue(set(row["relatedIds"]) <= records.keys())
            for reference in row["entities"]:
                entity = entities[reference["key"]]
                self.assertEqual(entity["contextId"], row["contextId"])
                self.assertTrue(reference["role"])
                self.assertTrue(reference["path"])
                self.assertIn(row["id"], entity["sourceIds"])
        for entity in entities.values():
            self.assertIn(entity["contextId"], contexts)
            self.assertIsInstance(entity["details"], dict)
            self.assertTrue(entity["sourceIds"])
            self.assertTrue(set(entity["sourceIds"]) <= records.keys())
            if "displaySourceId" in entity:
                self.assertIn(entity["displaySourceId"], entity["sourceIds"])
            for fact in entity["facts"]:
                self.assertTrue(fact["id"])
                self.assertTrue(fact["type"])
                self.assertTrue(fact["path"])
                self.assertTrue(fact["sourceIds"])
                self.assertTrue(set(fact["sourceIds"]) <= set(entity["sourceIds"]))
            for variant in entity.get("variants", []):
                self.assertTrue(variant["key"])
                self.assertTrue(variant["sourceIds"])
                self.assertTrue(set(variant["sourceIds"]) <= set(entity["sourceIds"]))
        catalog.validate_catalog(document)

    def test_empty_export_has_complete_catalog_and_source_envelope(self):
        document = catalog.build_catalog(make_database(), SHA256)
        self.assertEqual(document["format"], "forevertome.website-catalog")
        self.assertEqual(document["schemaVersion"], 1)
        self.assertEqual(document["source"], {
            "sha256": SHA256, "schemaVersion": 1, "synthetic": True, "observationCount": 0,
        })
        self.assertEqual(set(document["catalog"]), BUCKETS)
        self.assertTrue(all(value == [] for value in document["catalog"].values()))
        self.assertEqual(document["summary"]["observationCount"], 0)
        self.assertEqual(document["transactions"], [])
        self.assertEqual(document["observations"], [])
        self.assert_references(document)

    def test_every_supported_kind_is_preserved_once_and_classified(self):
        records  = [(kind, {"fixture_kind": kind}) for kind in sorted(export.SUPPORTED_KINDS)]
        database = make_database(make_session(1, records))
        document = catalog.build_catalog(database, SHA256)
        rows     = document["transactions"] + document["observations"]
        expected = database["sessions"][0]["observations"]
        self.assertEqual({row["type"] for row in document["transactions"]}, ACTIONS)
        self.assertEqual({row["type"] for row in document["observations"]}, export.SUPPORTED_KINDS - ACTIONS)
        self.assertCountEqual([row["id"] for row in rows], [row["observation_id"] for row in expected])
        self.assertEqual(document["summary"]["kindCounts"], {kind: 1 for kind in export.SUPPORTED_KINDS})
        self.assertEqual(document["summary"]["transactionCounts"], {kind: 1 for kind in ACTIONS})
        self.assertEqual(document["summary"]["observationCount"], len(expected))
        for bucket in (document["transactions"], document["observations"]):
            self.assertEqual([row["sequence"] for row in bucket], sorted(row["sequence"] for row in bucket))
        self.assert_references(document)

    def test_original_payload_and_session_metadata_are_retained_without_mutation(self):
        session  = make_session(1, [
            ("spell.metadata", {"spell_id": 123, "name": "Éclair 森", "iconID": 42,
                                "current_state": {"power_costs": [], "cooldown": {"duration": 0}},
                                "is_passive": False, "description": "<script>literal text</script>"}),
            ("spell.succeeded", {"spell_id": 123}),
        ])
        first    = session["observations"][0]
        second   = session["observations"][1]
        first["missing_fields"] = {"data.cast_time": "not_ready"}
        second["related_observation_ids"] = [first["observation_id"]]
        database = make_database(session)
        before   = copy.deepcopy(database)
        document = catalog.build_catalog(database, SHA256)
        rows     = {row["id"]: row for row in document["observations"] + document["transactions"]}
        self.assertEqual(database, before)
        self.assertEqual(document["sessions"][0]["data"], session["session"])
        self.assertEqual(document["sessions"][0]["diagnostics"], session["diagnostics"])
        for source in session["observations"]:
            row = rows[source["observation_id"]]
            self.assertEqual(row["data"], source["data"])
            self.assertEqual(row["capture"], source["capture"])
            self.assertEqual(row["evidence"], source["evidence"])
            self.assertEqual(row["missingFields"], source["missing_fields"])
            self.assertEqual(row["relatedIds"], source["related_observation_ids"])
            self.assertEqual(row["elapsedSeconds"], source["elapsed_s"])
        self.assert_references(document)

    def test_repeated_builds_are_deterministic_and_ignore_dictionary_order(self):
        database = make_database(make_session(1, [
            ("quest.accepted", {"quest_id": 200, "quest_run_id": "synthetic-run"}),
            ("item.metadata", {"item_id": 100, "name": "Synthetic item", "link": LINK_A}),
        ]))
        reordered = json.loads(json.dumps(database, sort_keys=True))
        first     = catalog.build_catalog(database, SHA256)
        self.assertEqual(first, catalog.build_catalog(database, SHA256))
        self.assertEqual(first, catalog.build_catalog(reordered, SHA256))

    def test_entities_merge_only_within_product_build_and_locale_context(self):
        records  = [("item.metadata", {"item_id": 100, "name": "Synthetic item"})]
        sessions = [make_session(1, records), make_session(2, records),
                    make_session(3, records, build="70000"), make_session(4, records, locale="frFR"),
                    make_session(5, records)]
        sessions[4]["session"]["product"] = "OTHER_SYNTHETIC_PRODUCT"
        document = catalog.build_catalog(make_database(*sessions), SHA256)
        items    = document["catalog"]["items"]
        self.assertEqual(len(document["contexts"]), 4)
        self.assertEqual(len(items), 4)
        self.assertEqual({item["nativeId"] for item in items}, {100})
        self.assertEqual(sorted(len(item["sourceIds"]) for item in items), [1, 1, 1, 2])
        self.assertEqual(len({item["key"] for item in items}), 4)
        self.assert_references(document)

    def test_repeated_rewards_chat_and_inventory_remain_separate(self):
        reward   = {"quest_id": 200, "quest_run_id": "synthetic-run", "item_id": 100,
                    "link": LINK_A, "quantity": 2, "recipient": "local_player", "source_status": "quest_event"}
        database = make_database(make_session(1, [
            ("quest.reward_received", reward), ("quest.reward_received", reward),
            ("item.received", {"item_id": 100, "link": LINK_A, "quantity": 2, "source_status": "unknown"}),
            ("inventory.delta", {"item_id": 100, "before_quantity": 0, "after_quantity": 2,
                                 "delta": 2, "scope": "carried_bags_0_to_4", "source_status": "unknown"}),
        ]))
        document = catalog.build_catalog(database, SHA256)
        rows     = document["transactions"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(Counter(row["type"] for row in rows),
                         {"quest.reward_received": 2, "item.received": 1, "inventory.delta": 1})
        for row in rows[2:]:
            self.assertNotIn("quest_id", row["data"])
            self.assertEqual(row["data"]["source_status"], "unknown")
        self.assertFalse(any("acquisition" in key.lower() for key in document["summary"]))
        self.assert_references(document)

    def test_late_metadata_enriches_items_and_retains_exact_link_variants(self):
        session = make_session(1, [
            ("item.received", {"item_id": 100, "link": LINK_A, "quantity": 1}),
            ("item.received", {"item_id": 100, "link": LINK_B, "quantity": 1}),
            ("item.metadata", {"item_id": 100, "link": LINK_A, "name": "Synthetic sword", "icon_id": 456}),
            ("item.metadata", {"item_id": 100, "link": LINK_B, "name": "Synthetic sword", "item_level": 8}),
        ])
        session["observations"][2]["related_observation_ids"] = [session["observations"][0]["observation_id"]]
        session["observations"][3]["related_observation_ids"] = [session["observations"][1]["observation_id"]]
        document = catalog.build_catalog(make_database(session), SHA256)
        item     = document["catalog"]["items"][0]
        self.assertEqual(len(document["catalog"]["items"]), 1)
        self.assertEqual(item["display"]["name"], "Synthetic sword")
        self.assertEqual({variant["link"] for variant in item["variants"]}, {LINK_A, LINK_B})
        self.assertEqual(len({variant["key"] for variant in item["variants"]}), 2)
        self.assertEqual(set(item["sourceIds"]), {row["observation_id"] for row in session["observations"]})
        self.assertTrue(any(fact["data"].get("icon_id") == 456 for fact in item["facts"]))
        self.assertTrue(any(fact["data"].get("item_level") == 8 for fact in item["facts"]))
        self.assertNotIn("stats", item)
        self.assertNotIn("iconURL", item)
        self.assert_references(document)

    def test_loot_candidates_link_items_and_npcs_without_claiming_drop_sources(self):
        candidate = {"creature_id": 300, "name": "Synthetic boar", "unit_token": "target",
                     "guid": "Creature-0-1-2-3-300-00000001", "entity_kind": "Creature", "reaction": 2}
        visible   = {"item_id": 100, "link": LINK_A, "quantity": 2, "loot_session_id": "loot-1",
                     "slot": 1, "revision": 1, "source_status": "unknown", "sources": [],
                     "source_candidates": [candidate]}
        receipt   = {"item_id": 100, "link": LINK_A, "quantity": 1, "loot_session_id": "loot-1",
                     "loot_slot": 1, "loot_revision": 1, "loot_match_status": "candidate",
                     "source_status": "unknown", "source_candidates": [candidate]}
        session   = make_session(1, [
            ("loot.opened", {"loot_session_id": "loot-1", "target_candidate": candidate}),
            ("loot.visible", visible), ("item.received", receipt),
            ("item.metadata", {"item_id": 100, "name": "Synthetic sword", "link": LINK_A}),
        ])
        records = session["observations"]
        records[1]["related_observation_ids"] = [records[0]["observation_id"]]
        records[2]["related_observation_ids"] = [records[1]["observation_id"]]
        document = catalog.build_catalog(make_database(session), SHA256)
        item     = document["catalog"]["items"][0]
        npc      = document["catalog"]["npcs"][0]
        rows     = {row["type"]: row for row in document["observations"] + document["transactions"]}
        for entity in (item, npc):
            facts = [fact for fact in entity["facts"] if fact["type"] == "loot.provenance"]
            self.assertEqual(len(facts), 2)
            self.assertCountEqual([fact["data"] for fact in facts], [visible, receipt])
            self.assertTrue(all(fact["data"]["source_status"] == "unknown" for fact in facts))
        for kind in ("loot.visible", "item.received"):
            refs = [reference for reference in rows[kind]["entities"] if reference["key"] == npc["key"]]
            self.assertEqual(refs, [{"key": npc["key"], "role": "loot_candidate",
                                     "path": "data.source_candidates[0].creature_id"}])
        self.assertEqual(rows["loot.visible"]["relatedIds"], [rows["loot.opened"]["id"]])
        self.assertEqual(rows["item.received"]["relatedIds"], [rows["loot.visible"]["id"]])
        self.assertFalse(any(reference["key"] == npc["key"] for reference in rows["item.metadata"]["entities"]))
        self.assertNotIn("source_candidates", item["details"])
        self.assert_references(document)

    def test_plural_api_loot_sources_preserve_quantities_and_mapping_status(self):
        sources = [
            {"source_guid": "Creature-0-1-2-3-300-00000001", "creature_id": 300,
             "entity_kind": "Creature", "quantity": 1},
            {"source_guid": "Vehicle-0-1-2-3-301-00000002", "creature_id": 301,
             "entity_kind": "Vehicle", "quantity": 2},
            {"source_guid": "GameObject-0-1-2-3-400-00000003", "entity_kind": "GameObject", "quantity": 1},
        ]
        for status, matches in (("mapped", True), ("mapped", False), ("partial", False), ("unverified", True)):
            with self.subTest(status=status, matches=matches):
                data     = {"item_id": 100, "link": LINK_A, "quantity": 4, "loot_session_id": "loot-1",
                            "slot": 1, "revision": 1, "sources": sources, "source_status": status,
                            "source_quantity_matches": matches, "source_candidates": [],
                            "source_mapping_status": "validated" if status == "mapped" else "unverified"}
                document = catalog.build_catalog(make_database(make_session(1, [("loot.visible", data)])), SHA256)
                row      = document["observations"][0]
                item     = document["catalog"]["items"][0]
                npcs     = document["catalog"]["npcs"]
                self.assertEqual({npc["nativeId"] for npc in npcs}, {300, 301})
                role = "loot_source" if status == "mapped" and matches else "loot_candidate"
                objects = document["catalog"]["objects"]
                self.assertEqual([entry["nativeId"] for entry in objects], [400])
                self.assertEqual([reference["role"] for reference in row["entities"]], ["item", role, role, role])
                for entity in [item, *npcs, *objects]:
                    facts = [fact for fact in entity["facts"] if fact["type"] == "loot.provenance"]
                    self.assertEqual(len(facts), 1)
                    self.assertEqual(facts[0]["data"], data)
                self.assert_references(document)

    def test_unknown_and_legacy_loot_do_not_gain_inferred_entity_sources(self):
        session = make_session(1, [
            ("loot.opened", {"loot_session_id": "loot-1", "target_candidate": {"creature_id": 300}}),
            ("loot.visible", {"item_id": 100, "loot_session_id": "loot-1", "source_status": "unknown", "sources": []}),
            ("item.received", {"item_id": 100, "source_status": "unknown"}),
        ])
        document = catalog.build_catalog(make_database(session), SHA256)
        npc      = document["catalog"]["npcs"][0]
        rows     = document["observations"] + document["transactions"]
        for row in rows:
            if row["type"] in ("loot.visible", "item.received"):
                self.assertFalse(any(reference["key"] == npc["key"] for reference in row["entities"]))
                self.assertNotIn("source_candidates", row["data"])
        self.assertFalse(any(fact["type"] == "loot.provenance" for fact in npc["facts"]))
        self.assert_references(document)

    def test_conflicting_metadata_facts_retain_each_observed_value(self):
        database = make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "First observed name", "item_level": 5}),
            ("item.metadata", {"item_id": 100, "name": "Later observed name", "item_level": 9}),
        ]))
        document = catalog.build_catalog(database, SHA256)
        item     = document["catalog"]["items"][0]
        levels   = {fact["data"]["item_level"] for fact in item["facts"] if "item_level" in fact["data"]}
        self.assertEqual(levels, {5, 9})
        self.assertIn(item["display"]["name"], {"First observed name", "Later observed name"})
        self.assert_references(document)

    def test_numeric_item_stats_and_tooltips_preserve_evidence_and_missing_values(self):
        detailed = {"item_id": 100, "link": LINK_A, "name": "Synthetic armor", "stats_status": "available",
                    "stats": {"RESISTANCE0_NAME": 35, "ITEM_MOD_STAMINA_SHORT": 4},
                    "stat_labels": {"RESISTANCE0_NAME": "Armor", "ITEM_MOD_STAMINA_SHORT": "Stamina"},
                    "tooltip_lines": [{"leftText": "35 Armor"}, {"leftText": "+4 Stamina"}]}
        document = catalog.build_catalog(make_database(make_session(1, [
            ("item.metadata", detailed),
            ("item.metadata", {"item_id": 101, "name": "Older metadata without stats"}),
        ])), SHA256)
        items = {item["nativeId"]: item for item in document["catalog"]["items"]}
        self.assertEqual(items[100]["display"]["stats"], detailed["stats"])
        self.assertTrue(any(fact["data"].get("stats") == detailed["stats"] for fact in items[100]["facts"]))
        self.assertEqual(items[100]["display"]["tooltipLines"], detailed["tooltip_lines"])
        self.assertNotIn("stats", items[101]["display"])
        self.assertTrue(all("stats" not in fact["data"] for fact in items[101]["facts"]))
        self.assert_references(document)

    def test_spell_details_preserve_cast_time_typed_costs_damage_text_and_provenance(self):
        detailed = {
            "spell_id": 123, "name": "Synthetic strike", "iconID": 42, "castTime": 0,
            "minRange": 0, "maxRange": 30, "description": "Deals 205 to 210 damage.",
            "subtext": "Rank 2", "is_passive": False, "values_context": "character_at_observation",
            "resolved_spell_id": 124, "base_spell_id": 125, "override_spell_id": 126,
            "base_cooldown_ms": 0, "base_cooldown_status": "available",
            "current_state": {"power_costs": [
                {"type": 0, "name": "MANA", "cost": 12.5, "costPercent": 2.25, "hasRequiredAura": False},
                {"type": 3, "name": "ENERGY", "cost": 40, "minCost": 0, "costPerSec": 1.5},
            ], "cooldown": {"duration": 0, "isEnabled": True}},
            "tooltip_lines": [{"index": 1, "left_text": "205 to 210 damage", "right_text": "Instant", "type": 0}],
            "tooltip_status": "available", "tooltip_context": "character_at_observation",
            "tooltip_method": "C_TooltipInfo.GetSpellByID",
        }
        database = make_database(make_session(1, [
            ("spell.metadata", detailed),
            ("spell.metadata", {"spell_id": 123, "name": "Later partial name", "description": "Different observed text"}),
        ]))
        document = catalog.build_catalog(database, SHA256)
        spells   = {spell["nativeId"]: spell for spell in document["catalog"]["spells"]}
        spell    = spells[123]
        display  = spell["display"]
        self.assertEqual(spell["details"], detailed)
        self.assertEqual(spell["displaySourceId"], database["sessions"][0]["observations"][0]["observation_id"])
        self.assertEqual(display["castTimeMs"], 0)
        self.assertEqual((display["minRange"], display["maxRange"]), (0, 30))
        self.assertEqual(display["currentState"], detailed["current_state"])
        self.assertEqual(display["description"], detailed["description"])
        self.assertEqual(display["tooltipLines"], detailed["tooltip_lines"])
        self.assertEqual(display["tooltipContext"], detailed["tooltip_context"])
        self.assertEqual(display["tooltipMethod"], detailed["tooltip_method"])
        self.assertEqual(display["valuesContext"], detailed["values_context"])
        self.assertEqual(display["baseCooldownMs"], 0)
        self.assertFalse(display["isPassive"])
        for field in ("resolvedSpellId", "baseSpellId", "overrideSpellId"):
            self.assertIn(display[field], spells)
        for field in ("manaCost", "damage", "minimumDamage", "maximumDamage"):
            self.assertNotIn(field, display)
        self.assertTrue(any(fact["data"].get("tooltip_lines") == detailed["tooltip_lines"] for fact in spell["facts"]))
        self.assertTrue(any(fact["data"].get("description") == "Different observed text" for fact in spell["facts"]))
        self.assertEqual(spells[124]["details"], {})
        self.assert_references(document)
        spell["details"]["current_state"]["power_costs"][0]["cost"] = -1
        self.assertEqual(database["sessions"][0]["observations"][0]["data"], detailed)
        self.assertEqual(display["currentState"]["power_costs"][0]["cost"], 12.5)

    def test_entity_details_come_from_one_observed_snapshot(self):
        records = [
            ("quest.metadata", {"quest_id": 200, "title": "Synthetic quest", "description": "Quest story", "load_success": True}),
            ("unit.sighting", {"creature_id": 300, "name": "Synthetic creature", "level": 12,
                               "entity_position": {"subject": "target", "map_id": 1, "x": 20, "y": 30}}),
            ("recipe.metadata", {"recipe_id": 400, "name": "Synthetic recipe", "quantity_min": 1, "quantity_max": 2}),
            ("talent.metadata", {"entity_type": "node", "entity_id": 500, "config_id": 7,
                                 "info": {"ID": 500, "currentRank": 0, "maxRanks": 3, "entryIDs": []}}),
            ("profession.snapshot", {"professionID": 600, "professionName": "Synthetic profession", "skillLevel": 5}),
        ]
        database = make_database(make_session(1, records))
        document = catalog.build_catalog(database, SHA256)
        expected = {"quests": 200, "npcs": 300, "recipes": 400, "talents": "node:500", "professions": 600}
        for index, (bucket, native_id) in enumerate(expected.items()):
            entity = next(entity for entity in document["catalog"][bucket] if entity["nativeId"] == native_id)
            self.assertEqual(entity["details"], records[index][1])
            self.assertEqual(entity["displaySourceId"], database["sessions"][0]["observations"][index]["observation_id"])
        self.assert_references(document)

    def test_invalid_cast_time_sentinels_remain_evidence_without_becoming_display_values(self):
        for value in (-1000000, True, "instant"):
            with self.subTest(cast_time=value):
                data     = {"spell_id": 123, "name": "Synthetic spell", "castTime": value}
                document = catalog.build_catalog(make_database(make_session(1, [("spell.metadata", data)])), SHA256)
                spell    = document["catalog"]["spells"][0]
                self.assertNotIn("castTimeMs", spell["display"])
                self.assertEqual(spell["display"]["castTimeStatus"], "invalid_result")
                self.assertEqual(spell["details"]["castTime"], value)
                self.assertTrue(any(fact["data"].get("castTime") == value for fact in spell["facts"]))
                self.assert_references(document)

        data     = {"spell_id": 123, "name": "Synthetic spell", "reported_cast_time_ms": -1000000,
                    "cast_time_status": "invalid_result"}
        document = catalog.build_catalog(make_database(make_session(1, [("spell.metadata", data)])), SHA256)
        spell    = document["catalog"]["spells"][0]
        self.assertNotIn("castTimeMs", spell["display"])
        self.assertEqual(spell["display"]["castTimeStatus"], "invalid_result")
        self.assertEqual(spell["display"]["reportedCastTimeMs"], -1000000)
        self.assertEqual(spell["details"], data)
        self.assert_references(document)

    def test_complete_empty_item_stats_outrank_partial_or_unavailable_metadata(self):
        complete = {"item_id": 100, "name": "Synthetic ordinary item", "link": LINK_A,
                    "stats": {}, "stats_status": "available", "tooltip_lines": [], "tooltip_status": "available"}
        document = catalog.build_catalog(make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Partial stats", "link": LINK_B,
                               "stats": {"RESISTANCE0_NAME": 10}, "stats_status": "partial", "icon_id": 42}),
            ("item.metadata", complete),
            ("item.metadata", {"item_id": 100, "name": "Later unavailable stats", "stats_status": "unavailable"}),
        ])), SHA256)
        item = document["catalog"]["items"][0]
        self.assertEqual(item["details"], complete)
        self.assertEqual(item["display"]["stats"], {})
        self.assertEqual(item["display"]["statsStatus"], "available")
        self.assertEqual(item["display"]["tooltipLines"], [])
        self.assertNotIn("iconId", item["display"])
        self.assertEqual({variant["link"] for variant in item["variants"]}, {LINK_A, LINK_B})
        self.assertTrue(any(fact["data"].get("stats") == {"RESISTANCE0_NAME": 10} for fact in item["facts"]))
        self.assert_references(document)

    def test_player_location_is_not_inferred_as_npc_position(self):
        session  = make_session(1, [("unit.sighting", {"creature_id": 300, "name": "Synthetic boar"})])
        location = {"status": "available", "subject": "player", "coordinate_system": "ui_map_normalized",
                    "ui_map_id": 1411, "x": 0.25, "y": 0.75}
        session["observations"][0]["location"] = location
        document = catalog.build_catalog(make_database(session), SHA256)
        row      = document["observations"][0]
        npc      = document["catalog"]["npcs"][0]
        self.assertEqual(row["location"]["subject"], "player")
        self.assertEqual((row["location"]["mapX"], row["location"]["mapY"]), (25, 75))
        self.assertEqual({entry["nativeId"] for entry in document["catalog"]["maps"]}, {"ui_map:1411"})
        for field in ("location", "entity_position", "spawn", "spawns", "mapX", "mapY"):
            self.assertNotIn(field, npc)
            self.assertTrue(all(field not in fact["data"] for fact in npc["facts"]))
        self.assert_references(document)

    def test_quest_reward_choices_and_merchant_offers_remain_observations(self):
        dialogue = {"quest_id": 200, "title": "Synthetic quest", "phase": "QUEST_COMPLETE",
                    "npc": {"creature_id": 300, "name": "Synthetic giver"},
                    "rewards": [{"item_id": 100, "name": "Guaranteed", "quantity": 1}],
                    "choices": [{"item_id": 101, "name": "Choice A", "quantity": 1},
                                {"item_id": 102, "name": "Choice B", "quantity": 1}],
                    "required_items": [{"item_id": 103, "name": "Required", "quantity": 3}]}
        merchant = {"item_id": 104, "name": "For sale", "price": 50, "stackCount": 1,
                    "npc": {"creature_id": 301, "name": "Synthetic vendor"},
                    "costs": [{"item_id": 105, "quantity": 2}]}
        document = catalog.build_catalog(make_database(make_session(1, [
            ("quest.dialogue", dialogue), ("merchant.offer", merchant),
        ])), SHA256)
        self.assertEqual(document["transactions"], [])
        self.assertEqual({item["nativeId"] for item in document["catalog"]["items"]}, set(range(100, 106)))
        self.assertEqual(document["observations"][0]["data"], dialogue)
        self.assertEqual(document["observations"][1]["data"], merchant)
        self.assert_references(document)

    def test_talent_ids_keep_namespaces_and_link_to_spells(self):
        document = catalog.build_catalog(make_database(make_session(1, [
            ("talent.metadata", {"entity_type": "node", "entity_id": 123, "config_id": 7,
                                 "info": {"ID": 123, "entryIDs": [123], "currentRank": 1}}),
            ("talent.metadata", {"entity_type": "entry", "entity_id": 123, "config_id": 7,
                                 "info": {"definitionID": 456, "maxRanks": 2}}),
            ("talent.metadata", {"entity_type": "definition", "entity_id": 456, "config_id": 7,
                                 "info": {"spellID": 123, "overrideName": "Synthetic talent"}}),
            ("talent.rank", {"entry_id": 123, "rank": 2, "description": "Synthetic rank text"}),
        ])), SHA256)
        talents = {entry["nativeId"]: entry for entry in document["catalog"]["talents"]}
        self.assertTrue({"node:123", "entry:123", "definition:456"} <= talents.keys())
        self.assertNotEqual(talents["node:123"]["key"], talents["entry:123"]["key"])
        self.assertIn(123, {entry["nativeId"] for entry in document["catalog"]["spells"]})
        self.assert_references(document)

    def test_recipe_profession_and_reagent_ids_preserve_native_field_shapes(self):
        recipe   = {"recipe_id": 400, "recipeID": 400, "name": "Synthetic recipe", "output_item_id": 100,
                    "reagent_slots": [{"quantityRequired": 2, "required": True, "reagentType": 1,
                                       "reagents": [{"itemID": 101}, {"currencyID": 102}]}]}
        document = catalog.build_catalog(make_database(make_session(1, [
            ("recipe.learned", {"recipe_id": 400, "base_recipe_id": 401}),
            ("recipe.metadata", recipe),
            ("profession.snapshot", {"professionID": 500, "professionName": "Synthetic smithing", "skillLevel": 2}),
        ])), SHA256)
        self.assertIn(400, {entry["nativeId"] for entry in document["catalog"]["recipes"]})
        self.assertTrue({100, 101} <= {entry["nativeId"] for entry in document["catalog"]["items"]})
        self.assertIn(102, {entry["nativeId"] for entry in document["catalog"]["currencies"]})
        self.assertIn(500, {entry["nativeId"] for entry in document["catalog"]["professions"]})
        self.assertEqual(next(row["data"] for row in document["observations"] if row["type"] == "recipe.metadata"), recipe)
        self.assert_references(document)

    def test_time_and_coordinates_are_derived_only_when_present(self):
        session = make_session(1, [("location.sample", {}), ("coverage.gap", {"reason": "synthetic"})])
        session["observations"][0]["observed_at_server_s"] = 1790000000
        session["observations"][0]["location"] = {
            "status": "available", "subject": "player", "coordinate_system": "ui_map_normalized",
            "ui_map_id": 1411, "x": 0, "y": 1,
        }
        session["observations"][1]["location"] = {"status": "unavailable", "reason": "not_ready"}
        document = catalog.build_catalog(make_database(session), SHA256)
        first    = document["observations"][0]
        absent   = document["observations"][1]
        self.assertEqual(first["observedAtUnix"], 1790000000)
        self.assertEqual(datetime.fromisoformat(first["observedAt"].replace("Z", "+00:00")),
                         datetime.fromtimestamp(1790000000, timezone.utc))
        self.assertEqual((first["location"]["mapX"], first["location"]["mapY"]), (0, 100))
        self.assertNotIn("observedAt", absent)
        self.assertNotIn("observedAtUnix", absent)
        self.assertNotIn("mapX", absent["location"])
        self.assertNotIn("mapY", absent["location"])
        self.assert_references(document)

    def test_validator_rejects_dangling_references_and_inconsistent_counts(self):
        document = catalog.build_catalog(make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "Synthetic item"}),
        ])), SHA256)
        mutations = []
        broken    = copy.deepcopy(document)
        broken["observations"][0]["relatedIds"] = ["missing-observation"]
        mutations.append(broken)
        broken = copy.deepcopy(document)
        broken["catalog"]["items"][0]["sourceIds"] = ["missing-observation"]
        mutations.append(broken)
        broken = copy.deepcopy(document)
        broken["observations"][0]["entities"][0]["key"] = "missing-entity"
        mutations.append(broken)
        broken = copy.deepcopy(document)
        broken["summary"]["observationCount"] += 1
        mutations.append(broken)
        broken = copy.deepcopy(document)
        broken["transactions"].append(copy.deepcopy(broken["observations"][0]))
        mutations.append(broken)
        for index, broken in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                catalog.validate_catalog(broken)

    def test_cli_outputs_valid_deterministic_json_and_never_overwrites(self):
        database = make_database(make_session(1, [
            ("item.metadata", {"item_id": 100, "link": LINK_A, "name": "Éclair 森"}),
        ]))
        raw = source_bytes(database)
        with tempfile.TemporaryDirectory() as directory:
            root    = Path(directory)
            source  = root / "ForeverTome.lua"
            output  = root / "catalog.json"
            repeat  = root / "repeat.json"
            compact = root / "compact.json"
            source.write_bytes(raw)
            for destination, options in ((output, []), (repeat, []), (compact, ["--compact"])):
                process = subprocess.run([sys.executable, str(MODULE_PATH), str(source), "--output", str(destination), *options],
                                         capture_output=True, text=True, timeout=30)
                self.assertEqual(process.returncode, 0, process.stderr)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(document["source"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(output.read_bytes(), repeat.read_bytes())
            self.assertEqual(json.loads(compact.read_text(encoding="utf-8")), document)
            self.assertLess(compact.stat().st_size, output.stat().st_size)
            before = output.read_bytes()
            for destination in (source, output):
                process = subprocess.run([sys.executable, str(MODULE_PATH), str(source), "--output", str(destination)],
                                         capture_output=True, text=True, timeout=30)
                self.assertNotEqual(process.returncode, 0)
                self.assertNotIn("Traceback", process.stderr)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(output.read_bytes(), before)
            self.assert_references(document)

    def test_cli_rejects_lua_code_and_invalid_data_without_creating_output(self):
        valid = source_bytes(make_database(make_session(1, [("item.received", {"item_id": 100})])))
        cases = [valid + b"\nos.execute('exit 0')\n", valid[:-10],
                 valid.replace(b'"item.received"', b'"future.kind"'), b"return {}"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, raw in enumerate(cases):
                with self.subTest(case=index):
                    source = root / f"invalid-{index}.lua"
                    output = root / f"invalid-{index}.json"
                    source.write_bytes(raw)
                    process = subprocess.run([sys.executable, str(MODULE_PATH), str(source), "--output", str(output)],
                                             capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertFalse(output.exists())
                    self.assertEqual(source.read_bytes(), raw)
                    self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
