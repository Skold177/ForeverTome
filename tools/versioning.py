"""Read the release version shared by addon and desktop distribution builds."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_version(version: str) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError("Release version must be MAJOR.MINOR.PATCH")
    if any(int(part) > 65535 for part in version.split(".")):
        raise ValueError("Release version components must fit Windows version metadata")
    return version


def manifest_version(manifest: str) -> str:
    versions = re.findall(r"(?m)^## Version:[ \t]*([^\r\n]*)", manifest)
    if len(versions) != 1:
        raise ValueError("Addon manifest must declare exactly one release version")
    return validate_version(versions[0].strip())


def addon_version(root: Path | None = None) -> str:
    source   = ROOT if root is None else root
    manifest = source / "ForeverTome" / "ForeverTome.toc"
    return manifest_version(manifest.read_text(encoding="utf-8-sig"))
