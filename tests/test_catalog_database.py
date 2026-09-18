import copy
import json
import unittest
from pathlib import Path

from test_catalog import SHA256, catalog, make_database, make_session
from tools.catalog_database import database_projection


def project(*sessions):
    document = catalog.build_catalog(make_database(*sessions), SHA256)
    result   = database_projection(document["contexts"], document["sessions"],
                                   document["transactions"] + document["observations"])
    return document, result


class DatabaseProjectionTests(unittest.TestCase):
    def test_one_creature_identity_preserves_services_and_contextual_monster_classification(self):
        session = make_session(1, [
            ("unit.sighting", {"creature_id": 300, "name": "Variable creature", "reaction": 3}),
            ("unit.sighting", {"creature_id": 300, "reaction": 5}),
            ("merchant.offer", {"npc": {"creature_id": 300}, "item_id": 100, "price": 25, "numAvailable": -1}),
        ])
        document, result = project(session)
        creature         = result["catalog"]["creatures"][0]
        self.assertNotIn("npcs", result["catalog"])
        self.assertNotIn("monsters", result["catalog"])
        self.assertEqual(creature["key"], document["catalog"]["npcs"][0]["key"])
        self.assertEqual(creature["contentKey"], "content:WF:creature:300")
        self.assertEqual(creature["sourceCount"], 3)
        self.assertEqual(creature["classification"], {
            "scope": "observed_context", "reactionValues": [3, 5], "monsterObserved": True,
        })
        self.assertEqual([service["type"] for service in creature["services"]], ["sells"])
        edge = result["relationships"][0]
        self.assertEqual(edge["predicate"], "sells")
        self.assertEqual(edge["attributes"]["price"], 25)
        self.assertEqual(edge["sourceCount"], 1)

    def test_content_families_keep_build_locale_versions_and_session_scope_configs(self):
        rows = [("item.metadata", {"item_id": 100, "name": "Observed"}),
                ("talent.metadata", {"entity_type": "config", "entity_id": 4, "config_id": 4, "info": {"ID": 4}})]
        document, result = project(make_session(1, rows), make_session(2, rows),
                                   make_session(3, rows, locale="frFR"))
        items            = result["catalog"]["items"]
        configs          = result["catalog"]["talents"]
        self.assertEqual(len(items), 2)
        self.assertEqual(len({entry["key"] for entry in items}), 2)
        self.assertEqual(len({entry["contentKey"] for entry in items}), 1)
        self.assertEqual(len(configs), 3)
        self.assertEqual(len({entry["contentKey"] for entry in configs}), 3)
        self.assertTrue(all(entry["identityScope"] == "session" for entry in configs))

    def test_game_objects_require_valid_guid_and_do_not_become_creatures(self):
        rows = [("loot.visible", {"item_id": 100, "source_candidates": [
            {"source_guid": "GameObject-0-1-2-3-400-00000001", "entity_kind": "GameObject", "observed_label": "Observed chest label"},
            {"source_guid": "Player-0-400", "entity_kind": "GameObject"},
            {"source_guid": "GameObject-0-1-2-3-0-AAAA", "entity_kind": "GameObject"},
            {"source_guid": "GameObject-0-1-2-3-999999999999-AAAA", "entity_kind": "GameObject"},
            {"source_guid": "GameObject-0-1-2-3-401-nothex", "entity_kind": "GameObject"},
        ]})]
        document, result = project(make_session(1, rows))
        self.assertEqual(result["catalog"]["creatures"], [])
        self.assertEqual([entry["nativeId"] for entry in result["catalog"]["objects"]], [400])
        self.assertEqual(result["catalog"]["objects"][0]["display"]["observedLabel"], "Observed chest label")
        self.assertNotIn("name", result["catalog"]["objects"][0]["display"])
        self.assertEqual([edge["predicate"] for edge in result["relationships"]], ["loot_source_candidate"])

    def test_quest_offers_receipts_and_starter_candidates_keep_separate_evidence(self):
        rows = [
            ("quest.dialogue", {"quest_id": 200, "phase": "QUEST_DETAIL", "npc": {"creature_id": 300},
                                "rewards": [{"item_id": 100, "quantity": 2}], "choices": [{"item_id": 101}],
                                "quest_start_item_id": 102}),
            ("quest.reward_received", {"quest_id": 200, "item_id": 100, "quantity": 2, "quest_run_id": "run-1"}),
        ]
        document, result = project(make_session(1, rows))
        edges            = {edge["predicate"]: edge for edge in result["relationships"]}
        self.assertEqual(set(edges), {"offers_reward", "offers_reward_choice", "started_by_item", "starts_quest", "reward_received"})
        self.assertEqual(edges["starts_quest"]["status"], "candidate")
        self.assertNotEqual(edges["offers_reward"]["sourceIds"], edges["reward_received"]["sourceIds"])
        self.assertEqual(edges["reward_received"]["attributes"]["quest_run_id"], "run-1")

    def test_lua_array_missing_paths_attach_to_the_matching_object(self):
        session = make_session(1, [("loot.visible", {"item_id": 100, "sources": [
            {"source_guid": "GameObject-0-1-2-3-400-00000001", "tooltip_status": "unsupported"},
            {"source_guid": "GameObject-0-1-2-3-401-00000002", "observed_label": "Readable label"},
        ]})])
        session["observations"][0]["missing_fields"] = {
            "data.sources.1.tooltip_lines": "unsupported",
            "data.sources.1.observed_label": "not_ready_or_restricted",
            "data.sources[1].entity_position": "not_observed",
        }
        document, result = project(session)
        objects          = {entry["nativeId"]: entry for entry in result["catalog"]["objects"]}
        first            = objects[400]["fieldCoverage"]
        second           = objects[401]["fieldCoverage"]
        self.assertEqual(first["tooltip_lines"]["statuses"], ["unavailable"])
        self.assertEqual(first["observed_label"]["statuses"], ["unavailable"])
        self.assertEqual(first["tooltip_lines"]["missing"][0]["reason"], "unsupported")
        self.assertEqual(first["observed_label"]["missing"][0]["reason"], "not_ready_or_restricted")
        self.assertEqual(second["observed_label"]["statuses"], ["captured"])
        self.assertEqual(second["observed_label"]["missing"], [])
        self.assertEqual(second["entity_position"]["missing"][0]["reason"], "not_observed")

    def test_recipe_talent_and_item_relationships_use_explicit_identifiers(self):
        rows = [
            ("recipe.metadata", {"recipe_id": 600, "output_item_id": 100, "profession_id": 900,
                                 "quantity_min": 1, "quantity_max": 2, "quality_item_ids": [103],
                                 "reagent_slots": [{"quantityRequired": 4, "reagents": [{"itemID": 101}, {"currencyID": 20}]}]}),
            ("talent.metadata", {"entity_type": "node", "entity_id": 10, "tree_id": 9, "config_id": 1,
                                 "info": {"entryIDs": [11], "conditionIDs": [12], "visibleEdges": [{"targetNode": 13, "type": 1}]}}),
            ("talent.metadata", {"entity_type": "definition", "entity_id": 14, "info": {"spellID": 500}}),
            ("item.metadata", {"item_id": 100, "name": "Item name", "item_spell_id": 501,
                               "item_spell_name": "Item effect", "gems": [{"item_id": 102}]}),
            ("spell.metadata", {"spell_id": 500, "override_spell_id": 502}),
        ]
        document, result = project(make_session(1, rows))
        edges            = result["relationships"]
        predicates       = {edge["predicate"] for edge in edges}
        self.assertTrue({"produces", "produces_quality_variant", "reagent_option", "belongs_to_profession",
                         "contains", "requires", "visible_edge_to", "grants_spell", "item_spell", "socketed_gem", "overridden_by"} <= predicates)
        reagents = [edge for edge in edges if edge["predicate"] == "reagent_option"]
        self.assertEqual(len(reagents), 2)
        self.assertTrue(all(edge["attributes"]["quantityRequired"] == 4 for edge in reagents))
        effect = next(entry for entry in result["catalog"]["spells"] if entry["nativeId"] == 501)
        self.assertEqual(effect["display"]["name"], "Item effect")
        entities = {entity["key"] for bucket in result["catalog"].values() for entity in bucket}
        sources  = {row["id"] for row in document["transactions"] + document["observations"]}
        for edge in edges:
            self.assertIn(edge["subject"], entities)
            self.assertIn(edge["object"], entities)
            self.assertTrue(set(edge["sourceIds"]) <= sources)
            self.assertEqual({entry["sourceId"] for entry in edge["evidence"]}, set(edge["sourceIds"]))

    def test_npc_spell_and_services_have_explicit_evidence(self):
        document, result = project(make_session(1, [
            ("spell.succeeded", {"actor": "npc", "npc": {"creature_id": 300}, "spell_id": 500}),
            ("interaction.snapshot", {"npc": {"creature_id": 300}, "service": "trainer", "scope": "opened_npc_service"}),
        ]))
        creature         = result["catalog"]["creatures"][0]
        self.assertEqual([edge["predicate"] for edge in result["relationships"]], ["casts_spell"])
        self.assertEqual(creature["services"][0]["type"], "trainer")
        self.assertEqual(len(creature["services"][0]["sourceIds"]), 1)

    def test_field_values_missing_reasons_and_positions_are_traceable(self):
        session = make_session(1, [
            ("item.metadata", {"item_id": 100, "name": "First name", "stats": {}}),
            ("item.metadata", {"item_id": 100, "name": "Second name", "stats": {"POWER": 3}}),
            ("unit.sighting", {"creature_id": 300, "entity_position": {"map_id": 1, "x": 5, "y": 6}}),
        ])
        session["observations"][0]["missing_fields"] = {"data.tooltip_lines": "not_ready_or_restricted"}
        document, result = project(session)
        item             = result["catalog"]["items"][0]
        fields           = item["fieldCoverage"]
        self.assertCountEqual([entry["value"] for entry in fields["name"]["candidates"]], ["First name", "Second name"])
        self.assertIn("name", item["multipleValueFields"])
        self.assertEqual(fields["tooltip_lines"]["statuses"], ["unavailable"])
        self.assertEqual(fields["tooltip_lines"]["missing"][0]["reason"], "not_ready_or_restricted")
        self.assertEqual(fields["quality"]["statuses"], ["not_scanned"])
        self.assertEqual(fields["stats"]["statuses"], ["captured"])
        self.assertEqual(item["firstObserved"]["sequence"], 1)
        self.assertEqual(item["lastObserved"]["sequence"], 2)
        self.assertEqual(result["catalog"]["creatures"][0]["fieldCoverage"]["entity_position"]["statuses"], ["captured"])
        self.assertIsNone(result["coverage"]["gameDatabaseCompleteness"])
        self.assertEqual(result["coverage"]["missingReasonCounts"], {"not_ready_or_restricted": 1})

    def test_loot_windows_deduplicate_revisions_and_never_turn_unknowns_into_rates(self):
        visible = {"loot_session_id": "loot-1", "item_id": 100, "slot": 1, "revision": 1, "quantity": 2,
                   "source_status": "mapped", "source_mapping_status": "unverified", "source_quantity_matches": True,
                   "sources": [{"creature_id": 300, "quantity": 2}]}
        rows = [("loot.opened", {"loot_session_id": "loot-1", "target_candidate": {"creature_id": 300}}),
                ("loot.visible", visible), ("loot.visible", visible),
                ("loot.visible", {**visible, "revision": 2, "quantity": 1}),
                ("loot.snapshot", {"loot_session_id": "loot-1", "completeness": "complete", "captured_slots": 1, "slot_count": 1}),
                ("item.received", {**visible, "quantity": 1}),
                ("loot.opened", {"loot_session_id": "loot-2", "target_candidate": {"creature_id": 300}})]
        document, result = project(make_session(1, rows))
        stats            = result["lootStatistics"]
        self.assertEqual(stats["windowCount"], 2)
        self.assertEqual(stats["windows"][0]["slotCount"], 1)
        self.assertEqual(stats["windows"][0]["slotRevisionCount"], 2)
        self.assertIsNone(stats["windows"][0]["dropRate"])
        self.assertIn("unverified_source_mapping", stats["windows"][0]["reasons"])
        self.assertIn("eligibility_not_recorded", stats["windows"][0]["reasons"])
        self.assertEqual(stats["dropRates"], [])
        self.assertTrue(all(edge["status"] == "candidate" for edge in result["relationships"]))

    def test_missing_recipe_metadata_is_not_applied_to_output_item(self):
        session = make_session(1, [("recipe.metadata", {"recipe_id": 600, "output_item_id": 100})])
        session["observations"][0]["missing_fields"] = {"data.name": "not_ready"}
        document, result = project(session)
        item             = result["catalog"]["items"][0]
        recipe           = result["catalog"]["recipes"][0]
        self.assertEqual(item["fieldCoverage"]["name"]["statuses"], ["not_scanned"])
        self.assertEqual(recipe["fieldCoverage"]["name"]["statuses"], ["unavailable"])

    def test_validated_source_with_zero_quantity_is_not_a_positive_loot_edge(self):
        document, result = project(make_session(1, [("loot.visible", {
            "item_id": 100, "source_status": "mapped", "source_mapping_status": "validated",
            "source_quantity_matches": True, "quantity": 2,
            "sources": [{"creature_id": 300, "quantity": 0}, {"creature_id": 301, "quantity": 2}],
        })]))
        self.assertEqual(len(result["relationships"]), 1)
        edge = result["relationships"][0]
        self.assertTrue(edge["subject"].endswith(":npc:301"))
        self.assertEqual(edge["attributes"]["sourceQuantity"], 2)

    def test_observation_bounds_use_server_time_when_available(self):
        first  = make_session(1, [("item.metadata", {"item_id": 100})])
        second = make_session(2, [("item.metadata", {"item_id": 100})])
        first["observations"][0]["observed_at_server_s"]  = 2000
        second["observations"][0]["observed_at_server_s"] = 1000
        document, result = project(first, second)
        item             = result["catalog"]["items"][0]
        self.assertEqual(item["observationOrder"], "server_time")
        self.assertEqual(item["firstObserved"]["sessionId"], second["session"]["session_id"])
        self.assertEqual(item["lastObserved"]["sessionId"], first["session"]["session_id"])

    def test_contextual_loot_target_is_not_joined_to_later_item(self):
        document, result = project(make_session(1, [
            ("loot.opened", {"loot_session_id": "loot-1", "target_candidate": {"creature_id": 300}}),
            ("loot.visible", {"loot_session_id": "loot-1", "item_id": 100, "source_status": "unknown"}),
        ]))
        self.assertEqual(result["relationships"], [])

    def test_projection_is_deterministic_and_does_not_modify_source(self):
        document, first = project(make_session(1, [("item.metadata", {"item_id": 100, "name": "Observed"})]))
        original        = copy.deepcopy(document)
        second          = database_projection(document["contexts"], document["sessions"],
                                              document["transactions"] + document["observations"])
        self.assertEqual(first, second)
        self.assertEqual(document, original)
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "database-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(first), {"catalog", "relationships", "coverage", "lootStatistics"})
        self.assertTrue(set(first) <= set(schema["properties"]))


if __name__ == "__main__":
    unittest.main()
