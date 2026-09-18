"""Project gathering cast outcomes using the inspected Forever beta client tables."""

from __future__ import annotations

import copy


GATHERING_SPELLS = {
    "herbalism": frozenset({2366, 2368, 2369, 2371, 3570, 11993, 1235236}),
    "mining": frozenset({2575, 2576, 2577, 2578, 2579, 3564, 10248, 1235230}),
    "skinning": frozenset({8613, 8617, 8618, 10768}),
    "fishing": frozenset({7620, 7731, 7732, 18248}),
}
RULE_ID = "forever-beta-69893-gathering-casts-v2"


def gathering_entries(document: dict) -> list[dict]:
    contexts = {context["id"]: context for context in document["contexts"]}
    spells   = {entity["key"]: entity for entity in document["catalog"]["spells"]}
    entries  = []
    for row in document["transactions"]:
        if row["type"] not in {"spell.succeeded", "gathering.attempt"} or row["data"].get("actor") != "player":
            continue
        outcome = "succeeded" if row["type"] == "spell.succeeded" else row["data"].get("outcome")
        expected = {"succeeded": "UNIT_SPELLCAST_SUCCEEDED", "failed": "UNIT_SPELLCAST_FAILED",
                    "interrupted": "UNIT_SPELLCAST_INTERRUPTED"}
        if (outcome not in expected or row["capture"].get("event") != expected[outcome]
                or row["evidence"].get("method") != "direct_event"):
            continue
        context = contexts[row["contextId"]]
        client  = context["client"]
        if context["product"] != "WF" or client.get("version") != "1.60.1" or client.get("build") != "69893":
            continue
        spell_id = row["data"].get("spell_id")
        if type(spell_id) is not int:
            continue
        profession = next((name for name, identifiers in GATHERING_SPELLS.items() if spell_id in identifiers), None)
        if profession is None:
            continue
        entry = {
            "id": row["id"], "contextId": row["contextId"], "sessionId": row["sessionId"],
            "profession": profession, "spellId": spell_id, "elapsedSeconds": row["elapsedSeconds"],
            "sourceIds": [row["id"]], "evidence": copy.deepcopy(row["evidence"]),
            "classification": {"method": "client_spell_allowlist", "ruleId": RULE_ID},
            "positionMeaning": "player_at_successful_gathering_cast",
            "resourceIdentity": "not_observed", "receivedItems": "not_attributed",
            "outcome": outcome,
        }
        if outcome != "succeeded":
            entry["positionMeaning"] = "player_at_gathering_attempt"
        attempt_id = row["data"].get("attempt_id", row["data"].get("gathering_attempt_id"))
        if isinstance(attempt_id, str):
            entry["attemptId"] = attempt_id
        for field in ("location", "observedAt", "observedAtUnix"):
            if field in row:
                entry[field] = copy.deepcopy(row[field])
        for reference in row["entities"]:
            entity = spells.get(reference["key"])
            if entity and entity["nativeId"] == spell_id:
                entry["spellKey"] = entity["key"]
                if "name" in entity["display"]:
                    entry["spellName"] = entity["display"]["name"]
                break
        entries.append(entry)
    return entries
