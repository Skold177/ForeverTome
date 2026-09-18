"""Visible desktop controls for local ForeverTome catalog exports."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.desktop_exporter import ExporterController, load_settings, save_settings
from tools import addon_installer
from tools.watch_catalog import CATEGORIES


APP_NAME = "ForeverTome Exporter"
COLORS   = {"page": "#f5f3ef", "card": "#ffffff", "ink": "#242e32", "muted": "#657075",
            "line": "#dfdfd8", "gold": "#996c20", "header": "#243438", "green": "#28775a", "red": "#b04435"}


class ExporterApp:
    def __init__(self, root, source="", output_dir="", settings_file=None, discover=True, installer_backend=addon_installer):
        self.root          = root
        self.settings_file = settings_file
        self.controller    = ExporterController()
        self.closing       = False
        self.closed        = False
        self.watching      = False
        self.last_result   = None
        self.last_error    = None
        self.inputs        = []
        self.addon_thread  = None
        self.addon_events  = queue.Queue()
        self.addon_cancel  = threading.Event()
        self.installer     = installer_backend
        preferences        = load_settings(settings_file)
        self.client        = tk.StringVar(value=preferences.get("client", ""))
        self.addon_status  = tk.StringVar(value="Find your World of Warcraft: Forever Beta folder.")
        self.addon_version = tk.StringVar(value="Installed addon version: not checked")
        self.source        = tk.StringVar(value=source or preferences.get("source", ""))
        self.output_dir    = tk.StringVar(value=output_dir or preferences.get("output_dir", "")
                                         or str(Path.home() / "Documents" / "ForeverTome" / "Exports"))
        self.status        = tk.StringVar(value="Ready")
        self.detail        = tk.StringVar(value="Choose your recording, then export once or watch for new saves.")
        self.saved_at      = tk.StringVar(value="No save checked yet")
        self.totals        = tk.StringVar(value="Your catalog will appear here after an export.")
        self.counts        = {name: tk.StringVar(value="—") for name in CATEGORIES}
        root.title(APP_NAME)
        root.geometry("900x850")
        root.minsize(790, 820)
        root.configure(background=COLORS["page"])
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._layout()
        self._set_busy(False)
        self.root.after(100, self._drain_events)
        if discover:
            self.root.after(150, self._detect_clients)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["page"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure("TLabel", background=COLORS["page"], foreground=COLORS["ink"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=COLORS["card"])
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("CardMuted.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), background=COLORS["card"])
        style.configure("Count.TLabel", font=("Segoe UI", 22, "bold"), background=COLORS["card"])
        style.configure("TEntry", padding=8, fieldbackground=COLORS["card"], foreground=COLORS["ink"])
        style.configure("TNotebook", background=COLORS["page"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(20, 10), font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", COLORS["page"])],
                  foreground=[("selected", COLORS["gold"])])
        style.configure("TButton", padding=(14, 9), font=("Segoe UI", 10), background="#e9e7e1", borderwidth=0)
        style.map("TButton", background=[("active", "#dedbd2"), ("disabled", "#eeede9")],
                  foreground=[("disabled", "#939a9c")])
        style.configure("Primary.TButton", background=COLORS["gold"], foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#805a1d"), ("disabled", "#d7cbb8")],
                  foreground=[("disabled", "#f6f4f0")])

    def _layout(self):
        header = tk.Frame(self.root, background=COLORS["header"], padx=28, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="FOREVERTOME", background=COLORS["header"], foreground="#d9b572",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(header, text="Your addon and your catalogs", background=COLORS["header"], foreground="#ffffff",
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", pady=(5, 3))
        tk.Label(header, text="Install the latest addon and turn your saved adventures into JSON.",
                 background=COLORS["header"], foreground="#c7d2d1", font=("Segoe UI", 10)).pack(anchor="w")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        body = ttk.Frame(self.tabs, padding=(18, 16))
        self.tabs.add(body, text="Export recordings")
        self._addon_layout()
        paths = ttk.Frame(body, style="Card.TFrame", padding=18)
        paths.pack(fill="x")
        paths.columnconfigure(0, weight=1)
        self._path_row(paths, "WoW recording", self.source, self._browse_source, 0)
        self._path_row(paths, "Export folder", self.output_dir, self._browse_output, 2)
        ttk.Label(paths, text="WoW writes the recording when you /reload or log out.",
                  style="CardMuted.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(16, 16))
        self.watch_button = ttk.Button(actions, text="Start watching", style="Primary.TButton", command=self._watch)
        self.watch_button.pack(side="left")
        self.once_button = ttk.Button(actions, text="Export now", command=self._once)
        self.once_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop)
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open export folder", command=self._open_output).pack(side="right")

        status = ttk.Frame(body, style="Card.TFrame", padding=18)
        status.pack(fill="x")
        self.status_label = ttk.Label(status, textvariable=self.status, style="Title.TLabel")
        self.status_label.pack(anchor="w")
        ttk.Label(status, textvariable=self.detail, style="CardMuted.TLabel", wraplength=750,
                  justify="left").pack(anchor="w", pady=(5, 12))
        ttk.Label(status, textvariable=self.saved_at, style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(status, textvariable=self.totals, style="Card.TLabel").pack(anchor="w", pady=(5, 15))
        counts = ttk.Frame(status, style="Card.TFrame")
        counts.pack(fill="x")
        for column, category in enumerate(CATEGORIES):
            counts.columnconfigure(column, weight=1, uniform="category")
            ttk.Label(counts, textvariable=self.counts[category], style="Count.TLabel").grid(row=0, column=column, sticky="w")
            label = "NPCs" if category == "npcs" else category.capitalize()
            ttk.Label(counts, text=label, style="CardMuted.TLabel").grid(row=1, column=column, sticky="w")

        ttk.Label(body, text="Recent activity", style="Muted.TLabel").pack(anchor="w", pady=(16, 5))
        self.activity = tk.Text(body, height=3, wrap="word", background=COLORS["page"], foreground=COLORS["muted"],
                                font=("Segoe UI", 9), relief="flat", borderwidth=0, state="disabled", takefocus=False)
        self.activity.pack(fill="both", expand=True)
        ttk.Label(body, text="Only runs while this window is open. Files stay on your computer.",
                  style="Muted.TLabel").pack(anchor="w", pady=(12, 0))

    def _addon_layout(self):
        body = ttk.Frame(self.tabs, padding=(18, 20))
        self.tabs.add(body, text="Install / update addon")
        card = ttk.Frame(body, style="Card.TFrame", padding=20)
        card.pack(fill="x")
        ttk.Label(card, text="World of Warcraft: Forever Beta", style="Title.TLabel").pack(anchor="w")
        ttk.Label(card, text="Choose the game folder containing _classic_beta_.", style="CardMuted.TLabel").pack(anchor="w", pady=(5, 16))
        paths = ttk.Frame(card, style="Card.TFrame")
        paths.pack(fill="x")
        self.client_picker = ttk.Combobox(paths, textvariable=self.client, state="readonly", font=("Segoe UI", 10))
        self.client_picker.pack(side="left", fill="x", expand=True, ipady=6)
        self.client_picker.bind("<<ComboboxSelected>>", self._client_selected)
        self.client_browse = ttk.Button(paths, text="Browse…", command=self._browse_client)
        self.client_browse.pack(side="right", padx=(10, 0))
        ttk.Label(card, textvariable=self.addon_version, style="Card.TLabel").pack(anchor="w", pady=(16, 5))
        ttk.Label(card, text="Each update downloads the latest merged addon from GitHub.\n"
                             "Keep using this application for future addon updates; no new installer is needed.",
                  style="CardMuted.TLabel", wraplength=750).pack(anchor="w")
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=18)
        self.install_button = ttk.Button(actions, text="Install / update addon", style="Primary.TButton", command=self._install_addon)
        self.install_button.pack(side="left")
        self.detect_button = ttk.Button(actions, text="Find game folder", command=self._detect_clients)
        self.detect_button.pack(side="left", padx=8)
        ttk.Label(body, textvariable=self.addon_status, wraplength=780, justify="left").pack(anchor="w", pady=(0, 20))
        ttk.Label(body, text="Your recordings, game settings, and other addons are preserved.\n"
                            "After installing, reload WoW. A first installation may need a client restart.",
                  style="Muted.TLabel", justify="left").pack(anchor="w")

    def _addon_busy(self, busy):
        for widget in (self.install_button, self.detect_button, self.client_browse):
            widget.configure(state="disabled" if busy else "normal")
        self.client_picker.configure(state="disabled" if busy else "readonly")

    def _client_selected(self, event=None):
        try:
            client  = self.installer.normalize_client(Path(self.client.get()))
            version = self.installer.installed_version(client)
            self.addon_version.set("Installed addon version: " + (version or "not installed"))
            recordings = sorted((client / "WTF" / "Account").glob("*/SavedVariables/ForeverTome.lua"))
            if len(recordings) == 1 and not self.source.get():
                self.source.set(str(recordings[0]))
            self._remember()
        except (OSError, ValueError) as error:
            self.addon_status.set(str(error))

    def _browse_client(self):
        chosen = filedialog.askdirectory(parent=self.root, title="Choose World of Warcraft or its _classic_beta_ folder")
        if chosen:
            try:
                client = self.installer.normalize_client(Path(chosen))
                self.client_picker.configure(values=[str(client)])
                self.client.set(str(client))
                self._client_selected()
                self.addon_status.set("Ready to install the latest addon.")
            except (OSError, ValueError) as error:
                messagebox.showerror(APP_NAME, str(error), parent=self.root)

    def _detect_clients(self):
        self._start_addon_job("detect")

    def _install_addon(self):
        if not self.client.get():
            messagebox.showerror(APP_NAME, "Find or choose your Forever Beta game folder first.", parent=self.root)
            return
        self._start_addon_job("install")

    def _start_addon_job(self, action):
        if self.closing or (self.addon_thread is not None and self.addon_thread.is_alive()):
            return
        client = Path(self.client.get()) if self.client.get() else None
        self.addon_cancel.clear()
        self._addon_busy(True)
        self.addon_status.set("Looking for Forever Beta…" if action == "detect" else "Downloading the latest addon…")
        self.addon_thread = threading.Thread(target=self._addon_work, args=(action, client), daemon=False,
                                             name="ForeverTomeAddonInstaller")
        self.addon_thread.start()

    def _addon_work(self, action, client):
        try:
            if action == "detect":
                clients = self.installer.detect_clients()
                self.addon_events.put({"type": "clients", "paths": [str(path) for path in clients]})
            else:
                client  = self.installer.normalize_client(client)
                package = self.installer.latest_addon()
                if not self.addon_cancel.is_set():
                    self.addon_events.put({"type": "installing", "version": package.version})
                    target = self.installer.install_addon(package, client)
                    self.addon_events.put({"type": "installed", "version": package.version,
                                           "commit": package.commit, "target": str(target)})
        except Exception as error:
            self.addon_events.put({"type": "error", "message": str(error) or type(error).__name__})
        finally:
            self.addon_events.put({"type": "finished"})

    def _drain_addon_events(self):
        while True:
            try:
                event = self.addon_events.get_nowait()
            except queue.Empty:
                break
            kind = event["type"]
            if kind == "clients":
                paths = event["paths"]
                self.client_picker.configure(values=paths)
                if self.client.get() not in paths and len(paths) == 1:
                    self.client.set(paths[0])
                if self.client.get():
                    self._client_selected()
                self.addon_status.set("Ready to install the latest addon." if len(paths) == 1
                                      else "Choose a detected game folder." if paths
                                      else "No Forever Beta folder found. Use Browse to choose it.")
            elif kind == "installing":
                self.addon_status.set(f"Installing addon {event['version']}…")
            elif kind == "installed":
                self.addon_version.set("Installed addon version: " + event["version"])
                self.addon_status.set(f"Installed {event['version']} successfully. Reload WoW to load the update.")
                self._client_selected()
                self._log(f"Installed addon {event['version']} ({event['commit'][:8]}).")
            elif kind == "error":
                self.addon_status.set("Could not complete the request: " + event["message"])
            elif kind == "finished" and not self.closing:
                self._addon_busy(False)

    def _path_row(self, parent, label, variable, command, row):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 12, 5))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row + 1, column=0, sticky="ew")
        button = ttk.Button(parent, text="Browse…", command=command)
        button.grid(row=row + 1, column=1, padx=(10, 0))
        self.inputs.extend((entry, button))

    def _browse_source(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose the ForeverTome saved recording",
                                           filetypes=[("WoW saved recordings", "*.lua"), ("All files", "*.*")])
        if chosen:
            self.source.set(chosen)

    def _browse_output(self):
        chosen = filedialog.askdirectory(parent=self.root, title="Choose an export folder", mustexist=False)
        if chosen:
            self.output_dir.set(chosen)

    def _watch(self):
        self._begin(True)

    def _once(self):
        self._begin(False)

    def _begin(self, watch):
        if self.closing or self.controller.running:
            return
        if not self.source.get().strip() or not self.output_dir.get().strip():
            messagebox.showerror(APP_NAME, "Choose a WoW recording and an export folder first.", parent=self.root)
            return
        source = Path(self.source.get().strip()).expanduser()
        output = Path(self.output_dir.get().strip()).expanduser()
        if not source.is_file():
            messagebox.showerror(APP_NAME, "The recording file does not exist. Save in WoW, then select ForeverTome.lua in SavedVariables.", parent=self.root)
            return
        if output.exists() and not output.is_dir():
            messagebox.showerror(APP_NAME, "Choose a folder for the exported files.", parent=self.root)
            return
        self._remember()
        self.watching    = watch
        self.last_error  = None
        self.last_result = None
        self.status.set("Checking saved recording…")
        self.detail.set("You can stop at any time. An export already in progress will finish first.")
        self._set_busy(True)
        try:
            self.controller.start(source, output, watch=watch)
        except (OSError, ValueError, RuntimeError) as error:
            self.last_error = str(error)
            self._set_busy(False)
            self._show_error(str(error))

    def _remember(self):
        if self.output_dir.get().strip() and (self.source.get().strip() or self.client.get()):
            try:
                save_settings(self.source.get().strip(), Path(self.output_dir.get().strip()).expanduser(),
                              self.settings_file, client=Path(self.client.get()) if self.client.get() else None)
            except (OSError, ValueError) as error:
                self._log(f"Could not remember your folders: {error}")

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in (*self.inputs, self.watch_button, self.once_button):
            widget.configure(state=state)
        self.stop_button.configure(state="normal" if busy and not self.closing else "disabled")

    def stop(self):
        self.watching = False
        self.controller.stop()
        self.status.set("Stopping…")
        self.detail.set("Finishing the current check before stopping.")
        self.stop_button.configure(state="disabled")

    def _show_error(self, message):
        self.last_error = message
        self.status.set("Waiting to retry" if self.watching else "Export needs attention")
        self.status_label.configure(foreground=COLORS["red"])
        self.detail.set(message)
        self._log(message)

    def _drain_events(self):
        if self.closed:
            return
        self._drain_addon_events()
        while True:
            try:
                event = self.controller.events.get_nowait()
            except queue.Empty:
                break
            kind = event["type"]
            if kind == "working":
                self._log("Checking the saved recording.")
            elif kind in ("exported", "current"):
                self.last_result = event
                self.last_error  = None
                self.status_label.configure(foreground=COLORS["green"])
                self.status.set("Watching for new saves" if self.watching else "Export complete")
                self.detail.set("Save in WoW with /reload or logout. Your JSON files will update here." if self.watching
                                else "Your catalogs are ready in the export folder.")
                self.saved_at.set("WoW save: " + event.get("saved_at", "Unknown"))
                summary = event["summary"]
                self.totals.set(f"{summary['observationCount']:,} observations  ·  {summary['transactionCount']:,} transactions")
                for category, variable in self.counts.items():
                    count = event.get("categoryCounts", {}).get(category)
                    variable.set(f"{count:,}" if isinstance(count, int) else "—")
                self._log("Updated all seven catalogs." if kind == "exported" else "Catalogs already match this save.")
            elif kind == "error":
                self._show_error(event["message"])
            elif kind == "stopped" and not self.closing:
                self._set_busy(False)
                if self.last_error:
                    self.status.set("Stopped · export needs attention")
                    self.detail.set(self.last_error)
                else:
                    self.status.set("Stopped" if not self.last_result else "Catalogs up to date")
                    self.detail.set("Exporting is stopped. Start watching or export again whenever you like.")
                self._log("Exporter stopped.")
                self.watching = False
        if self.closing:
            self.status.set("Closing…")
            self.detail.set("Finishing the current operation. The app will close when it is done.")
            self.addon_status.set("Closing after the current operation finishes…")
            addon_running = self.addon_thread is not None and self.addon_thread.is_alive()
            if not self.controller.running and not addon_running:
                self.closed = True
                self.root.destroy()
                return
        self.root.after(100, self._drain_events)

    def _log(self, message):
        self.activity.configure(state="normal")
        self.activity.insert("end", datetime.now().strftime("%H:%M:%S") + "  " + message + "\n")
        if int(self.activity.index("end-1c").split(".")[0]) > 60:
            self.activity.delete("1.0", "2.0")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _open_output(self):
        if not self.output_dir.get().strip():
            return
        try:
            path = Path(self.output_dir.get().strip()).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(path))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror(APP_NAME, f"Could not open the export folder: {error}", parent=self.root)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self._remember()
        self.addon_cancel.set()
        self.controller.stop()
        self._set_busy(True)
        self._addon_busy(True)


def smoke_test(report: Path) -> int:
    result = {"ok": False}
    root   = None
    app    = None
    try:
        with tempfile.TemporaryDirectory(prefix="forevertome-app-check-") as directory:
            folder = Path(directory)
            source = folder / "ForeverTome.lua"
            raw    = b'''ForeverTomeDB = {
                schema_version = 1, synthetic = true, installation_id = "abcdef0123456789abcdef0123456789",
                next_session = 0, settings = { paused = false }, sessions = {}, record_count = 0, estimated_bytes = 0
            }'''
            source.write_bytes(raw)
            root = tk.Tk()
            root.withdraw()
            client = folder / "_classic_beta_"
            client.mkdir()
            (client / "WowB.exe").write_bytes(b"synthetic client marker")
            files = {"ForeverTome.toc": b"## Version: 0.2.3\n## SavedVariables: ForeverTomeDB\nCore.lua\nBootstrap.lua\n",
                     "Core.lua": b"-- synthetic core\n", "Bootstrap.lua": b"-- synthetic bootstrap\n",
                     "README.md": b"Synthetic package", "LICENSE": b"Synthetic package"}
            updated = dict(files)
            updated["ForeverTome.toc"] = files["ForeverTome.toc"].replace(b"0.2.3", b"9.8.7")
            updated["Core.lua"]        = b"-- updated synthetic core\n"
            packages = iter((addon_installer.AddonPackage("0.2.3", "a" * 40, files, "synthetic"),
                             addon_installer.AddonPackage("9.8.7", "b" * 40, updated, "synthetic")))

            def latest_addon():
                return next(packages)

            backend = SimpleNamespace(normalize_client=addon_installer.normalize_client,
                                      installed_version=addon_installer.installed_version,
                                      install_addon=addon_installer.install_addon,
                                      latest_addon=latest_addon)
            app = ExporterApp(root, str(source), str(folder / "exports"), folder / "settings.json",
                              discover=False, installer_backend=backend)
            app.client.set(str(client))
            deadline = time.monotonic() + 20
            state    = {"phase": "once", "failure": None}

            def poll():
                try:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Desktop smoke test timed out")
                    if app.last_error and state["phase"] not in ("error", "stopped"):
                        raise RuntimeError(app.last_error)
                    if state["phase"] == "once" and app.last_result and not app.controller.running:
                        packets = [json.loads((folder / "exports" / f"{name}.json").read_text(encoding="utf-8"))
                                   for name in CATEGORIES]
                        assert {packet["category"] for packet in packets} == set(CATEGORIES)
                        assert len({packet["exportId"] for packet in packets}) == 1
                        assert source.read_bytes() == raw
                        state["phase"] = "watch"
                        app._begin(True)
                    elif state["phase"] == "watch" and app.last_result:
                        source.write_bytes(b"ForeverTomeDB = {")
                        state["phase"] = "error"
                    elif state["phase"] == "error" and app.last_error:
                        app.stop()
                        state["phase"] = "stopped"
                    elif state["phase"] == "stopped" and not app.controller.running and app.status.get().startswith("Stopped"):
                        source.write_bytes(raw)
                        state["phase"] = "restarted"
                        app._begin(True)
                    elif state["phase"] == "restarted" and app.last_result:
                        state["phase"] = "install"
                        app._install_addon()
                    elif (state["phase"] == "install" and app.addon_status.get().startswith("Installed ")
                          and not app.addon_thread.is_alive()):
                        assert addon_installer.installed_version(client) == "0.2.3"
                        for name, content in files.items():
                            assert (client / "Interface" / "AddOns" / "ForeverTome" / name).read_bytes() == content
                        state["phase"] = "update"
                        app._install_addon()
                    elif state["phase"] == "update" and app.addon_status.get().startswith("Installed 9.8.7 "):
                        assert addon_installer.installed_version(client) == "9.8.7"
                        assert app.addon_version.get() == "Installed addon version: 9.8.7"
                        for name, content in updated.items():
                            assert (client / "Interface" / "AddOns" / "ForeverTome" / name).read_bytes() == content
                        state["phase"] = "close"
                        app.close()
                        return
                    root.after(30, poll)
                except Exception as error:
                    state["failure"] = repr(error)
                    app.close()

            root.after(0, app._once)
            root.after(30, poll)
            root.mainloop()
            if state["failure"]:
                raise RuntimeError(state["failure"])
            assert state["phase"] == "close" and app.closed and not app.controller.running
            assert app.addon_thread is not None and not app.addon_thread.is_alive()
            result = {"ok": True, "tkVersion": tk.TkVersion, "categories": list(CATEGORIES), "stopAfterError": True,
                      "addonInstall": True, "addonUpdateWithoutRebuild": True,
                      "sourceUnchanged": True, "closedWithoutWorker": True, "frozen": bool(getattr(sys, "frozen", False))}
    except Exception as error:
        result["error"] = repr(error)
        if app is not None:
            app.controller.stop()
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Initially selected SavedVariables file")
    parser.add_argument("--output-dir", type=Path, help="Initially selected export folder")
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if options.smoke_test:
        return smoke_test(options.smoke_test)
    root = tk.Tk()
    ExporterApp(root, str(options.source or ""), str(options.output_dir or ""))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
