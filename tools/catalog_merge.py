"""Append category evidence without duplicating entities or observations."""

from __future__ import annotations

import copy
from collections.abc import Iterable

from tools import export_saved_variables as saved
from tools.catalog_entities import CatalogBuilder


def _index(rows: list[dict], key: str, label: str) -> dict:
    saved.require(isinstance(rows, list), f"Invalid category {label} list")
    result = {}
    for row in rows:
        saved.require(isinstance(row, dict) and isinstance(row.get(key), str) and row[key],
                      f"Invalid category {label} identity")
        saved.require(row[key] not in result, f"Duplicate category {label}: {row[key]}")
        result[row[key]] = row
    return result


def _without(row: dict, fields: set[str]) -> dict:
    result = {key: value for key, value in row.items() if key not in fields}
    return result


def _same(previous: dict, current: dict) -> bool:
    before = saved.canonical(previous)
    after  = saved.canonical(current)
    return before == after


def _raw_record(row: dict) -> dict:
    result = _without(row, {"entities", "observedAt", "channel"})
    if "location" in result:
        result["location"] = _without(result["location"], {"mapX", "mapY"})
    return result


def _source_ids(row: dict) -> set[str]:
    values = row["sourceIds"]
    saved.require(isinstance(values, list) and values
                  and all(isinstance(value, str) for value in values), "Invalid category provenance")
    return set(values)


def _merge_provenance(previous: list[dict], current: list[dict], key: str, label: str) -> list[dict]:
    result = copy.deepcopy(_index(previous, key, label))
    for identity, row in _index(current, key, label).items():
        if identity in result:
            old = result[identity]
            saved.require(_same(_without(old, {"sourceIds"}), _without(row, {"sourceIds"})),
                          f"Conflicting category {label}: {identity}")
            old["sourceIds"] = sorted(_source_ids(old) | _source_ids(row))
        else:
            result[identity] = copy.deepcopy(row)
    return [result[identity] for identity in sorted(result)]


def _validate(document: dict) -> None:
    saved.require(isinstance(document, dict) and document.get("format") == "forevertome.catalog-category"
                  and document.get("schemaVersion") == 1, "Unsupported category format")
    category = document["category"]
    kinds    = {"spells": "spell", "talents": "talent", "items": "item", "quests": "quest",
                "monsters": "npc", "npcs": "npc", "gathering": None}
    saved.require(category in kinds, "Unsupported catalog category")
    contexts = _index(document["contexts"], "id", "context")
    sessions = _index(document["sessions"], "id", "session")
    records  = _index(document["records"], "id", "observation")
    entries  = _index(document["entries"], "id" if category == "gathering" else "key", "entry")
    for session in sessions.values():
        saved.require(session["contextId"] in contexts and session["data"]["session_id"] == session["id"],
                      "Invalid category session")
    for row in records.values():
        saved.require(row["sessionId"] in sessions
                      and row["contextId"] == sessions[row["sessionId"]]["contextId"]
                      and row["id"] == f"{row['sessionId']}:{row['sequence']}", "Invalid category observation")
        saved.require(all(identity in records for identity in row["relatedIds"]),
                      "Dangling category observation reference")
    for entry in entries.values():
        sources = _source_ids(entry)
        saved.require(entry["contextId"] in contexts
                      and all(identity in records and records[identity]["contextId"] == entry["contextId"]
                              for identity in sources), "Invalid category entry provenance")
        if category == "gathering":
            saved.require(entry["id"] in sources and entry["sessionId"] == records[entry["id"]]["sessionId"]
                          and entry["spellId"] == records[entry["id"]]["data"].get("spell_id"),
                          "Invalid gathering identity")
            continue
        saved.require(entry["kind"] == kinds[category]
                      and entry["key"] == f"{entry['contextId']}:{entry['kind']}:{entry['nativeId']}",
                      "Invalid category entity identity")
        saved.require("displaySourceId" not in entry or entry["displaySourceId"] in sources,
                      "Invalid category display provenance")
        for fact in _index(entry["facts"], "id", "fact").values():
            saved.require(_source_ids(fact) <= sources, "Invalid category fact provenance")
        for variant in _index(entry.get("variants", []), "key", "variant").values():
            saved.require(_source_ids(variant) <= sources, "Invalid category variant provenance")


