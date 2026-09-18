"""Preserve all available observation evidence before publishing database projections."""

from __future__ import annotations

import copy
import hashlib
import re
from collections import Counter

from tools import export_saved_variables as saved
from tools.catalog_entities import CatalogBuilder
from tools.catalog_merge import _index, _raw_record, _same, _without, merge_diagnostics


FORMAT = "forevertome.catalog-history"


def history_id(document: dict) -> str:
    evidence = {field: document[field] for field in ("contexts", "sessions", "records", "imports", "retention")}
    return hashlib.sha256(saved.canonical(evidence).encode("utf-8")).hexdigest()


def validate_evidence(document: dict) -> tuple:
    try:
        contexts = _index(document["contexts"], "id", "context")
        sessions = _index(document["sessions"], "id", "session")
        records  = _index(document["records"], "id", "observation")
        for context in contexts.values():
            saved.require(isinstance(context["product"], str) and isinstance(context["client"], dict),
                          "Invalid history context")
        for session in sessions.values():
            saved.require(session["contextId"] in contexts and isinstance(session["data"], dict)
                          and session["data"]["session_id"] == session["id"], "Invalid history session")
            diagnostics = session["diagnostics"]
            saved.require(isinstance(diagnostics, dict) and isinstance(diagnostics.get("counts"), dict)
                          and all(isinstance(key, str) and saved.integer(value)
                                  for key, value in diagnostics["counts"].items())
                          and saved.integer(diagnostics.get("distinct")), "Invalid history diagnostics")
        for row in records.values():
            saved.require(row["sessionId"] in sessions and row["contextId"] == sessions[row["sessionId"]]["contextId"]
                          and saved.integer(row["sequence"], 1)
                          and row["id"] == f"{row['sessionId']}:{row['sequence']}", "Invalid history observation identity")
            saved.require(row["type"] in saved.SUPPORTED_KINDS and saved.numeric(row["elapsedSeconds"]),
                          "Invalid history observation type or time")
            saved.require(all(isinstance(row[field], dict) for field in ("data", "capture", "evidence", "missingFields"))
                          and isinstance(row["entities"], list), "Invalid history observation payload")
            saved.require(isinstance(row["relatedIds"], list)
                          and all(isinstance(identity, str) and identity in records for identity in row["relatedIds"]),
                          "Dangling history observation reference")
            saved.require(isinstance(row["evidence"].get("method"), str)
                          and all(isinstance(value, str) for value in row["missingFields"].values()),
                          "Invalid history observation evidence")
            saved.validate_payload_shapes(row["data"])
        return contexts, sessions, records
    except (KeyError, TypeError, AttributeError) as error:
        raise saved.ExportError("Invalid archived evidence; existing evidence was not replaced") from error


def validate_archive(document: dict) -> None:
    try:
        saved.require(document.get("format") == FORMAT and document.get("schemaVersion") == 1,
                      "Unsupported history format")
        contexts, sessions, records = validate_evidence(document)
        imports = _index(document["imports"], "id", "import")
        for entry in imports.values():
            saved.require(entry["kind"] in ("saved_variables", "legacy_snapshot", "legacy_category", "database_projection")
                          and isinstance(entry["name"], str)
                          and isinstance(entry["source"], dict)
                          and saved.integer(entry["recordCount"]), "Invalid history import")
        saved.require(document["retention"]["scope"] == "all_available_observations"
                      and document["retention"]["priorCoverage"] == "unknown"
                      and type(document["retention"]["legacyMigration"]) is bool, "Invalid history retention metadata")
        saved.require(document["summary"]["observationCount"] == len(records)
                      and document["summary"]["sessionCount"] == len(sessions)
                      and document["summary"]["kindCounts"] == dict(Counter(row["type"] for row in records.values())),
                      "Invalid history summary")
        saved.require(isinstance(document.get("historyId"), str)
                      and re.fullmatch(r"[a-f0-9]{64}", document["historyId"]) is not None
                      and document["historyId"] == history_id(document), "Invalid history evidence digest")
    except (KeyError, TypeError, AttributeError) as error:
        raise saved.ExportError("Invalid cumulative history; existing evidence was not replaced") from error


def merge_history(previous: dict | None, current: dict, sources: list[tuple[str, dict]]) -> dict:
    if previous is not None:
        validate_archive(previous)
    contexts = {}
    sessions = {}
    records  = {}
    imports  = {entry["id"]: copy.deepcopy(entry) for entry in previous["imports"]} if previous else {}
    views    = [("history.json", previous)] if previous else []
    views.extend(sources)
    views.append(("SavedVariables", current))
    for name, view in views:
        for context in view["contexts"]:
            identity = context["id"]
            saved.require(identity not in contexts or _same(contexts[identity], context),
                          f"Conflicting history context: {identity}")
            contexts[identity] = copy.deepcopy(context)
        for session in view["sessions"]:
            identity = session["id"]
            merged   = copy.deepcopy(session)
            if identity in sessions:
                old = sessions[identity]
                saved.require(_same(_without(old, {"diagnostics"}), _without(session, {"diagnostics"})),
                              f"Conflicting history session: {identity}")
                merged["diagnostics"] = merge_diagnostics(old["diagnostics"], session["diagnostics"])
            sessions[identity] = merged
        rows = view["records"] if "records" in view else view["transactions"] + view["observations"]
        for row in rows:
            identity = row["id"]
            saved.require(identity not in records or _same(_raw_record(records[identity]), _raw_record(row)),
                          f"Conflicting history observation: {identity}")
            records[identity] = copy.deepcopy(row)
        kind = "saved_variables" if name == "SavedVariables" else {
            "forevertome.catalog-category": "legacy_category", "forevertome.database": "database_projection",
        }.get(view["format"], "legacy_snapshot")
        if name == "history.json" or (previous and kind in ("legacy_category", "database_projection")) or (previous and name == "latest.json"):
            continue
        identity = hashlib.sha256(f"{kind}:{name}:{view['exportId']}".encode("utf-8")).hexdigest()
        imports[identity] = {
            "id": identity, "kind": kind, "name": name, "exportId": view["exportId"],
            "source": copy.deepcopy(view["source"]), "recordCount": len(rows),
        }
    order   = {identity: index for index, identity in enumerate(sessions)}
    ordered = sorted(records.values(), key=lambda row: (order[row["sessionId"]], row["sequence"]))
    builder = CatalogBuilder()
    for row in ordered:
        row["entities"] = builder.add(row["contextId"], {
            "observation_id": row["id"], "session_id": row["sessionId"], "kind": row["type"],
            "data": row["data"], "location": row.get("location"),
        })
    result = {
        "format": FORMAT, "schemaVersion": 1, "generatorVersion": current["generatorVersion"],
        "exportId": current["exportId"], "source": copy.deepcopy(current["source"]),
        "contexts": [contexts[identity] for identity in sorted(contexts)], "sessions": list(sessions.values()),
        "records": ordered, "imports": [imports[identity] for identity in sorted(imports)],
        "retention": {
            "scope": "all_available_observations", "priorCoverage": "unknown",
            "legacyMigration": any(entry["kind"].startswith("legacy_") for entry in imports.values()),
            "meaning": "Preserves every imported observation and session diagnostic. Legacy category files retain only their selected evidence; previously discarded records cannot be recovered.",
        },
        "summary": {
            "observationCount": len(ordered), "sessionCount": len(sessions),
            "kindCounts": dict(sorted(Counter(row["type"] for row in ordered).items())),
        },
        "semantics": copy.deepcopy(current["semantics"]),
    }
    result["historyId"] = history_id(result)
    validate_archive(result)
    return result
