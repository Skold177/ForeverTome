import copy
import unittest

from test_catalog import SHA256, make_database, make_session
from tools.build_catalog import build_catalog
from tools.catalog_gathering import gathering_entries


class GatheringCatalogTests(unittest.TestCase):
    def catalog(self, spell_ids, build="69893"):
        session = make_session(1, [("spell.succeeded", {"spell_id": identity, "actor": "player"}) for identity in spell_ids])
        session["session"]["client"]["build"] = build
        for observation in session["observations"]:
            observation["capture"] = {"event": "UNIT_SPELLCAST_SUCCEEDED"}
            observation["evidence"] = {"method": "direct_event"}
        return build_catalog(make_database(session), SHA256)

    def test_native_and_forever_gather_casts_retain_each_occurrence(self):
        document = self.catalog([2366, 1235236, 2575, 1235230, 8613, 8613])
        entries  = gathering_entries(document)
        self.assertEqual([entry["profession"] for entry in entries],
                         ["herbalism", "herbalism", "mining", "mining", "skinning", "skinning"])
        self.assertEqual(len({entry["id"] for entry in entries}), 6)
        for entry in entries:
            self.assertEqual(entry["sourceIds"], [entry["id"]])
            self.assertTrue(entry["spellKey"].endswith(f":spell:{entry['spellId']}"))

    def test_training_books_opening_and_unknown_builds_do_not_become_gathering(self):
        self.assertEqual(gathering_entries(self.catalog([1240952, 1245610, 1272073, 3365, 75])), [])
        self.assertEqual(gathering_entries(self.catalog([2366, 2575, 8613], build="99999")), [])

    def test_player_positions_are_preserved_without_inventing_nodes_or_drops(self):
        document = self.catalog([2575, 8613])
        document["transactions"][0]["location"] = {
            "status": "available", "subject": "player", "ui_map_id": 1411,
            "coordinate_system": "ui_map_normalized", "x": 0, "y": 0.25, "mapX": 0, "mapY": 25,
        }
        document["transactions"][1]["location"] = {"status": "unavailable", "reason": "no_position"}
        before  = copy.deepcopy(document)
        entries = gathering_entries(document)
        self.assertEqual(entries[0]["location"], document["transactions"][0]["location"])
        self.assertEqual(entries[1]["location"]["status"], "unavailable")
        self.assertNotIn("x", entries[1]["location"])
        for entry in entries:
            self.assertEqual(entry["resourceIdentity"], "not_observed")
            self.assertEqual(entry["receivedItems"], "not_attributed")
            self.assertEqual(entry["positionMeaning"], "player_at_successful_gathering_cast")
        self.assertEqual(document, before)

    def test_only_successful_player_events_are_classified(self):
        for field, value in (("actor", "pet"), ("spell_id", "2575")):
            document = self.catalog([2575])
            document["transactions"][0]["data"][field] = value
            self.assertEqual(gathering_entries(document), [])
        for field in ("capture", "evidence"):
            document = self.catalog([2575])
            document["transactions"][0][field] = {}
            self.assertEqual(gathering_entries(document), [])
        document = self.catalog([2575])
        document["transactions"][0]["type"] = "spell.learned"
        self.assertEqual(gathering_entries(document), [])


if __name__ == "__main__":
    unittest.main()
