"""Convert ForeverTome SavedVariables data without executing Lua."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


class ExportError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 128 * 1024 * 1024
    string_bytes: int = 65536
    nodes: int = 4_000_000
    depth: int = 24
    sessions: int = 512
    observations: int = 60000


ARRAY_FIELDS = frozenset({
    "sessions", "observations", "related_observation_ids", "objectives", "changes",
    "rewards", "choices", "required_items", "available_quests", "active_quests",
    "options", "sources", "items", "reagents", "recipes", "costs",
    "currencies", "reward_items", "choice_items", "source_pairs", "spells",
    "reagent_slots", "links", "collectors",
})
SUPPORTED_KINDS = frozenset({
    "session.started", "session.ended", "coverage.gap", "player.snapshot", "player.state",
    "unit.sighting", "world.context", "world.transition", "location.sample",
    "merchant.opened", "merchant.offer", "merchant.closed", "spell.metadata", "spell.succeeded",
    "profession.snapshot", "recipe.learned", "recipe.metadata", "craft.result",
    "quest.baseline", "quest.metadata_unavailable", "quest.snapshot", "quest.objective_delta",
    "quest.ready", "quest.log_scope", "quest.dialogue", "quest.accepted", "quest.turned_in",
    "quest.removed", "quest.metadata", "interaction.snapshot", "item.metadata_unresolved",
    "item.metadata", "item.received", "loot.visible", "loot.opened", "loot.snapshot",
    "loot.slot_unavailable", "loot.slot_cleared", "loot.closed", "inventory.snapshot", "inventory.delta",
})
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
NUMBER     = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
LONG_OPEN  = re.compile(r"\[(=*)\[")
KINDS      = re.compile(r"[a-z_]+\.[a-z_]+\Z")


class Parser:
    def __init__(self, source: str, limits: Limits):
        self.source   = source
        self.limits   = limits
        self.position = 0
        self.nodes    = 0

    def fail(self, message: str):
        raise ExportError(f"{message} at character {self.position}")

    def whitespace(self):
        while self.position < len(self.source):
            if self.source[self.position].isspace():
                self.position += 1
            elif self.source.startswith("--", self.position):
                self.position += 2
                match = LONG_OPEN.match(self.source, self.position)
                if match:
                    closer = "]" + match.group(1) + "]"
                    end    = self.source.find(closer, match.end())
                    if end < 0:
                        self.fail("Unterminated comment")
                    self.position = end + len(closer)
                else:
                    end = self.source.find("\n", self.position)
                    self.position = len(self.source) if end < 0 else end + 1
            else:
                return

    def consume(self, token: str):
        self.whitespace()
        if not self.source.startswith(token, self.position):
            self.fail(f"Expected {token!r}")
        self.position += len(token)

    def string(self) -> str:
        quote  = self.source[self.position]
        result = bytearray()
        self.position += 1
        escapes = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11}
        while self.position < len(self.source):
            character = self.source[self.position]
            self.position += 1
            if character == quote:
                try:
                    return result.decode("utf-8")
                except UnicodeDecodeError:
                    self.fail("String contains invalid UTF-8")
            if character == "\\":
                if self.position >= len(self.source):
                    self.fail("Unterminated escape")
                character = self.source[self.position]
                self.position += 1
                if character in escapes:
                    result.append(escapes[character])
                elif character in "\\\"'":
                    result.extend(character.encode("utf-8"))
                elif character in "0123456789":
                    digits = character
                    while len(digits) < 3 and self.position < len(self.source) and self.source[self.position] in "0123456789":
                        digits += self.source[self.position]
                        self.position += 1
                    number = int(digits)
                    if number > 255:
                        self.fail("Decimal escape exceeds one byte")
                    result.append(number)
                elif character in "\r\n":
                    if character == "\r" and self.source.startswith("\n", self.position):
                        self.position += 1
                    result.append(10)
                else:
                    self.fail("Unsupported string escape")
            else:
                if character in "\r\n":
                    self.fail("Unescaped newline in quoted string")
                result.extend(character.encode("utf-8"))
            if len(result) > self.limits.string_bytes:
                self.fail("String size limit exceeded")
        self.fail("Unterminated string")

    def value(self, depth: int = 0):
        self.whitespace()
        self.nodes += 1
        if self.nodes > self.limits.nodes or depth > self.limits.depth:
            self.fail("Data complexity limit exceeded")
        if self.position >= len(self.source):
            self.fail("Unexpected end of data")
        character = self.source[self.position]
        if character in "\"'":
            return self.string()
        if character == "{":
            return self.table(depth + 1)
        match = LONG_OPEN.match(self.source, self.position)
        if match:
            closer = "]" + match.group(1) + "]"
            end    = self.source.find(closer, match.end())
            if end < 0:
                self.fail("Unterminated long string")
            result = self.source[match.end():end].replace("\r\n", "\n").replace("\r", "\n")
            if result.startswith("\n"):
                result = result[1:]
            self.position = end + len(closer)
            if len(result.encode("utf-8")) > self.limits.string_bytes:
                self.fail("String size limit exceeded")
            return result
        match = NUMBER.match(self.source, self.position)
        if match:
            token = match.group()
            self.position = match.end()
            try:
                result = float(token) if any(part in token for part in ".eE") else int(token)
            except ValueError:
                self.fail("Invalid number")
            if abs(result) > 9007199254740991 or not math.isfinite(result):
                self.fail("Number outside supported finite range")
            return result
        match = IDENTIFIER.match(self.source, self.position)
        if match and match.group() in ("true", "false", "nil"):
            self.position = match.end()
            return {"true": True, "false": False, "nil": None}[match.group()]
        self.fail("Only literal data is permitted")

    def table(self, depth: int) -> dict:
        self.consume("{")
        result     = {}
        next_index = 1
        while True:
            self.whitespace()
            if self.source.startswith("}", self.position):
                self.position += 1
                return result
            if self.source.startswith("[", self.position) and not LONG_OPEN.match(self.source, self.position):
                self.position += 1
                key = self.value(depth)
                if type(key) not in (str, int) or isinstance(key, int) and key < 1:
                    self.fail("Table keys must be strings or positive integers")
                self.consume("]")
                self.consume("=")
                value = self.value(depth)
            else:
                start = self.position
                match = IDENTIFIER.match(self.source, self.position)
                if match:
                    self.position = match.end()
                    self.whitespace()
                if match and self.source.startswith("=", self.position):
                    key = match.group()
                    self.position += 1
                    value = self.value(depth)
                else:
                    self.position = start
                    key           = next_index
                    next_index += 1
                    value = self.value(depth)
            if isinstance(key, str) and len(key.encode("utf-8")) > 128:
                self.fail("Table key size limit exceeded")
            if key in result:
                self.fail("Duplicate table key")
            result[key] = value
            self.whitespace()
            if self.source.startswith((",", ";"), self.position):
                self.position += 1
            elif not self.source.startswith("}", self.position):
                self.fail("Expected table separator or closing brace")

    def parse(self) -> dict:
        self.whitespace()
        match = IDENTIFIER.match(self.source, self.position)
        if not match or match.group() != "ForeverTomeDB":
            self.fail("Expected ForeverTomeDB assignment")
        self.position = match.end()
        self.consume("=")
        result = self.value()
        self.whitespace()
        if self.source.startswith(";", self.position):
            self.position += 1
            self.whitespace()
        if self.position != len(self.source):
            self.fail("Trailing executable or unexpected data")
        if not isinstance(result, dict):
            self.fail("Database must be a table")
        return result


def normalize(value, field: str = ""):
    if not isinstance(value, dict):
        return value
    integer_keys = [key for key in value if type(key) is int]
    is_array     = field in ARRAY_FIELDS or bool(value) and len(integer_keys) == len(value) and set(integer_keys) == set(range(1, len(value) + 1))
    if is_array:
        if set(value) != set(range(1, len(value) + 1)):
            raise ExportError(f"Array {field!r} contains noncontiguous or named keys")
        return [normalize(value[index]) for index in range(1, len(value) + 1)]
    result = {}
    for key, child in value.items():
        name = str(key)
        if name in result:
            raise ExportError("Table keys collide in JSON representation")
        result[name] = normalize(child, name)
    return result


def require(condition: bool, message: str):
    if not condition:
        raise ExportError(message)


def integer(value, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 9007199254740991


def numeric(value, minimum: float = 0) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def validate_payload_shapes(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ARRAY_FIELDS:
                require(isinstance(child, list), f"Invalid array field {key}")
            validate_payload_shapes(child)
    elif isinstance(value, list):
        for child in value:
            validate_payload_shapes(child)


def validate(database: dict, limits: Limits):
    require(set(database) <= {"schema_version", "synthetic", "installation_id", "next_session", "settings", "sessions", "record_count", "estimated_bytes"}, "Unsupported database fields")
    require(database.get("schema_version") == 1 and type(database.get("schema_version")) is int, "Unsupported schema version")
    require(type(database.get("synthetic")) is bool, "Missing synthetic flag")
    identity = database.get("installation_id")
    require(isinstance(identity, str) and re.fullmatch(r"[a-f0-9]{32}", identity) is not None, "Invalid installation identity")
    require(integer(database.get("next_session")), "Invalid session serial")
    settings = database.get("settings")
    require(isinstance(settings, dict) and type(settings.get("paused")) is bool, "Invalid settings")
    sessions = database.get("sessions")
    require(isinstance(sessions, list) and len(sessions) <= limits.sessions, "Invalid session collection")
    session_ids     = set()
    observation_ids = set()
    references      = []
    total           = 0
    for entry in sessions:
        require(isinstance(entry, dict), "Invalid session entry")
        header       = entry.get("session")
        observations = entry.get("observations")
        diagnostics  = entry.get("diagnostics")
        require(isinstance(header, dict) and isinstance(observations, list) and isinstance(diagnostics, dict), "Invalid session envelope")
        session_id = header.get("session_id")
        require(isinstance(session_id, str) and re.fullmatch(re.escape(identity) + r"-[1-9][0-9]*", session_id) is not None, "Invalid session ID")
        require(session_id not in session_ids and int(session_id.rsplit("-", 1)[1]) <= database["next_session"], "Duplicate or impossible session ID")
        session_ids.add(session_id)
        for field in ("product", "addon_version", "adapter_id"):
            require(isinstance(header.get(field), str) and bool(header[field]), f"Invalid session {field}")
        require(isinstance(header.get("client"), dict) and isinstance(header.get("capabilities"), dict), "Invalid client or capability header")
        for capability in header["capabilities"].values():
            require(isinstance(capability, dict) and isinstance(capability.get("status"), str)
                    and type(capability.get("enabled")) is bool, "Invalid capability status")
        client = header["client"]
        for field in ("version", "build", "locale"):
            require(isinstance(client.get(field), str) and bool(client[field]), f"Invalid client {field}")
        for field in ("interface_version", "project_id"):
            require(field not in client or integer(client[field]), f"Invalid client {field}")
        require("started_at_server_s" not in header or numeric(header["started_at_server_s"]), "Invalid session start time")
        require(isinstance(diagnostics.get("counts"), dict) and all(integer(count) for count in diagnostics["counts"].values()), "Invalid diagnostics")
        require(integer(diagnostics.get("distinct")), "Invalid diagnostic count")
        previous = 0
        for sequence, observation in enumerate(observations, 1):
            total += 1
            require(total <= limits.observations, "Observation count limit exceeded")
            require(isinstance(observation, dict), "Invalid observation")
            observation_id = f"{session_id}:{sequence}"
            require(observation.get("sequence") == sequence and type(observation.get("sequence")) is int, "Invalid observation sequence")
            require(observation.get("session_id") == session_id and observation.get("observation_id") == observation_id, "Observation identity mismatch")
            require(observation_id not in observation_ids, "Duplicate observation ID")
            observation_ids.add(observation_id)
            kind = observation.get("kind")
            require(isinstance(kind, str) and KINDS.fullmatch(kind) is not None and kind in SUPPORTED_KINDS, "Unsupported observation kind")
            elapsed = observation.get("elapsed_s")
            require(numeric(elapsed) and elapsed >= previous, "Invalid or decreasing observation time")
            previous = elapsed
            if "observed_at_server_s" in observation:
                require(numeric(observation["observed_at_server_s"]), "Invalid wall-clock time")
            for field in ("capture", "data", "evidence", "missing_fields"):
                require(isinstance(observation.get(field), dict), f"Invalid observation {field}")
            validate_payload_shapes(observation["data"])
            capture = observation["capture"]
            for field in ("event", "method", "api"):
                require(field not in capture or isinstance(capture[field], str), f"Invalid capture {field}")
            for field in ("sampled_elapsed_s", "trigger_elapsed_s"):
                require(field not in capture or numeric(capture[field]), f"Invalid capture {field}")
            require(isinstance(observation["evidence"].get("method"), str) and bool(observation["evidence"]["method"]), "Missing evidence method")
            require(all(isinstance(value, str) for value in observation["missing_fields"].values()), "Invalid missing-field reason")
            related = observation.get("related_observation_ids")
            require(isinstance(related, list) and all(isinstance(item, str) for item in related), "Invalid observation references")
            references.extend(related)
            location = observation.get("location")
            if location is not None:
                require(isinstance(location, dict) and location.get("status") in ("available", "unavailable"), "Invalid location")
                require("ui_map_id" not in location or integer(location["ui_map_id"], 1), "Invalid location map")
                require("sampled_elapsed_s" not in location or numeric(location["sampled_elapsed_s"]), "Invalid location sample time")
                if location["status"] == "available":
                    require(location.get("subject") == "player" and location.get("coordinate_system") == "ui_map_normalized", "Unsupported coordinate system")
                    require(integer(location.get("ui_map_id"), 1), "Invalid location map")
                    require(all(numeric(location.get(axis)) and location[axis] <= 1 for axis in ("x", "y")), "Invalid map coordinates")
                else:
                    require(isinstance(location.get("reason"), str) and "x" not in location and "y" not in location, "Invalid unavailable location")
    require(all(reference in observation_ids for reference in references), "Dangling observation reference")
    require(integer(database.get("record_count")) and database["record_count"] == total, "Stored observation count does not match data")
    require(integer(database.get("estimated_bytes")), "Invalid storage estimate")


def parse_saved_variables(source: bytes | str, limits: Limits = Limits()) -> dict:
    raw = source.encode("utf-8") if isinstance(source, str) else source
    require(len(raw) <= limits.file_bytes, "Input file size limit exceeded")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ExportError("Input must be UTF-8") from error
    database = normalize(Parser(text, limits).parse())
    validate(database, limits)
    return database


def read_stable(path: Path, limits: Limits = Limits()) -> tuple[dict, str]:
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= limits.file_bytes, "Input file size limit exceeded")
        raw   = stream.read(limits.file_bytes + 1)
        after = os.fstat(stream.fileno())
        named = path.stat()
    identity = (before.st_size, before.st_mtime_ns, before.st_ino)
    require(identity == (after.st_size, after.st_mtime_ns, after.st_ino) == (named.st_size, named.st_mtime_ns, named.st_ino)
            and len(raw) == before.st_size, "Input changed during reading; save and copy it again")
    return parse_saved_variables(raw, limits), hashlib.sha256(raw).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def import_sqlite(database: dict, destination: Path) -> int:
    inserted   = 0
    connection = sqlite3.connect(destination)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS ft_sessions (session_id TEXT PRIMARY KEY, header_json TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS ft_observations (observation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL, record_json TEXT NOT NULL, UNIQUE(session_id, sequence))")
            for entry in database["sessions"]:
                header     = entry["session"]
                session_id = header["session_id"]
                encoded    = canonical(header)
                existing   = connection.execute("SELECT header_json FROM ft_sessions WHERE session_id = ?", (session_id,)).fetchone()
                require(existing is None or existing[0] == encoded, f"Conflicting session ID: {session_id}")
                connection.execute("INSERT OR IGNORE INTO ft_sessions VALUES (?, ?)", (session_id, encoded))
                for observation in entry["observations"]:
                    identity = observation["observation_id"]
                    encoded  = canonical(observation)
                    existing = connection.execute("SELECT record_json FROM ft_observations WHERE observation_id = ?", (identity,)).fetchone()
                    require(existing is None or existing[0] == encoded, f"Conflicting observation ID: {identity}")
                    if existing is None:
                        connection.execute("INSERT INTO ft_observations VALUES (?, ?, ?, ?)", (identity, session_id, observation["sequence"], encoded))
                        inserted += 1
    finally:
        connection.close()
    return inserted


def write_export(database: dict, destination: Path, format_name: str, source_hash: str):
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        if format_name == "json":
            json.dump(database, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        else:
            metadata = {key: value for key, value in database.items() if key != "sessions"}
            stream.write(canonical({"type": "export", "source_sha256": source_hash, "database": metadata}) + "\n")
            for entry in database["sessions"]:
                stream.write(canonical({"type": "session", "session": entry["session"], "diagnostics": entry["diagnostics"]}) + "\n")
                for observation in entry["observations"]:
                    stream.write(canonical({"type": "observation", "observation": observation}) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Stable copy of SavedVariables/ForeverTome.lua after /reload or logout")
    parser.add_argument("--output", type=Path, required=True, help="New JSON or JSONL file; existing files are never replaced")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    parser.add_argument("--sqlite", type=Path, help="Optional local evidence database with idempotent import")
    args = parser.parse_args(argv)
    try:
        paths = [args.source.resolve(), args.output.resolve()]
        if args.sqlite is not None:
            paths.append(args.sqlite.resolve())
        require(len(paths) == len(set(paths)), "Source, output and SQLite paths must differ")
        require(not args.output.exists(), "Output already exists; choose a new file")
        database, digest = read_stable(args.source)
        write_export(database, args.output, args.format, digest)
        inserted = import_sqlite(database, args.sqlite) if args.sqlite else None
        summary  = f"Exported {database['record_count']} observations across {len(database['sessions'])} sessions."
        if inserted is not None:
            summary += f" Imported {inserted} new observations into SQLite."
        print(summary)
        return 0
    except (ExportError, OSError, sqlite3.Error) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
