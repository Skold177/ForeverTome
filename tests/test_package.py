import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_addon", ROOT / "tools" / "package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_distribution_contains_only_runtime_and_documentation(self):
        files    = package.addon_files()
        expected = {"ForeverTome.toc", "Core.lua", "Compatibility.lua", "Quests.lua", "Loot.lua", "World.lua", "Bootstrap.lua", "README.md", "LICENSE"}
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


if __name__ == "__main__":
    unittest.main()
