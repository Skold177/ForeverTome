"""Find a Forever beta client and install a verified addon payload from merged main."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import string
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.desktop_exporter import load_settings


REPOSITORY       = "Skold177/ForeverTome"
API_URL          = f"https://api.github.com/repos/{REPOSITORY}/commits/main"
MAX_DOWNLOAD     = 32 * 1024 * 1024
MAX_ARCHIVE      = 128 * 1024 * 1024
MAX_PAYLOAD_FILE = 4 * 1024 * 1024
MAX_PAYLOAD      = 16 * 1024 * 1024
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?"


class InstallError(ValueError):
    pass


@dataclass(frozen=True)
class AddonPackage:
    version: str
    commit: str
    files: dict[str, bytes]
    source_url: str


def _reject_reparse(path: Path) -> None:
    for part in reversed((path, *path.parents)):
        try:
            status = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(status.st_mode) or getattr(status, "st_file_attributes", 0) & 0x400:
            raise InstallError(f"Select a client without symbolic links or junctions: {part}")


def normalize_client(path: Path) -> Path:
    candidate = Path(os.path.abspath(path))
    if candidate.name.casefold() != "_classic_beta_":
        candidate = candidate / "_classic_beta_"
    _reject_reparse(candidate)
    if not candidate.is_dir():
        raise InstallError("Select the WoW Forever _classic_beta_ folder or its World of Warcraft parent")
    for executable in ("WowB.exe", "Wow.exe"):
        binary = candidate / executable
        _reject_reparse(binary)
        if binary.is_file():
            return candidate.resolve(strict=True)
    raise InstallError("The _classic_beta_ folder must contain WowB.exe or Wow.exe")


def _registry_paths() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    paths = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for product in ("World of Warcraft", "World of Warcraft Beta"):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Blizzard Entertainment\{product}",
                                        0, winreg.KEY_READ | view) as key:
                        for name in ("InstallPath", "InstallLocation", "ProgramPath"):
                            try:
                                value, kind = winreg.QueryValueEx(key, name)
                                if isinstance(value, str) and value:
                                    path = Path(os.path.expandvars(value.strip('"')))
                                    paths.append(path.parent if path.suffix.casefold() == ".exe" else path)
                            except OSError:
                                continue
                except OSError:
                    continue
    return paths


def _candidate_paths() -> list[Path]:
    paths       = _registry_paths()
    preferences = load_settings()
    if preferences.get("client"):
        paths.append(Path(preferences["client"]))
    if preferences.get("source"):
        source = Path(preferences["source"])
        paths.extend(parent for parent in list(source.parents)[:12]
                     if parent.name.casefold() == "_classic_beta_")
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        if os.environ.get(name):
            paths.append(Path(os.environ[name]) / "World of Warcraft")
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            if root.exists():
                paths.extend((root / "World of Warcraft", root / "Games" / "World of Warcraft",
                              root / "Blizzard" / "World of Warcraft"))
    return paths


def detect_clients() -> list[Path]:
    found = {}
    for candidate in _candidate_paths():
        try:
            client = normalize_client(candidate)
            found[str(client).casefold()] = client
        except (OSError, ValueError):
            continue
    return sorted(found.values(), key=lambda value: str(value).casefold())


def _version(manifest: str) -> str:
    versions = re.findall(r"(?m)^## Version:[ \t]*(\S+)[ \t]*$", manifest)
    if len(versions) != 1 or len(versions[0]) > 64 or not re.fullmatch(VERSION_PATTERN, versions[0]):
        raise InstallError("The addon manifest has an invalid version")
    return versions[0]


def installed_version(client: Path) -> str | None:
    target = normalize_client(client) / "Interface" / "AddOns" / "ForeverTome" / "ForeverTome.toc"
    _reject_reparse(target)
    if not target.is_file():
        return None
    if target.stat().st_size > 65536:
        return None
    try:
        return _version(target.read_text(encoding="utf-8-sig"))
    except (UnicodeError, InstallError):
        return None


def _manifest(content: bytes) -> tuple[str, list[str]]:
    if len(content) > 65536:
        raise InstallError("The addon manifest is too large")
    try:
        manifest = content.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as error:
        raise InstallError("The addon manifest must be UTF-8") from error
    declarations = re.findall(r"(?m)^## SavedVariables:[ \t]*(.*)$", manifest)
    if declarations != ["ForeverTomeDB"] or re.search(r"(?m)^## SavedVariablesPerCharacter:", manifest):
        raise InstallError("The addon manifest must declare only ForeverTomeDB SavedVariables")
    paths = [line.strip() for line in manifest.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not paths or len(paths) != len({name.casefold() for name in paths}):
        raise InstallError("The addon load list is empty or duplicated")
    if any(not re.fullmatch(r"[A-Za-z0-9_]+\.lua", name) for name in paths):
        raise InstallError("The addon manifest contains an unsafe runtime path")
    if not {"Core.lua", "Bootstrap.lua"}.issubset(paths):
        raise InstallError("The addon is missing its core runtime files")
    return _version(manifest), paths


def _download(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": "ForeverTomeExporter", "Accept": "application/vnd.github+json" if url == API_URL else "application/zip",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.geturl().startswith("https://"):
            raise InstallError("The addon download did not remain on HTTPS")
        content = response.read(limit + 1)
    if len(content) > limit:
        raise InstallError("The addon download exceeds its size limit")
    return content


def _package_from_archive(content: bytes, commit: str, source_url: str) -> AddonPackage:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise InstallError("GitHub returned an invalid commit identifier")
    if len(content) > MAX_DOWNLOAD:
        raise InstallError("The addon archive is too large")
    prefix = f"ForeverTome-{commit}/"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(entry.file_size for entry in entries) > MAX_ARCHIVE:
                raise InstallError("The addon archive exceeds its unpacked size limit")
            names = set()
            for entry in entries:
                name  = entry.filename.rstrip("/")
                if (not name or "\\" in name or ":" in name or "\x00" in name
                        or "\x00" in entry.orig_filename or "\\" in entry.orig_filename
                        or any(part in ("", ".", "..") for part in name.split("/"))
                        or PurePosixPath(name).is_absolute() or not entry.filename.startswith(prefix)):
                    raise InstallError("The addon archive contains an unsafe path")
                if name.casefold() in names:
                    raise InstallError("The addon archive contains duplicate paths")
                names.add(name.casefold())
                mode = entry.external_attr >> 16
                if (stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or entry.external_attr & 0x400):
                    raise InstallError("The addon archive contains a symbolic link or special file")
            if archive.getinfo(prefix + "ForeverTome/ForeverTome.toc").file_size > 65536:
                raise InstallError("The addon manifest is too large")
            manifest       = archive.read(prefix + "ForeverTome/ForeverTome.toc")
            version, paths = _manifest(manifest)
            files          = {"ForeverTome.toc": manifest}
            sources        = {name: prefix + "ForeverTome/" + name for name in paths}
            sources.update({"README.md": prefix + "README.md", "LICENSE": prefix + "LICENSE"})
            for name, source in sources.items():
                if archive.getinfo(source).file_size > MAX_PAYLOAD_FILE:
                    raise InstallError(f"The addon file {name} is too large")
                files[name] = archive.read(source)
            if sum(map(len, files.values())) > MAX_PAYLOAD:
                raise InstallError("The addon payload is too large")
    except (zipfile.BadZipFile, KeyError, RuntimeError, EOFError) as error:
        raise InstallError("The download is not a complete, readable addon archive") from error
    return AddonPackage(version, commit, files, source_url)


def latest_addon() -> AddonPackage:
    try:
        response = json.loads(_download(API_URL, 1024 * 1024))
    except (ValueError, UnicodeError) as error:
        raise InstallError("GitHub did not return a valid main commit") from error
    commit = response.get("sha") if isinstance(response, dict) else None
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise InstallError("GitHub returned an invalid main commit identifier")
    archive_url = f"https://codeload.github.com/{REPOSITORY}/zip/{commit}"
    source_url  = f"https://github.com/{REPOSITORY}/tree/{commit}"
    return _package_from_archive(_download(archive_url, MAX_DOWNLOAD), commit, source_url)


def _validate_package(package: AddonPackage) -> None:
    if not isinstance(package.files, dict) or "ForeverTome.toc" not in package.files:
        raise InstallError("The addon package is missing its manifest")
    if any(not isinstance(content, bytes) or len(content) > MAX_PAYLOAD_FILE for content in package.files.values()):
        raise InstallError("The addon package contains an invalid or oversized file")
    version, paths = _manifest(package.files["ForeverTome.toc"])
    if version != package.version or set(package.files) != {"ForeverTome.toc", "README.md", "LICENSE", *paths}:
        raise InstallError("The addon package does not match its manifest")
    if sum(map(len, package.files.values())) > MAX_PAYLOAD:
        raise InstallError("The addon package is too large")


def _remove_stage(stage: Path, parent: Path) -> None:
    _reject_reparse(stage)
    if stage.resolve().parent != parent.resolve() or not stage.name.startswith(".ForeverTome-install-"):
        raise InstallError("The installer staging path is outside its expected directory")
    shutil.rmtree(stage)


def install_addon(package: AddonPackage, client: Path) -> Path:
    _validate_package(package)
    client = normalize_client(client)
    parent = client / "Interface" / "AddOns"
    target = parent / "ForeverTome"
    _reject_reparse(target)
    for name in package.files:
        _reject_reparse(target / name)
    parent.mkdir(parents=True, exist_ok=True)
    stage      = Path(tempfile.mkdtemp(prefix=".ForeverTome-install-", dir=parent))
    payload    = stage / "new"
    backup     = stage / "previous"
    replaced   = []
    originals  = set()
    keep_stage = False
    try:
        payload.mkdir()
        backup.mkdir()
        for name, content in package.files.items():
            with (payload / name).open("wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            destination = target / name
            if destination.exists():
                if not destination.is_file() or destination.stat().st_size > MAX_PAYLOAD_FILE:
                    raise InstallError(f"The existing addon file {name} cannot be safely replaced")
                shutil.copy2(destination, backup / name)
                originals.add(name)
        target.mkdir(exist_ok=True)
        try:
            for name in sorted(package.files, key=lambda value: (value == "ForeverTome.toc", value)):
                destination = target / name
                _reject_reparse(destination)
                replaced.append(name)
                os.replace(payload / name, destination)
        except (OSError, InstallError) as error:
            failures = []
            for name in reversed(replaced):
                try:
                    destination = target / name
                    _reject_reparse(destination)
                    if name in originals:
                        os.replace(backup / name, destination)
                    else:
                        destination.unlink(missing_ok=True)
                except (OSError, InstallError) as rollback_error:
                    failures.append(str(rollback_error))
            if failures:
                keep_stage = True
                raise InstallError(f"Installation failed and could not fully restore the addon; backups remain in {backup}") from error
            raise InstallError("Installation failed; the previous addon files were restored") from error
    finally:
        if not keep_stage:
            _remove_stage(stage, parent)
    return target
