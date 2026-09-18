import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_exporter, package_installer, versioning

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_addon", ROOT / "tools" / "package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_distribution_contains_only_runtime_and_documentation(self):
        files    = package.addon_files()
        expected = {"ForeverTome.toc", "Core.lua", "Compatibility.lua", "Quests.lua", "Loot.lua", "Spells.lua", "Talents.lua", "World.lua", "Bootstrap.lua", "README.md", "LICENSE"}
        self.assertEqual(set(files), expected)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "addon.zip"
            package.write_zip(files, destination)
            first = destination.read_bytes()
            package.write_zip(files, destination)
            self.assertEqual(destination.read_bytes(), first)
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(set(archive.namelist()), {"ForeverTome/" + name for name in expected})
                for name, data in files.items():
                    self.assertEqual(archive.read("ForeverTome/" + name), data)

    def test_install_updates_only_addon_files_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory)
            (client / "WowB.exe").write_bytes(b"test executable placeholder")
            sentinel = client / "WTF" / "SavedVariables" / "ForeverTome.lua"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b"existing saved observations")
            files  = package.addon_files(16002)
            target = package.install(files, client)
            self.assertTrue(target.samefile(client / "Interface" / "AddOns" / "ForeverTome"))
            self.assertEqual(target, client.resolve() / "Interface" / "AddOns" / "ForeverTome")
            self.assertIn(b"## Interface: 16002", (target / "ForeverTome.toc").read_bytes())
            self.assertEqual(sentinel.read_bytes(), b"existing saved observations")
            self.assertEqual(package.install(files, client), target)

    def test_invalid_client_or_interface_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                package.install(package.addon_files(), Path(directory))
        with self.assertRaises(ValueError):
            package.addon_files(0)

    def test_default_zip_name_tracks_the_packaged_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root  = Path(directory)
            files = package.addon_files()
            files["ForeverTome.toc"] = b"## Version: 4.5.6\n"
            with patch.object(package, "ROOT", root), patch.object(package, "addon_files", return_value=files):
                self.assertEqual(package.main([]), 0)
            destination = root / "dist" / "ForeverTome-4.5.6.zip"
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.read("ForeverTome/ForeverTome.toc"), files["ForeverTome.toc"])

    def test_release_version_requires_one_windows_compatible_manifest_version(self):
        self.assertEqual(versioning.manifest_version("## Version: 1.23.456\r\n"), "1.23.456")
        invalid = ("", "## Version: 0.2.6\n## Version: 0.2.7\n", "## Version: 01.2.3\n",
                   "## Version: 1.2.3-beta\n", "## Version: 65536.0.0\n", "## Version: 1.2.3 extra\n")
        for manifest in invalid:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                versioning.manifest_version(manifest)

    def test_exporter_build_stamps_the_manifest_version_into_its_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root       = Path(directory)
            output     = root / "bundle"
            source     = root / "ForeverTome"
            entry      = root / "tools" / "exporter_app.py"
            executable = output / "ForeverTomeExporter.exe"
            source.mkdir()
            entry.parent.mkdir()
            (source / "ForeverTome.toc").write_text("## Version: 4.5.6\n", encoding="utf-8")
            (root / "LICENSE").write_text("test license", encoding="utf-8")
            entry.write_text("", encoding="utf-8")

            def run(command, **kwargs):
                if "--version-file" in command:
                    resource = Path(command[command.index("--version-file") + 1]).read_text(encoding="utf-8")
                    self.assertIn("filevers=(4, 5, 6, 0), prodvers=(4, 5, 6, 0)", resource)
                    self.assertIn("StringStruct('FileVersion', '4.5.6')", resource)
                    self.assertIn("StringStruct('ProductVersion', '4.5.6')", resource)
                    executable.write_bytes(b"test executable")
                else:
                    self.assertEqual(command[:2], [str(executable), "--smoke-test"])
                    Path(command[2]).write_text(json.dumps({"ok": True}), encoding="utf-8")

            with patch.object(package_exporter, "ROOT", root), patch.object(package_exporter.sys, "platform", "win32"), \
                    patch.object(package_exporter.subprocess, "run", side_effect=run):
                self.assertEqual(package_exporter.build(output), executable)
            self.assertEqual((output / "VERSION").read_text(encoding="utf-8"), "4.5.6\n")
            self.assertEqual((output / "LICENSE").read_text(encoding="utf-8"), "test license")

    def test_failed_exporter_rebuild_does_not_leave_a_valid_bundle_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root   = Path(directory)
            output = root / "bundle"
            entry  = root / "tools" / "exporter_app.py"
            source = root / "ForeverTome"
            source.mkdir()
            entry.parent.mkdir()
            output.mkdir()
            entry.write_text("", encoding="utf-8")
            (source / "ForeverTome.toc").write_text("## Version: 4.5.6\n", encoding="utf-8")
            (output / "VERSION").write_text("0.1.2\n", encoding="utf-8")
            with patch.object(package_exporter, "ROOT", root), patch.object(package_exporter.sys, "platform", "win32"), \
                    patch.object(package_exporter.subprocess, "run", side_effect=OSError("build failed")):
                with self.assertRaisesRegex(OSError, "build failed"):
                    package_exporter.build(output)
            self.assertFalse((output / "VERSION").exists())

    def test_installer_uses_the_selected_bundles_version_and_rejects_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root       = Path(directory)
            bundle     = root / "bundle"
            output     = root / "setup"
            compiler   = root / "ISCC.exe"
            version    = bundle / "VERSION"
            executable = output / "ForeverTomeSetup.exe"
            bundle.mkdir()
            for name in ("ForeverTomeExporter.exe", "LICENSE", "README.txt"):
                (bundle / name).write_bytes(b"test bundle file")
            compiler.write_bytes(b"test compiler")
            version.write_text("1.2.3\n", encoding="utf-8")

            def run(command, **kwargs):
                self.assertIn(f"/DBundleDir={bundle}", command)
                self.assertEqual(version.read_text(encoding="utf-8"), "1.2.3\n")
                executable.write_bytes(b"test setup")

            with patch.object(package_installer.sys, "platform", "win32"), \
                    patch.object(package_installer.subprocess, "run", side_effect=run) as build:
                self.assertEqual(package_installer.build(bundle, output, compiler), executable)
                version.write_text("invalid\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    package_installer.build(bundle, output, compiler)
                version.unlink()
                with self.assertRaisesRegex(ValueError, "Missing application bundle file"):
                    package_installer.build(bundle, output, compiler)
            self.assertEqual(build.call_count, 1)


if __name__ == "__main__":
    unittest.main()
