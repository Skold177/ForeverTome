"""Build and smoke-test the standalone Windows catalog exporter."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

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
commit of Skold177/ForeverTome, not unpublished work or a tagged release.
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

Outputs: spells.json, talents.json, items.json, quests.json, monsters.json,
npcs.json, gathering.json, latest.json, and dated full snapshots.
The application reads SavedVariables without modifying or executing it.
Nothing is uploaded. Use only one exporter for each output folder.

Source and documentation: https://github.com/Skold177/ForeverTome
License: GNU General Public License version 2; see the adjacent LICENSE.
"""


def build(output_dir: Path) -> Path:
    if sys.platform != "win32":
        raise ValueError("Build the Windows exporter on Windows")
    output_dir = output_dir.resolve()
    build_dir  = ROOT / "artifacts" / "exporter-build"
    entry      = ROOT / "tools" / "exporter_app.py"
    if not entry.is_file():
        raise ValueError("Missing exporter application entry point")
    output_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", APP_NAME,
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
