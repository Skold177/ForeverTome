"""Build a versioned website catalog and activity history from WoW SavedVariables."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import export_saved_variables as saved
from tools.catalog_entities import CatalogBuilder


FORMAT            = "forevertome.website-catalog"
SCHEMA_VERSION    = 1
GENERATOR_VERSION = "0.2.3"
TRANSACTION_KINDS = frozenset("""
quest.accepted quest.turned_in quest.reward_received quest.removed quest.objective_delta quest.ready
item.received inventory.delta loot.opened loot.slot_cleared loot.closed merchant.opened merchant.closed
spell.succeeded spell.learned spellbook.changed recipe.learned craft.result player.state
""".split())
OBSERVATION_KINDS = frozenset("""
session.started session.ended coverage.gap player.snapshot unit.sighting world.context world.transition
location.sample merchant.offer spell.metadata spell.metadata_unavailable spellbook.snapshot spellbook.scan
talent.metadata talent.rank talent.build talent.snapshot profession.snapshot recipe.metadata quest.baseline
quest.metadata_unavailable quest.snapshot quest.log_scope quest.dialogue quest.metadata interaction.snapshot
item.metadata_unresolved item.metadata loot.visible loot.snapshot loot.slot_unavailable inventory.snapshot
""".split())
CHANNELS = {
    "quest.reward_received": "quest_reward_receipt",
    "item.received": "loot_chat_receipt",
    "inventory.delta": "inventory_change",
    "craft.result": "craft_result",
}


def catalog_export_id(source_sha256: str) -> str:
    identity = f"{FORMAT}:{SCHEMA_VERSION}:{GENERATOR_VERSION}:{source_sha256}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def context_for(header: dict) -> dict:
    context = {"product": header["product"], "client": copy.deepcopy(header["client"])}
    digest  = hashlib.sha256(saved.canonical(context).encode("utf-8")).hexdigest()
    return {"id": "context:" + digest, **context}


def timestamp(value: int | float) -> str | None:
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        return None


def project_row(observation: dict, context_id: str, entities: list[dict]) -> dict:
    row = {
        "id": observation["observation_id"],
        "type": observation["kind"],
        "sessionId": observation["session_id"],
        "contextId": context_id,
        "sequence": observation["sequence"],
        "elapsedSeconds": observation["elapsed_s"],
        "data": copy.deepcopy(observation["data"]),
        "capture": copy.deepcopy(observation["capture"]),
        "evidence": copy.deepcopy(observation["evidence"]),
        "missingFields": copy.deepcopy(observation["missing_fields"]),
        "relatedIds": list(observation["related_observation_ids"]),
        "entities": entities,
    }
    if "observed_at_server_s" in observation:
        value = observation["observed_at_server_s"]
        row["observedAtUnix"] = value
        formatted = timestamp(value)
        if formatted is not None:
            row["observedAt"] = formatted
    if observation.get("location") is not None:
        location = copy.deepcopy(observation["location"])
        if location["status"] == "available":
            location["mapX"] = round(location["x"] * 100, 6)
            location["mapY"] = round(location["y"] * 100, 6)
        row["location"] = location
    if observation["kind"] in CHANNELS:
        row["channel"] = CHANNELS[observation["kind"]]
    return row


def build_catalog(database: dict, source_sha256: str) -> dict:
    saved.validate(database, saved.Limits())
    saved.require(isinstance(source_sha256, str) and re.fullmatch(r"[a-f0-9]{64}", source_sha256) is not None,
                  "Source SHA-256 must be a lowercase hex digest")
    saved.require(TRANSACTION_KINDS.isdisjoint(OBSERVATION_KINDS)
                  and TRANSACTION_KINDS | OBSERVATION_KINDS == saved.SUPPORTED_KINDS,
                  "Catalog routes must cover every supported observation kind")
    contexts     = {}
    sessions     = []
    transactions = []
    observations = []
    kinds        = Counter()
    builder      = CatalogBuilder()
    for session in database["sessions"]:
        header  = session["session"]
        context = context_for(header)
        contexts[context["id"]] = context
        sessions.append({
            "id": header["session_id"], "contextId": context["id"],
            "data": copy.deepcopy(header), "diagnostics": copy.deepcopy(session["diagnostics"]),
        })
        for observation in session["observations"]:
            kind = observation["kind"]
            refs = builder.add(context["id"], observation)
            row  = project_row(observation, context["id"], refs)
            kinds[kind] += 1
            if kind in TRANSACTION_KINDS:
                transactions.append(row)
            else:
                observations.append(row)
    catalog = builder.finish()
    result  = {
        "format": FORMAT,
        "schemaVersion": SCHEMA_VERSION,
        "generatorVersion": GENERATOR_VERSION,
        "exportId": catalog_export_id(source_sha256),
        "source": {
            "sha256": source_sha256, "schemaVersion": database["schema_version"],
            "synthetic": database["synthetic"], "observationCount": database["record_count"],
        },
        "contexts": sorted(contexts.values(), key=lambda context: context["id"]),
        "sessions": sessions,
        "catalog": catalog,
        "transactions": transactions,
        "observations": observations,
        "summary": {
            "observationCount": database["record_count"],
            "transactionCount": len(transactions),
            "kindCounts": dict(sorted(kinds.items())),
            "transactionCounts": dict(sorted(Counter(row["type"] for row in transactions).items())),
            "catalogCounts": {name: len(entries) for name, entries in catalog.items()},
            "receiptChannels": dict(sorted(Counter(row["channel"] for row in transactions if "channel" in row).items())),
        },
        "semantics": {
            "catalog": "Observed content in each client context; not a complete game database.",
            "display": "Representative observed metadata; inspect facts and exact item variants for context.",
            "locations": "Outer locations are player positions at observation time, not NPC spawn points.",
            "receipts": "Quest, chat, crafting and inventory channels can overlap. Do not sum channels as acquisitions.",
            "itemStats": "Absent stats are unknown, never zero. Older recordings did not capture gameplay stats.",
            "icons": "Game file IDs and paths require an asset resolver; no image bytes or public URL are implied.",
            "text": "Recorded strings are untrusted display text, not HTML.",
        },
    }
    validate_catalog(result)
    return result


def validate_catalog(document: dict) -> None:
    saved.require(document.get("format") == FORMAT and document.get("schemaVersion") == SCHEMA_VERSION,
                  "Unsupported website catalog format")
    contexts = {context["id"] for context in document["contexts"]}
    sessions = {session["id"]: session for session in document["sessions"]}
    saved.require(len(contexts) == len(document["contexts"]) and len(sessions) == len(document["sessions"]),
                  "Duplicate catalog context or session")
    saved.require(all(session["contextId"] in contexts for session in sessions.values()), "Unknown session context")
    entities = {}
    for entries in document["catalog"].values():
        for entity in entries:
            saved.require(entity["key"] not in entities and entity["contextId"] in contexts, "Invalid catalog identity")
            entities[entity["key"]] = entity
    records = {}
    counts  = Counter()
    for name, allowed in (("transactions", TRANSACTION_KINDS), ("observations", OBSERVATION_KINDS)):
        for row in document[name]:
            saved.require(row["id"] not in records, "Duplicate record identity")
            saved.require(row["type"] in allowed, "Incorrect record route")
            saved.require(row["sessionId"] in sessions, "Unknown record session")
            saved.require(row["contextId"] == sessions[row["sessionId"]]["contextId"], "Incorrect record context")
            saved.require(row["id"] == f"{row['sessionId']}:{row['sequence']}", "Incorrect record identity")
            for reference in row["entities"]:
                entity = entities.get(reference["key"])
                saved.require(entity is not None and entity["contextId"] == row["contextId"], "Unknown or cross-context entity")
            records[row["id"]] = row
            counts[row["type"]] += 1
    saved.require(len(records) == document["source"]["observationCount"] == document["summary"]["observationCount"],
                  "Catalog did not preserve every observation")
    saved.require(dict(counts) == document["summary"]["kindCounts"], "Incorrect kind counts")
    for row in records.values():
        saved.require(all(reference in records for reference in row["relatedIds"]), "Dangling observation reference")
    for entity in entities.values():
        source_ids = set(entity["sourceIds"])
        saved.require(source_ids and all(source in records and records[source]["contextId"] == entity["contextId"]
                                        for source in source_ids), "Invalid catalog provenance")
        if "displaySourceId" in entity:
            saved.require(entity["displaySourceId"] in source_ids, "Invalid display provenance")
        for fact in entity["facts"]:
            saved.require(fact["sourceIds"] and all(source in source_ids for source in fact["sourceIds"]),
                          "Invalid fact provenance")
        for variant in entity.get("variants", []):
            saved.require(variant["sourceIds"] and all(source in source_ids for source in variant["sourceIds"]),
                          "Invalid variant provenance")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="SavedVariables/ForeverTome.lua after /reload or logout")
    parser.add_argument("--output", type=Path, required=True, help="New website catalog JSON file (never overwritten)")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON for a smaller upload")
    options = parser.parse_args(arguments)
    try:
        saved.require(options.source.resolve() != options.output.resolve(), "Source and output paths must differ")
        saved.require(options.output.suffix.lower() == ".json", "Website output must have a .json extension")
        saved.require(not options.output.exists(), "Output already exists; choose a new file")
        database, digest = saved.read_stable(options.source)
        document         = build_catalog(database, digest)
        encoded          = json.dumps(document, ensure_ascii=False, allow_nan=False,
                                      indent=None if options.compact else 2,
                                      separators=(",", ":") if options.compact else None) + "\n"
        options.output.parent.mkdir(parents=True, exist_ok=True)
        with options.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
        summary = document["summary"]
        print(f"Cataloged {summary['observationCount']} observations into {summary['transactionCount']} transactions "
              f"and {sum(summary['catalogCounts'].values())} catalog entries.")
        print(f"Saved {options.output}")
        return 0
    except (saved.ExportError, OSError, ValueError) as error:
        print(f"Catalog export failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
