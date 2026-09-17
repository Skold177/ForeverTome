"""Build the addon ZIP and optionally copy its files into a selected local client."""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def addon_files(interface: int | None = None) -> dict[str, bytes]:
    source   = ROOT / "ForeverTome"
    manifest = (source / "ForeverTome.toc").read_text(encoding="utf-8")
    if interface is not None:
        if interface < 1 or interface > 999999:
            raise ValueError("Interface must be the positive number reported by GetBuildInfo()")
        manifest = re.sub(r"(?m)^## Interface: .*", f"## Interface: {interface}", manifest)
    paths = [line.strip() for line in manifest.splitlines() if line.strip() and not line.startswith("#")]
    if len(paths) != len(set(paths)) or not paths:
        raise ValueError("Manifest load list is empty or duplicated")
    if "## SavedVariables: ForeverTomeDB" not in manifest:
        raise ValueError("Missing SavedVariables declaration")
    files = {"ForeverTome.toc": manifest.encode("utf-8")}
    for name in paths:
        path = source / name
        if not re.fullmatch(r"[A-Za-z0-9_]+\.lua", name) or path.resolve().parent != source.resolve():
            raise ValueError("Unsafe manifest path")
        files[name] = path.read_bytes()
    files["README.md"] = (ROOT / "README.md").read_bytes()
    files["LICENSE"]   = (ROOT / "LICENSE").read_bytes()
    return files


def write_zip(files: dict[str, bytes], destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry               = zipfile.ZipInfo("ForeverTome/" + name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)


def install(files: dict[str, bytes], client: Path) -> Path:
    client = client.resolve(strict=True)
    if not any((client / name).is_file() for name in ("WowB.exe", "Wow.exe")):
        raise ValueError("Select the product directory containing WowB.exe or Wow.exe")
    target = (client / "Interface" / "AddOns" / "ForeverTome").resolve()
    if not target.is_relative_to(client):
        raise ValueError("Resolved addon destination leaves the selected client")
    for name in files:
        if not (target / name).resolve().is_relative_to(target):
            raise ValueError("Resolved addon file leaves the addon directory")
    target.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        destination = target / name
        if destination.exists() and destination.read_bytes() == data:
            continue
        destination.write_bytes(data)
    return target


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "ForeverTome-0.2.3.zip")
    parser.add_argument("--install", type=Path, metavar="CLIENT", help="Product directory containing the executable")
    parser.add_argument("--interface", type=int, help="Override the provisional TOC with the measured interface version")
    options = parser.parse_args(arguments)
    try:
        files = addon_files(options.interface)
        write_zip(files, options.output)
        print(f"Built {options.output}")
        if options.install:
            print(f"Installed {install(files, options.install)}")
        return 0
    except (OSError, ValueError) as error:
        print(f"Packaging failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
