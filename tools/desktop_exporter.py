"""Manage desktop export work without blocking the application window."""

from __future__ import annotations

import json
import math
import os
import queue
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from tools.watch_catalog import CATEGORIES, CatalogWatcher


def settings_path() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "ForeverTomeExporter" / "settings.json"
    return Path.home() / "AppData" / "Local" / "ForeverTomeExporter" / "settings.json"


def load_settings(path: Path | None = None) -> dict[str, str]:
    target = Path(path) if path is not None else settings_path()
    try:
        if target.stat().st_size > 65536:
            return {}
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    if not isinstance(document, dict):
        return {}
    return {key: document[key] for key in ("source", "output_dir", "client")
            if isinstance(document.get(key), str) and document[key].strip()}


def save_settings(source: Path, output_dir: Path, path: Path | None = None, client: Path | None = None) -> None:
    target   = Path(path) if path is not None else settings_path()
    document = {"source": str(source), "output_dir": str(output_dir)}
    if client is not None:
        document["client"] = str(client)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=target.parent)
    temporary_path        = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_document(path: Path) -> dict:
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError(f"Cannot display {path.name}: the file is too large")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"Cannot display {path.name}: expected a JSON object")
    return document


class ExporterController:
    def __init__(self, events: queue.Queue | None = None,
                 watcher_factory: Callable = CatalogWatcher, interval: float = 2.0):
        if not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("The check interval must be a finite positive number")
        self.events          = events if events is not None else queue.Queue()
        self.watcher_factory = watcher_factory
        self.interval        = float(interval)
        self._lock           = threading.Lock()
        self._thread         = None
        self._stop           = threading.Event()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, source: Path, output_dir: Path, watch: bool = True) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("An export is already running")
            self._stop   = threading.Event()
            self._thread = threading.Thread(
                target=self._run, args=(Path(source).resolve(), Path(output_dir).resolve(), bool(watch)),
                name="ForeverTomeExporter", daemon=False,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()

    def _result(self, kind: str, source: Path, output_dir: Path, document: dict | None,
                source_signature: tuple | None) -> dict:
        if document is None:
            document = read_document(output_dir / "latest.json")
        summary   = document.get("summary")
        export_id = document.get("exportId")
        if not isinstance(summary, dict) or not isinstance(export_id, str):
            raise ValueError("The catalog is missing its export summary")
        for field in ("observationCount", "transactionCount"):
            value = summary.get(field)
            if type(value) is not int or value < 0:
                raise ValueError(f"The catalog summary has an invalid {field}")
        counts = {}
        for category in CATEGORIES:
            view = read_document(output_dir / f"{category}.json")
            if view.get("exportId") != export_id or view.get("category") != category:
                raise ValueError("The category files do not match the current export")
            entries = view.get("entries")
            if not isinstance(entries, list):
                raise ValueError(f"The {category} catalog is missing its entries")
            counts[category] = len(entries)
        saved_time = source_signature[1] / 1_000_000_000 if source_signature else source.stat().st_mtime
        saved_at   = datetime.fromtimestamp(saved_time, timezone.utc).astimezone().isoformat(timespec="seconds")
        return {
            "type": kind, "summary": summary, "exportId": export_id,
            "output_dir": str(output_dir), "saved_at": saved_at, "categoryCounts": counts,
        }

    def _run(self, source: Path, output_dir: Path, watch: bool) -> None:
        watcher    = None
        last_error = None
        reported   = False
        self.events.put({"type": "working", "source": str(source), "output_dir": str(output_dir)})
        try:
            while not self._stop.is_set():
                try:
                    if watcher is None:
                        watcher = self.watcher_factory(source, output_dir)
                    document = watcher.sync()
                    if document is not None or not reported or last_error is not None:
                        kind      = "exported" if document is not None else "current"
                        signature = getattr(watcher, "signature", None)
                        result    = self._result(kind, source, output_dir, document, signature)
                        self.events.put(result)
                        reported = True
                    last_error = None
                except Exception as error:
                    message = str(error) or type(error).__name__
                    if message != last_error:
                        self.events.put({"type": "error", "message": message, "retrying": watch})
                    last_error = message
                if not watch or self._stop.wait(self.interval):
                    break
        finally:
            self.events.put({"type": "stopped"})
