"""Project a cumulative, provenance-preserving content database from observations."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from urllib.parse import quote

from tools.catalog_entities import CatalogBuilder


EXPECTED_FIELDS = {
    "item": ("name", "quality", "item_level", "stats", "tooltip_lines", "equip_location"),
    "quest": ("title", "description", "objective_text", "rewards", "choices"),
    "npc": ("name", "level", "classification", "reaction", "max_health", "entity_position"),
    "object": ("name", "observed_label", "tooltip_lines", "entity_position"),
    "spell": ("name", "description", "castTime", "minRange", "maxRange", "tooltip_lines"),
    "recipe": ("name", "output_item_id", "quantity_min", "quantity_max", "reagent_slots"),
    "talent": ("info",),
    "profession": ("professionName", "professionID"),
    "map": ("map_name",),
    "currency": ("name",),
}


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict) and value:
        for field, child in sorted(value.items()):
            path = f"{prefix}.{field}" if prefix else field
            result.update(_flatten(child, path))
    else:
        result[prefix] = copy.deepcopy(value)
    return result


def _observed(row):
    result = {"sourceId": row["id"], "sessionId": row["sessionId"], "sequence": row["sequence"]}
    for field in ("observedAt", "observedAtUnix"):
        if field in row:
            result[field] = row[field]
    return result


def _reference_parent(row, reference):
    value = row
    for field, index in re.findall(r"([A-Za-z_][A-Za-z_0-9]*)|\[([0-9]+)\]", reference["path"].rsplit(".", 1)[0]):
        if field:
            if not isinstance(value, dict):
                return {}
            value = value.get(field)
        elif isinstance(value, list) and int(index) < len(value):
            value = value[int(index)]
        else:
            return {}
    return value if isinstance(value, dict) else {}


def _field_status(reason):
    if reason == "restricted":
        return "restricted"
    if reason == "not_applicable":
        return "not_applicable"
    if reason in {"not_observed", "not_scanned"}:
        return "not_scanned"
    return "unavailable"


def _entity_fields(entity, records):
    fields       = defaultdict(dict)
    missing      = defaultdict(lambda: defaultdict(set))
    source_roots = defaultdict(set)
    for fact in entity["facts"]:
        if fact["type"] != "loot.provenance":
            roots = {fact["path"], re.sub(r"\[([0-9]+)\]", lambda match: "." + str(int(match.group(1)) + 1), fact["path"])}
            for source_id in fact["sourceIds"]:
                source_roots[source_id].update(roots)
        for path, value in _flatten(fact["data"]).items():
            identity  = _digest(value)
            candidate = fields[path].setdefault(identity, {"value": value, "sourceIds": set(), "factIds": set()})
            candidate["sourceIds"].update(fact["sourceIds"])
            candidate["factIds"].add(fact["id"])
    for source_id in entity["sourceIds"]:
        row   = records[source_id]
        roots = source_roots[source_id]
        for path, reason in row.get("missingFields", {}).items():
            normalized = path if path.startswith("data.") else "data." + path
            for root in roots:
                if normalized.startswith(root + "."):
                    relative = normalized[len(root) + 1:]
                    missing[relative][reason].add(source_id)
    result = {}
    for field in sorted(set(fields) | set(missing) | set(EXPECTED_FIELDS.get(entity["kind"], ()))):
        candidates = []
        for identity, candidate in sorted(fields[field].items()):
            candidates.append({"value": candidate["value"], "sourceIds": sorted(candidate["sourceIds"]),
                               "factIds": sorted(candidate["factIds"])})
        reasons  = [{"reason": reason, "status": _field_status(reason), "sourceIds": sorted(sources)}
                    for reason, sources in sorted(missing[field].items())]
        captured = bool(candidates) or any(path.startswith(field + ".") for path in fields)
        statuses = ["captured"] if captured else sorted({_field_status(reason) for reason in missing[field]})
        result[field] = {
            "statuses": sorted(set(statuses) | {entry["status"] for entry in reasons}) or ["not_scanned"],
            "candidates": candidates, "missing": reasons, "hasMultipleValues": len(candidates) > 1,
        }
    return result


class RelationshipBuilder:
    def __init__(self, entities):
        self.entities = entities
        self.edges    = {}

    def add(self, row, subject, predicate, target, status="observed", attributes=None):
        if subject is None or target is None or subject["key"] == target["key"]:
            return
        if subject["key"] not in self.entities or target["key"] not in self.entities:
            return
        base = {"contextId": row["contextId"], "subject": subject["key"], "predicate": predicate,
                "object": target["key"], "status": status, "attributes": copy.deepcopy(attributes or {})}
        identity = "relationship:" + _digest(base)
        edge     = self.edges.setdefault(identity, {"id": identity, **base, "sourceIds": set(), "evidence": []})
        edge["sourceIds"].add(row["id"])
        evidence = {"sourceId": row["id"], "subjectPath": subject["path"], "objectPath": target["path"]}
        if evidence not in edge["evidence"]:
            edge["evidence"].append(evidence)

    def finish(self):
        result = []
        for identity, edge in sorted(self.edges.items()):
            edge["sourceIds"]   = sorted(edge["sourceIds"])
            edge["evidence"]    = sorted(edge["evidence"], key=lambda value: (value["sourceId"], value["subjectPath"], value["objectPath"]))
            edge["sourceCount"] = len(edge["sourceIds"])
            result.append(edge)
        return result


def _relationships(records, entities):
    builder = RelationshipBuilder(entities)
    for row in records:
        data    = row["data"]
        refs    = row["entities"]
        kind    = row["type"]
        by_role = defaultdict(list)
        for reference in refs:
            by_role[reference["role"]].append(reference)
        primary = {role: next((reference for reference in values if reference["path"].count(".") == 1), None)
                   for role, values in by_role.items()}
        item    = primary.get("item")
        quest   = primary.get("quest")
        spell   = primary.get("spell")
        recipe  = primary.get("recipe")
        npc     = next((reference for reference in refs if reference["path"] == "data.npc.creature_id"), None)
        if kind == "spell.succeeded" and data.get("actor") == "npc":
            builder.add(row, npc, "casts_spell", spell)
        if kind == "merchant.offer" and npc:
            attributes = {field: copy.deepcopy(data[field]) for field in
                          ("price", "stackCount", "numAvailable", "isPurchasable", "hasExtendedCost", "costs", "interaction_id", "merchant_session_id")
                          if field in data}
            attributes["vendorKey"] = npc["key"]
            for role in ("item", "vendor_spell", "vendor_currency"):
                builder.add(row, npc, "sells", primary.get(role), attributes=attributes)
            for cost in by_role["vendor_cost"]:
                builder.add(row, item, "vendor_cost", cost, attributes=attributes)
        if kind.startswith("quest."):
            for role, predicate in (("reward", "offers_reward"), ("reward_choice", "offers_reward_choice"),
                                    ("required_item", "requires_item"), ("quest_start_item", "started_by_item")):
                for target in by_role[role]:
                    reward     = _reference_parent(row, target)
                    attributes = {field: copy.deepcopy(reward[field]) for field in ("quantity", "index", "reward_type", "link") if field in reward}
                    if "phase" in data:
                        attributes["phase"] = data["phase"]
                    builder.add(row, quest, predicate, target, attributes=attributes)
            if kind == "quest.reward_received":
                builder.add(row, quest, "reward_received", item, attributes={
                    field: data[field] for field in ("quantity", "quest_run_id", "recipient") if field in data})
            if kind == "quest.dialogue":
                predicate = {"QUEST_DETAIL": "starts_quest", "QUEST_PROGRESS": "ends_quest",
                             "QUEST_COMPLETE": "ends_quest"}.get(data.get("phase"))
                if predicate:
                    builder.add(row, npc, predicate, quest, "candidate", {"phase": data["phase"]})
        if kind == "interaction.snapshot":
            for target in by_role["offered_quest"]:
                builder.add(row, npc, "offers_quest", target)
            for target in by_role["active_quest"]:
                builder.add(row, npc, "discusses_quest", target)
        if kind.startswith("recipe."):
            for role, predicate in (("recipe_output", "produces"), ("recipe_quality_output", "produces_quality_variant"),
                                    ("recipe_reagent", "reagent_option"), ("base_recipe", "variant_of"),
                                    ("previous_recipe", "previous_recipe"), ("next_recipe", "next_recipe"),
                                    ("profession", "belongs_to_profession")):
                for target in by_role[role]:
                    attributes = {field: copy.deepcopy(data[field]) for field in ("quantity_min", "quantity_max")
                                  if role == "recipe_output" and field in data}
                    if role == "recipe_reagent":
                        for index, slot in enumerate(data.get("reagent_slots", [])):
                            if target["path"].startswith(f"data.reagent_slots[{index}]."):
                                attributes = {field: copy.deepcopy(value) for field, value in slot.items() if field != "reagents"}
                                attributes["slotArrayIndex"] = index
                                attributes["meaning"] = "One observed reagent option for this slot; inspect the slot's required flag and quantity rules."
                    builder.add(row, recipe, predicate, target, attributes=attributes)
        if kind == "item.metadata":
            for role, predicate in (("effect_spell_id", "has_effect_spell"), ("use_spell_id", "uses_spell"),
                                    ("equip_spell_id", "equips_spell"), ("item_spell_id", "item_spell")):
                for target in by_role[role]:
                    builder.add(row, item, predicate, target)
            for target in by_role["socketed_gem"]:
                gem        = _reference_parent(row, target)
                attributes = {"itemLink": data.get("requested_link", data.get("link"))}
                if "socket_index" in gem:
                    attributes["socketIndex"] = gem["socket_index"]
                builder.add(row, item, "socketed_gem", target, attributes=attributes)
        for role, predicate in (("base_spell", "variant_of"), ("override_spell", "overridden_by")):
            for target in by_role[role]:
                builder.add(row, spell, predicate, target)
        if kind == "talent.metadata":
            metadata  = primary.get("metadata")
            namespace = data.get("entity_type")
            for target in refs:
                path      = target["path"]
                predicate = None
                if path.startswith("data.info."):
                    if ".conditionIDs[" in path or path.endswith(".questID"):
                        predicate = "requires"
                    elif path.endswith(".spellID"):
                        predicate = "grants_spell"
                    elif path.endswith(".overriddenSpellID"):
                        predicate = "overrides_spell"
                    elif ".visibleEdges[" in path:
                        predicate = "visible_edge_to"
                    elif path.endswith(".definitionID"):
                        predicate = "has_definition"
                    elif any(field in path for field in (".treeIDs[", ".nodeIDs[", ".entryIDs[")):
                        predicate = "contains"
                    elif ".costs[" in path:
                        predicate = "requires_currency"
                    elif path.endswith(".rootNodeID"):
                        predicate = "root_node"
                    elif ".gates[" in path and path.endswith(".conditionID"):
                        predicate = "has_gate_condition"
                    elif ".gates[" in path and path.endswith(".topLeftNodeID"):
                        predicate = "gate_anchor"
                if predicate:
                    attributes = {"entityType": namespace}
                    if predicate == "visible_edge_to":
                        for index, edge in enumerate(data.get("info", {}).get("visibleEdges", [])):
                            if path.startswith(f"data.info.visibleEdges[{index}]."):
                                attributes.update(edge)
                    if predicate in {"requires_currency", "has_gate_condition", "gate_anchor"}:
                        attributes.update(copy.deepcopy(_reference_parent(row, target)))
                    builder.add(row, metadata, predicate, target, attributes=attributes)
                if path == "data.tree_id" and namespace != "tree":
                    builder.add(row, target, "contains", metadata)
        if kind in {"loot.visible", "item.received"}:
            for role in ("loot_source", "loot_candidate"):
                for source in by_role[role]:
                    descriptor = _reference_parent(row, source)
                    if role == "loot_source" and descriptor.get("quantity") == 0:
                        continue
                    status = "validated" if role == "loot_source" and data.get("source_quantity_matches") is True else "candidate"
                    attributes = {field: data[field] for field in
                                  ("loot_session_id", "slot", "revision", "source_status", "source_mapping_status") if field in data}
                    if "quantity" in descriptor:
                        attributes["sourceQuantity"] = descriptor["quantity"]
                    builder.add(row, source, "loot_observed" if status == "validated" else "loot_source_candidate", item,
                                status, attributes)
        for target in by_role["parent_map"]:
            for subject in by_role["observer_map"]:
                builder.add(row, subject, "parent_map", target)
        for subject in by_role["profession"]:
            for target in by_role["parent_profession"]:
                builder.add(row, subject, "parent_profession", target)
    return builder.finish()


def _coverage(sessions, records, catalog):
    kinds   = Counter()
    reasons = Counter()
    scans   = []
    gaps    = []
    for row in records:
        kinds[row["type"]] += 1
        reasons.update(row.get("missingFields", {}).values())
        if row["type"] in {"coverage.gap", "session.started", "session.ended"}:
            gaps.append({"sourceId": row["id"], "type": row["type"], "sessionId": row["sessionId"],
                         "data": copy.deepcopy(row["data"])})
        if (row["type"].endswith((".scan", ".snapshot")) or row["type"] in {"quest.log_scope", "inventory.storage"}) and any(
                field in row["data"] for field in ("completeness", "scope", "enumeration_complete")):
            scan = {field: copy.deepcopy(value) for field, value in row["data"].items()
                    if field in {"scope", "completeness", "enumeration_complete", "recipe_ids", "profession_id",
                                 "tree_ids", "config_id", "status", "bank_open", "expected_count", "captured_count"}
                    or field.endswith(("_count", "_status"))}
            scans.append({"sourceId": row["id"], "type": row["type"], "sessionId": row["sessionId"],
                          "contextId": row["contextId"], "data": scan,
                          "missingFields": copy.deepcopy(row.get("missingFields", {}))})
    return {
        "recordCount": len(records), "sessionCount": len(sessions), "kindCounts": dict(sorted(kinds.items())),
        "entityCounts": {bucket: len(entries) for bucket, entries in catalog.items()},
        "missingReasonCounts": dict(sorted(reasons.items())), "scans": scans, "boundaries": gaps,
        "sessionDiagnostics": [{"sessionId": session["id"], "diagnostics": copy.deepcopy(session["diagnostics"])}
                               for session in sessions],
        "gameDatabaseCompleteness": None,
        "semantics": "Coverage describes recorded observations and explicit scan scopes; the total game-content denominator is unknown.",
    }


def _loot_statistics(records):
    windows = {}
    for row in records:
        if not row["type"].startswith("loot."):
            continue
        loot_id = row["data"].get("loot_session_id")
        if not isinstance(loot_id, str) or not loot_id:
            continue
        identity = (row["sessionId"], loot_id)
        window   = windows.setdefault(identity, {"sessionId": row["sessionId"], "lootSessionId": loot_id,
                                                "contextId": row["contextId"], "sourceIds": [], "slots": {}, "snapshots": []})
        window["sourceIds"].append(row["id"])
        if row["type"] == "loot.visible":
            slot     = row["data"].get("slot")
            revision = row["data"].get("revision")
            if type(slot) is int and slot > 0 and type(revision) is int and revision > 0:
                window["slots"].setdefault(slot, {})[revision] = row
        if row["type"] == "loot.snapshot":
            window["snapshots"].append(row)
    result = []
    for identity, window in sorted(windows.items()):
        reasons = {"eligibility_not_recorded", "reopened_window_identity_unavailable", "source_independent_denominator_missing"}
        rows    = [row for revisions in window["slots"].values() for row in revisions.values()]
        if not any(row["data"].get("completeness") == "complete" for row in window["snapshots"]):
            reasons.add("incomplete_loot_snapshot")
        if not rows or any(row["data"].get("source_mapping_status") != "validated"
                           or row["data"].get("source_status") != "mapped"
                           or row["data"].get("source_quantity_matches") is not True for row in rows):
            reasons.add("unverified_source_mapping")
        result.append({
            "id": "loot-window:" + _digest(identity), "sessionId": window["sessionId"],
            "lootSessionId": window["lootSessionId"], "contextId": window["contextId"],
            "sourceIds": sorted(window["sourceIds"]), "slotCount": len(window["slots"]),
            "slotRevisionCount": len(rows), "eligibleDenominator": None, "dropRate": None,
            "status": "not_estimable", "reasons": sorted(reasons),
            "slots": [{"slot": slot, "revisions": [{"revision": revision, "sourceId": row["id"],
                        "itemId": row["data"].get("item_id"), "quantity": row["data"].get("quantity")}
                        for revision, row in sorted(revisions.items())]}
                      for slot, revisions in sorted(window["slots"].items())],
        })
    return {
        "windowCount": len(result), "windows": result, "eligibleDenominator": None, "dropRates": [],
        "status": "not_estimable",
        "requirements": ["validated_source_mapping", "complete_snapshot", "explicit_player_eligibility",
                         "stable_opportunity_identity_across_reopened_windows", "source_independent_loot_opportunity_samples"],
        "semantics": "Windows and slot revisions are evidence, not kills or independent loot opportunities. Receipts are excluded to avoid double counting.",
    }


def database_projection(contexts: list, sessions: list, records: list) -> dict:
    context_index = {context["id"]: context for context in contexts}
    session_order = {session["id"]: index for index, session in enumerate(sessions)}
    ordered       = sorted(records, key=lambda row: (session_order[row["sessionId"]], row["sequence"], row["id"]))
    builder       = CatalogBuilder()
    projected     = []
    for source in ordered:
        row = copy.deepcopy(source)
        row["entities"] = builder.add(row["contextId"], {
            "session_id": row["sessionId"], "observation_id": row["id"], "kind": row["type"],
            "data": row["data"], "location": row.get("location"),
        })
        projected.append(row)
    catalog = builder.finish()
    catalog["creatures"] = catalog.pop("npcs")
    catalog.setdefault("objects", [])
    record_index = {row["id"]: row for row in projected}
    entities     = {}
    for entries in catalog.values():
        for entity in entries:
            kind    = "creature" if entity["kind"] == "npc" else entity["kind"]
            context = context_index[entity["contextId"]]
            parts   = [context["product"], kind, str(entity["nativeId"])]
            entity["canonicalKind"] = kind
            entity["contentKey"]    = "content:" + ":".join(quote(part, safe="") for part in parts)
            entity["identityScope"] = "session" if entity["kind"] == "talent" and str(entity["nativeId"]).startswith("config:") else "content"
            sources = sorted((record_index[source] for source in entity["sourceIds"]),
                             key=lambda row: (session_order[row["sessionId"]], row["sequence"]))
            entity["observationOrder"] = "archive_session_order"
            if all("observedAtUnix" in row for row in sources):
                sources = sorted(sources, key=lambda row: (row["observedAtUnix"], session_order[row["sessionId"]], row["sequence"]))
                entity["observationOrder"] = "server_time"
            entity["sourceCount"]   = len(sources)
            entity["firstObserved"] = _observed(sources[0])
            entity["lastObserved"]  = _observed(sources[-1])
            entity["fieldCoverage"] = _entity_fields(entity, record_index)
            entity["multipleValueFields"] = [field for field, coverage in entity["fieldCoverage"].items()
                                              if coverage["hasMultipleValues"]]
            if kind == "creature":
                reactions = sorted({fact["data"]["reaction"] for fact in entity["facts"]
                                    if fact["type"] == "unit.descriptor" and type(fact["data"].get("reaction")) in (int, float)})
                entity["classification"] = {"scope": "observed_context", "reactionValues": reactions,
                                              "monsterObserved": any(1 <= reaction <= 4 for reaction in reactions)}
            entities[entity["key"]] = entity
    relationships = _relationships(projected, entities)
    services      = defaultdict(list)
    for edge in relationships:
        if edge["predicate"] in {"sells", "offers_quest", "starts_quest", "ends_quest"}:
            services[edge["subject"]].append({"type": edge["predicate"], "status": edge["status"], "relationshipId": edge["id"]})
    for entry in catalog["creatures"]:
        entry["services"] = services[entry["key"]]
        for fact in entry["facts"]:
            if fact["type"] == "npc.service":
                entry["services"].append({"type": fact["data"]["service"], "status": "observed", "sourceIds": fact["sourceIds"]})
    return {"catalog": catalog, "relationships": relationships,
            "coverage": _coverage(sessions, projected, catalog), "lootStatistics": _loot_statistics(projected)}
