"""Append saved WoW observations to cumulative category JSON files."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import export_saved_variables as saved
from tools.build_catalog import FORMAT, SCHEMA_VERSION, build_catalog, catalog_export_id, validate_catalog
from tools.catalog_merge import merge_category, validate_history


CATEGORY_FORMAT = "forevertome.catalog-category"
CATEGORIES      = ("spells", "talents", "items", "quests", "monsters", "npcs", "gathering")


def category_catalog(document: dict, category: str) -> dict:
    saved.require(category in CATEGORIES, "Unsupported catalog category")
    if category == "gathering":
        from tools.catalog_gathering import gathering_entries

        entries = gathering_entries(document)
    else:
        entries = document["catalog"]["npcs" if category == "monsters" else category]
    if category == "monsters":
        selected = []
        for entity in entries:
            for fact in entity["facts"]:
                data     = fact["data"]
                reaction = data.get("reaction") if isinstance(data, dict) else None
                if type(reaction) in (int, float) and reaction in (1, 2, 3, 4):
                    selected.append(entity)
                    break
        entries = selected
    record_index  = {row["id"]: row for row in document["transactions"] + document["observations"]}
    selected_ids  = set()
    pending       = [source for entity in entries for source in entity["sourceIds"]]
    session_order = {session["id"]: index for index, session in enumerate(document["sessions"])}
    while pending:
        source = pending.pop()
        if source in selected_ids:
            continue
        saved.require(source in record_index, "Category has an unknown source observation")
        selected_ids.add(source)
        pending.extend(record_index[source]["relatedIds"])
    records     = sorted((record_index[source] for source in selected_ids),
                         key=lambda row: (session_order[row["sessionId"]], row["sequence"]))
    session_ids = {row["sessionId"] for row in records}
    sessions    = [session for session in document["sessions"] if session["id"] in session_ids]
    result      = {
        "format": CATEGORY_FORMAT, "schemaVersion": SCHEMA_VERSION, "category": category,
        "generatorVersion": document["generatorVersion"],
        "exportId": document["exportId"], "source": copy.deepcopy(document["source"]),
        "contexts": copy.deepcopy(document["contexts"]), "entries": copy.deepcopy(entries),
        "records": copy.deepcopy(records), "sessions": copy.deepcopy(sessions),
        "semantics": copy.deepcopy(document["semantics"]),
    }
    if category == "monsters":
        result["selection"] = {
            "method": "observed_reaction", "reactions": [1, 2, 3, 4],
            "meaning": "Observed hostile or neutral reaction to player; not a universal creature classification.",
        }
    elif category == "gathering":
        result["selection"] = {
            "method": "recognized_gather_cast",
            "meaning": "Player positions on recognized successful gathering casts; not resource-node coordinates.",
        }
    return result


def atomic_write(path: Path, encoded: bytes) -> tuple:
    descriptor, temporary = tempfile.mkstemp(prefix=".catalog-", suffix=".tmp", dir=path.parent)
    temporary_path        = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        written = temporary_path.stat()
        os.replace(temporary_path, path)
        return written.st_size, written.st_mtime_ns, written.st_ino
    finally:
        temporary_path.unlink(missing_ok=True)


class CatalogWatcher:
    def __init__(self, source: Path, output_dir: Path):
        self.source            = source.resolve()
        self.output_dir        = output_dir.resolve()
        self.latest            = self.output_dir / "latest.json"
        self.outputs           = {category: self.output_dir / f"{category}.json" for category in CATEGORIES}
        self.outputs["latest"] = self.latest
        self.signature         = None
        self.output_signatures = {}
        self.digest            = None
        for path in self.outputs.values():
            saved.require(self.source != path, "Source and output paths must differ")
            saved.require(not path.is_symlink(), "Output must not be a symbolic link")

    def existing_digest(self) -> str | None:
        identity = self.existing_identity("latest")
        return identity[0] if identity else None

    def existing_identity(self, name: str) -> tuple | None:
        document = self.read_catalog(self.outputs[name], None if name == "latest" else name)
        if document is None:
            return None
        return document["source"]["sha256"], document["exportId"]

    def read_catalog(self, path: Path, category: str | None = None) -> dict | None:
        expected_format = CATEGORY_FORMAT if category else FORMAT
        saved.require(not path.is_symlink(), f"Output {path.name} must not be a symbolic link")
        if not path.exists():
            return None
        saved.require(path.is_file(), f"Output {path.name} must be a regular file")
        saved.require(path.stat().st_size <= 512 * 1024 * 1024, f"Existing {path.name} is too large")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            raise saved.ExportError(f"Refusing to replace an unrelated or invalid {path.name}") from error
        saved.require(isinstance(document, dict) and document.get("format") == expected_format
                      and document.get("schemaVersion") == SCHEMA_VERSION,
                      f"Refusing to replace an unrelated {path.name}")
        if category:
            saved.require(document.get("category") == category, f"Refusing to replace an unrelated {path.name} category")
        source = document.get("source")
        saved.require(isinstance(source, dict) and isinstance(source.get("sha256"), str)
                      and isinstance(document.get("exportId"), str), f"Invalid {path.name} catalog source")
        return document

    def legacy_catalogs(self, latest: dict | None):
        for path in sorted(self.output_dir.glob("catalog-*.json")):
            document = self.read_catalog(path)
            saved.require(document is not None, f"Snapshot disappeared: {path.name}")
            try:
                validate_catalog(document)
            except (KeyError, TypeError, AttributeError) as error:
                raise saved.ExportError(f"Invalid legacy catalog {path.name}") from error
            yield document
        if latest is not None:
            try:
                validate_catalog(latest)
            except (KeyError, TypeError, AttributeError) as error:
                raise saved.ExportError("Invalid legacy latest.json") from error
            yield latest

    def output_file_signature(self, path: Path) -> tuple | None:
        saved.require(not path.is_symlink(), f"Output {path.name} must not be a symbolic link")
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return stat.st_size, stat.st_mtime_ns, stat.st_ino

    def sync(self) -> dict | None:
        stat       = self.source.stat()
        signature  = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
        signatures = {name: self.output_file_signature(path) for name, path in self.outputs.items()}
        if signature == self.signature and all(signatures.values()) and signatures == self.output_signatures:
            return None
        previous         = {name: self.read_catalog(path, None if name == "latest" else name)
                            for name, path in self.outputs.items()}
        existing         = {name: (view["source"]["sha256"], view["exportId"]) if view else None
                            for name, view in previous.items()}
        database, digest = saved.read_stable(self.source)
        identity         = (digest, catalog_export_id(digest))
        if all(value == identity for value in existing.values()):
            self.signature         = signature
            self.output_signatures = signatures
            self.digest            = digest
            return None
        document  = build_catalog(database, digest)
        encoded   = (json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
        identity  = (digest, document["exportId"])
        migrating = [category for category in CATEGORIES if previous[category] is None
                     or previous[category].get("generatorVersion") != document["generatorVersion"]]
        if migrating:
            for legacy in self.legacy_catalogs(previous["latest"]):
                validate_history((view for name, view in previous.items() if name != "latest" and view), legacy)
                for category in migrating:
                    previous[category] = merge_category(previous[category], category_catalog(legacy, category))
        validate_history((view for name, view in previous.items() if name != "latest" and view), document)
        categories = {category: merge_category(previous[category], category_catalog(document, category))
                      for category in CATEGORIES if category != "monsters"}
        npcs       = categories["npcs"]
        monsters   = category_catalog({
            **document, "contexts": npcs["contexts"], "sessions": npcs["sessions"],
            "catalog": {"npcs": npcs["entries"]}, "transactions": [], "observations": npcs["records"],
        }, "monsters")
        categories["monsters"] = merge_category(previous["monsters"], monsters)
        views = {category: (json.dumps(categories[category], ensure_ascii=False, sort_keys=True,
                                      allow_nan=False, indent=2) + "\n").encode("utf-8")
                 for category in CATEGORIES}
        current = self.source.stat()
        saved.require(signature == (current.st_size, current.st_mtime_ns, current.st_ino),
                      "Input changed during catalog conversion; waiting for the next save check")
        saved.require(signatures == {name: self.output_file_signature(path) for name, path in self.outputs.items()},
                      "Output changed during catalog conversion; waiting for the next save check")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for category, content in views.items():
            if existing[category] != identity:
                signatures[category] = atomic_write(self.outputs[category], content)
        if existing["latest"] != identity:
            signatures["latest"] = atomic_write(self.latest, encoded)
        self.signature         = signature
        self.output_signatures = signatures
        self.digest            = digest
        return document


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Live SavedVariables/ForeverTome.lua (read only)")
    parser.add_argument("--output-dir", type=Path, required=True, help="Folder for cumulative category JSON files and latest.json")
    parser.add_argument("--interval", type=float, default=2, help="Seconds between save checks (default: 2)")
    parser.add_argument("--once", action="store_true", help="Convert the current save and exit")
    options = parser.parse_args(arguments)
    if not math.isfinite(options.interval) or options.interval < 0.25:
        parser.error("--interval must be a finite number of at least 0.25 seconds")
    try:
        watcher = CatalogWatcher(options.source, options.output_dir)
        for name in watcher.outputs:
            watcher.existing_identity(name)
    except (saved.ExportError, OSError) as error:
        print(f"Cannot start catalog watcher: {error}", file=sys.stderr, flush=True)
        return 1
    last_error = None
    print(f"Watching saved recordings; output: {watcher.latest}", flush=True)
    try:
        while True:
            try:
                document = watcher.sync()
                if document is not None:
                    summary = document["summary"]
                    print(f"Updated JSON: {summary['observationCount']} observations, "
                          f"{summary['transactionCount']} transactions, "
                          f"{sum(summary['catalogCounts'].values())} catalog entries.", flush=True)
                last_error = None
            except (saved.ExportError, OSError, ValueError) as error:
                message = str(error)
                if message != last_error:
                    print(f"Catalog update incomplete; existing files remain readable and the next check will retry: {message}",
                          file=sys.stderr, flush=True)
                    last_error = message
                if options.once:
                    return 1
            if options.once:
                return 0
            time.sleep(options.interval)
    except KeyboardInterrupt:
        print("Catalog watcher stopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
