# ForeverTome Exporter

ForeverTome Exporter is a standalone Windows application for installing the addon and converting its saved observations into category JSON files. Open it when you want to manage or export the addon, and close its window when you are finished. The packaged application includes Python and Tcl/Tk, so users do not need to install either separately.

## Install the application and addon

Run `ForeverTomeSetup.exe`. It installs the companion for the current Windows user under `%LOCALAPPDATA%\Programs\ForeverTomeExporter`, creates a Start menu shortcut, and offers an optional desktop shortcut. It does not need administrator privileges or add a startup task. You can open the companion at the end of setup. The portable `ForeverTomeExporter.exe` also runs directly without setup.

In the application's **Install / update addon** tab, choose a detected WoW Forever folder or browse to its `_classic_beta_` directory or the parent World of Warcraft folder. Click **Find game folder** to scan again. Click **Install / update addon** to download and install the addon. An internet connection is required for this action. Each click checks the latest merged commit on `main` in [Skold177/ForeverTome](https://github.com/Skold177/ForeverTome) and downloads that commit's addon. The downloaded manifest supplies the version shown in the window.

The same installed companion fetches future addon versions automatically when you click **Install / update addon**, even if its installer was built before that addon version existed. You do not need another installer for addon updates. Updating the companion's export features still requires a new companion build. Its Windows/setup version identifies that build and may stay older than an addon installed later.

The application updates ForeverTome's addon payload in the selected client's `Interface/AddOns/ForeverTome` directory. SavedVariables and other addons are preserved. After a first installation, restart WoW and enable the addon. For an update to an already enabled addon, use `/reload`.

Uninstall **ForeverTome Exporter** through Windows Settings to remove the companion and its shortcuts. Uninstalling the companion preserves the WoW addon, SavedVariables, exported catalogs, and application settings.

## Use the application

1. Open `ForeverTomeExporter.exe`.
2. In **Export recordings**, browse to your account's `SavedVariables/ForeverTome.lua` file, typically under `World of Warcraft/_classic_beta_/WTF/Account/<account>/SavedVariables/`.
3. Choose a separate output folder for the JSON files.
4. Select **Export now** for a single conversion, or **Start watching** to check for changes every two seconds while the application is open.
5. Use `/reload` or normal logout in WoW whenever you want the addon to save its observations to disk. The application cannot see observations still held in game memory.

The window shows conversion status, cumulative category counts, and errors. Observation and transaction totals describe the current save. **Open export folder** opens the destination in File Explorer. Your chosen source file and output folder are remembered locally for the next launch; opening the application does not automatically start watching.

**Stop** stops further checks. Closing the window stops watching and exits the application after any export or addon operation already in progress finishes safely. The window stays visible while it finishes. There is no tray mode, background service, or Windows startup task. Run only one exporter for each output folder, including any command-line watcher previously started there.

Exporting reads SavedVariables through the restricted data parser without executing Lua or changing the recording. Nothing is uploaded. Addon files are changed only by the explicit **Install / update addon** action. Paths and application preferences are stored in local settings; recordings are read from the file you select.

## Output files

The destination contains `spells.json`, `talents.json`, `items.json`, `quests.json`, `monsters.json`, `npcs.json`, and `gathering.json`. Each category accumulates evidence across saves, including entries, supporting records, sessions, and contexts. New evidence is merged by ID, identical observations are kept once, and conflicting content under the same observation ID is rejected. Exported history remains after the addon is cleared or the application restarts, provided you keep using the same output folder. Export successfully before clearing the addon.

`latest.json` contains the complete current save; the window's summary also describes that save. The application no longer creates dated `catalog-*.json` snapshots. On the first export with generator version 0.2.5, existing dated snapshots and `latest.json` are merged into the category history. Original snapshots remain untouched. Export once after upgrading, even if the saved recording has not changed.

JSON files use two-space indentation and line breaks for readability. Repeated checks skip unchanged saves, and incomplete saves are retried while watching. Keep backups of the category files: they retain history that may no longer exist in SavedVariables.

Each JSON file is replaced atomically. If another application reads several categories at once, it must check that their `exportId` values match. This ID and `source` describe the latest processed save; they do not identify all accumulated evidence. Unavailable game data remains unavailable; converting a recording does not supply missing item stats, enemy abilities, exact resource-node positions, or confirmed loot sources. See the [catalog format](website-catalog.md) for fields and interpretation limits.

## Run from source

For development, use Python 3.10 or newer with Tcl/Tk installed:

```powershell
py tools/exporter_app.py
```

The application uses the Python standard library. PyInstaller is needed only for packaging the executable.

## Build the Windows executable

Run on Windows from the repository root. An isolated build environment keeps packaging dependencies separate:

```powershell
py -m venv artifacts/exporter-venv
artifacts/exporter-venv/Scripts/python.exe -m pip install -r requirements-exporter-build.txt
artifacts/exporter-venv/Scripts/python.exe tools/package_exporter.py
```

The build produces `dist/exporter/ForeverTomeExporter.exe`, with an adjacent `LICENSE`, short `README.txt`, and `VERSION`. The release version comes from `ForeverTome/ForeverTome.toc` and is embedded in the executable's Windows file/product metadata and written to `VERSION`. It packages application code and its dependencies, without personal settings, SavedVariables, or generated catalogs. The command builds the application without installing or starting it for normal use. Its build files stay under the ignored `artifacts/exporter-build/` directory. Use `--output-dir <folder>` to choose another distribution folder.

After packaging, the command automatically runs the executable's smoke test, checking Tcl/Tk and catalog conversion, and requires a successful JSON report at `artifacts/exporter-build/smoke-test.json`. This test exits automatically and does not change game data. To run it separately:

```powershell
dist/exporter/ForeverTomeExporter.exe --smoke-test artifacts/exporter-build/manual-smoke-test.json
```

The addon ZIP remains a separate build through `tools/package.py`.

## Build the Windows installer

Build the application executable first, then use the existing Inno Setup 6 compiler to wrap that bundle:

```powershell
py tools/package_installer.py
```

The command produces `dist/installer/ForeverTomeSetup.exe` without running the installer. It finds `ISCC.exe` on `PATH` or in the usual Inno Setup 6 installation folders. For an existing compiler in another location, use `--compiler 'C:\BuildTools\Inno Setup 6\ISCC.exe'`. Use `--bundle-dir` and `--output-dir` to select other input and output folders.

The installer script is `installer/ForeverTomeExporter.iss`. It reads the application version from the selected bundle's `VERSION`, so setup and its executable retain the same version even when packaging an older bundle. A fresh build uses the TOC's release version for the addon, ZIP filename, Windows executable, and setup. Release tags should use `v` followed by that same version. It installs the executable, license, short readme, and version file. Addon discovery and installation run in the visible application after setup, when the user selects **Install / update addon**. No user settings, recordings, or generated catalogs are included in the setup payload.

The reference compiler is **Inno Setup 6.7.3**, available from the [official download page](https://jrsoftware.org/isdl.php). Compiler setup is a separate developer prerequisite, not an action performed by this repository's build tools. Its per-user installer configuration follows Inno Setup's [privilege settings](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm); the uninstall script deliberately has no additional file-deletion rules.