def _merge_entries(previous: dict, current: dict, records: list[dict]) -> list[dict]:
    gathering = current["category"] == "gathering"
    key       = "id" if gathering else "key"
    entries   = copy.deepcopy(_index(previous["entries"], key, "entry"))
    fields    = ("contextId", "sessionId", "profession", "spellId") if gathering else ("contextId", "kind", "nativeId")
    for identity, entry in _index(current["entries"], key, "entry").items():
        if identity not in entries:
            entries[identity] = copy.deepcopy(entry)
            continue
        old = entries[identity]
        saved.require(_same({field: old[field] for field in fields}, {field: entry[field] for field in fields}),
                      f"Conflicting category entry: {identity}")
        if gathering:
            sources = sorted(_source_ids(old) | _source_ids(entry))
            old.update(copy.deepcopy(entry))
            old["sourceIds"] = sources
            continue
        old["sourceIds"] = sorted(_source_ids(old) | _source_ids(entry))
        old["facts"]     = _merge_provenance(old["facts"], entry["facts"], "id", "fact")
        if "variants" in old or "variants" in entry:
            old["variants"] = _merge_provenance(old.get("variants", []), entry.get("variants", []), "key", "variant")
    if gathering:
        order = {row["id"]: index for index, row in enumerate(records)}
        return sorted(entries.values(), key=lambda entry: order[entry["id"]])
    builder = CatalogBuilder()
    for row in records:
        builder.add(row["contextId"], {
            "observation_id": row["id"], "kind": row["type"],
            "data": row["data"], "location": row.get("location"),
        })
    for bucket in builder.finish().values():
        for rebuilt in bucket:
            entry = entries.get(rebuilt["key"])
            if entry is not None and rebuilt.get("displaySourceId") in entry["sourceIds"]:
                for field in ("display", "details", "displaySourceId"):
                    entry[field] = rebuilt[field]
    return [entries[identity] for identity in sorted(entries)]


def validate_history(previous_views: Iterable[dict], current_document: dict) -> None:
    try:
        contexts = {}
        sessions = {}
        records  = {}
        history  = list(previous_views)
        for view in history:
            _validate(view)
        history.append({
            "contexts": current_document["contexts"], "sessions": current_document["sessions"],
            "records": current_document["transactions"] + current_document["observations"],
        })
        for view in history:
            for context in view["contexts"]:
                identity = context["id"]
                saved.require(identity not in contexts or _same(contexts[identity], context),
                              f"Conflicting category context: {identity}")
                contexts[identity] = context
            for session in view["sessions"]:
                identity = session["id"]
                header   = _without(session, {"diagnostics"})
                saved.require(identity not in sessions or _same(sessions[identity], header),
                              f"Conflicting category session: {identity}")
                sessions[identity] = header
            for row in view["records"]:
                identity = row["id"]
                raw      = _raw_record(row)
                saved.require(identity not in records or _same(records[identity], raw),
                              f"Conflicting category observation: {identity}")
                records[identity] = raw
    except (KeyError, TypeError, AttributeError) as error:
        raise saved.ExportError("Invalid category history; existing evidence was not replaced") from error


def merge_category(previous: dict | None, current: dict) -> dict:
    try:
        _validate(current)
        if previous is None:
            return copy.deepcopy(current)
        _validate(previous)
        saved.require(previous["category"] == current["category"], "Conflicting catalog categories")
        result   = copy.deepcopy(current)
        contexts = copy.deepcopy(_index(previous["contexts"], "id", "context"))
        sessions = copy.deepcopy(_index(previous["sessions"], "id", "session"))
        records  = copy.deepcopy(_index(previous["records"], "id", "observation"))
        for context in current["contexts"]:
            identity = context["id"]
            saved.require(identity not in contexts or _same(contexts[identity], context),
                          f"Conflicting category context: {identity}")
            contexts[identity] = copy.deepcopy(context)
        for session in current["sessions"]:
            identity = session["id"]
            saved.require(identity not in sessions
                          or _same(_without(sessions[identity], {"diagnostics"}), _without(session, {"diagnostics"})),
                          f"Conflicting category session: {identity}")
            sessions[identity] = copy.deepcopy(session)
        for row in current["records"]:
            identity = row["id"]
            saved.require(identity not in records or _same(_raw_record(records[identity]), _raw_record(row)),
                          f"Conflicting category observation: {identity}")
            records[identity] = copy.deepcopy(row)
        order              = {identity: index for index, identity in enumerate(sessions)}
        result["contexts"] = [contexts[identity] for identity in sorted(contexts)]
        result["sessions"] = list(sessions.values())
        result["records"]  = sorted(records.values(), key=lambda row: (order[row["sessionId"]], row["sequence"]))
        result["entries"]  = _merge_entries(previous, current, result["records"])
        _validate(result)
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise saved.ExportError("Invalid category catalog; existing evidence was not replaced") from error
