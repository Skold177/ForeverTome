"""Build and smoke-test the standalone Windows catalog exporter."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.versioning import addon_version, validate_version

ROOT     = Path(__file__).resolve().parents[1]
APP_NAME = "ForeverTomeExporter"

APP_README = """ForeverTome Exporter

Open ForeverTomeExporter.exe to install/update the addon and convert saved data.
No Python installation is needed to run this application.

1. In Install / update addon, select your detected WoW Forever folder or browse.
2. Click Install / update addon to download the latest merged addon from GitHub.
3. In Export recordings, select SavedVariables/ForeverTome.lua and an output folder.
4. Click Export now for one conversion, or Start watching while playing.
5. Use /reload or log out normally in WoW to save new observations.

Installing or updating needs an internet connection. It uses the latest merged main
commit of Skold177/ForeverTome each time you click Install / update addon.
Keep this application to fetch future addon updates; no replacement installer is
needed for addon updates. The setup and application version identify the companion
build, while the installed addon version comes from the downloaded addon.
Use exporter 0.3.0 or newer to export the additional observation types recorded by
addon 0.3.0. Older companions can still install the latest addon, but their older
parsers cannot export its new observation types. Exporter feature updates require
an updated companion build.
It updates ForeverTome addon files and preserves SavedVariables and other addons.
Restart WoW after a first installation; reload after updating an enabled addon.

Stop pauses automatic conversion. Close the window to exit; any
export or addon operation already in progress finishes safely before it closes.
It does not run in the system tray or start automatically with Windows.
Your selected folders are remembered locally for the next launch.

ForeverTomeSetup.exe installs this companion for your Windows user and creates
a Start menu shortcut, with an optional desktop shortcut. Addon installation
still uses the application's Install / update addon button. Uninstalling the companion
preserves the WoW addon, recordings, exported JSON, and application settings.

Outputs (16 files): spells.json, talents.json, items.json, quests.json,
creatures.json, monsters.json, npcs.json, gathering.json, recipes.json, maps.json,
professions.json, currencies.json, objects.json, history.json, database.json,
and latest.json. Categories accumulate evidence by ID across saves.
creatures.json uses canonical creature identities; npcs.json is an alias and
monsters.json is an observed-reaction subset. Import their shared keys once.
The window shows 11 canonical category counts without duplicate creature totals.

history.json preserves every available observation and session diagnostic before
the other cumulative files are generated. database.json provides canonical
catalogs, relationships, coverage, and loot evidence from the retained history.
Deleted category files and database.json can be rebuilt from history.json.
These files retain exported evidence after addon clearing or app restarts.
Export successfully before clearing the addon, and keep the same output folder.
latest.json describes the current save. The window separates current-save totals
from retained observations and sessions, and shows recorded gaps and scan counts.
Overall game database completeness remains unknown.

No new dated snapshots are created. Existing snapshots, latest.json, and category
evidence are imported into the archive without changing original snapshots.
Migration records its available sources; previously discarded data cannot be recovered.
Keep backups of the export folder, especially history.json. Readers of multiple
cumulative files must require matching exportId and historyId values.
The application reads SavedVariables without modifying or executing it.
Nothing is uploaded. Use only one exporter for each output folder.

Source and documentation: https://github.com/Skold177/ForeverTome
License: GNU General Public License version 2; see the adjacent LICENSE.
"""


def windows_version_info(version: str) -> str:
    version = validate_version(version)
    parts   = tuple(int(part) for part in version.split(".")) + (0,)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={parts!r}, prodvers={parts!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'ForeverTome'),
      StringStruct('FileDescription', 'ForeverTome Exporter'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('ProductName', 'ForeverTome Exporter'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""


def build(output_dir: Path) -> Path:
    if sys.platform != "win32":
        raise ValueError("Build the Windows exporter on Windows")
    output_dir   = output_dir.resolve()
    build_dir    = ROOT / "artifacts" / "exporter-build"
    entry        = ROOT / "tools" / "exporter_app.py"
    version      = addon_version(ROOT)
    version_file = build_dir / "windows-version.txt"
    if not entry.is_file():
        raise ValueError("Missing exporter application entry point")
    output_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    version_file.write_text(windows_version_info(version), encoding="utf-8")
    (output_dir / "VERSION").unlink(missing_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", APP_NAME,
        "--version-file", str(version_file),
        "--paths", str(ROOT),
        "--distpath", str(output_dir),
        "--workpath", str(build_dir / "work"),
        "--specpath", str(build_dir),
        str(entry),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    executable = output_dir / f"{APP_NAME}.exe"
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ValueError("PyInstaller did not produce the expected executable")
    report = build_dir / "smoke-test.json"
    report.unlink(missing_ok=True)
    subprocess.run([str(executable), "--smoke-test", str(report)], cwd=ROOT, check=True, timeout=120)
    result = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("Packaged exporter failed its smoke test")
    shutil.copyfile(ROOT / "LICENSE", output_dir / "LICENSE")
    (output_dir / "README.txt").write_text(APP_README, encoding="utf-8")
    (output_dir / "VERSION").write_text(version + "\n", encoding="utf-8")
    return executable


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "exporter")
    options = parser.parse_args(arguments)
    try:
        executable = build(options.output_dir)
        print(f"Built and verified {executable}")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Exporter packaging failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
