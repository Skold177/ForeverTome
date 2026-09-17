"""Build the per-user Windows setup executable from an existing application bundle."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_compiler(explicit: Path | None = None) -> Path:
    if explicit is not None:
        compiler = explicit.resolve()
        if not compiler.is_file():
            raise ValueError(f"Inno Setup compiler does not exist: {compiler}")
        return compiler
    candidates = []
    on_path    = shutil.which("ISCC.exe")
    if on_path:
        candidates.append(Path(on_path))
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            folder = Path(base) / "Programs" if variable == "LOCALAPPDATA" else Path(base)
            candidates.append(folder / "Inno Setup 6" / "ISCC.exe")
    for compiler in candidates:
        if compiler.is_file():
            return compiler.resolve()
    raise ValueError("Inno Setup 6 compiler not found; install it from jrsoftware.org/isdl.php or use --compiler ISCC.exe")


def build(bundle_dir: Path, output_dir: Path, compiler: Path | None = None) -> Path:
    if sys.platform != "win32":
        raise ValueError("Build the Windows installer on Windows")
    bundle_dir = bundle_dir.resolve()
    output_dir = output_dir.resolve()
    for name in ("ForeverTomeExporter.exe", "LICENSE", "README.txt"):
        source = bundle_dir / name
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(f"Missing application bundle file: {source}; run tools/package_exporter.py first")
    compiler = find_compiler(compiler)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(compiler), f"/DBundleDir={bundle_dir}", f"/O{output_dir}",
        str(ROOT / "installer" / "ForeverTomeExporter.iss"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    installer = output_dir / "ForeverTomeSetup.exe"
    if not installer.is_file() or installer.stat().st_size == 0:
        raise ValueError("Inno Setup did not produce the expected installer")
    return installer


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / "dist" / "exporter")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "installer")
    parser.add_argument("--compiler", type=Path, help="Path to an existing Inno Setup ISCC.exe")
    options = parser.parse_args(arguments)
    try:
        installer = build(options.bundle_dir, options.output_dir, options.compiler)
        print(f"Built {installer}")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Installer packaging failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
