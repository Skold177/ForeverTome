import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import addon_installer as installer
from tools import desktop_exporter as desktop


COMMIT   = "a" * 40
MANIFEST = b"## Interface: 16001\n## Version: 0.2.3\n## SavedVariables: ForeverTomeDB\n\nCore.lua\nBootstrap.lua\n"


def make_archive(extra=None, manifest=MANIFEST):
    prefix  = f"ForeverTome-{COMMIT}/"
    content = io.BytesIO()
    files   = {
        prefix: b"", prefix + "ForeverTome/ForeverTome.toc": manifest,
        prefix + "ForeverTome/Core.lua": b"local addon = {}\n",
        prefix + "ForeverTome/Bootstrap.lua": b"return true\n",
        prefix + "README.md": b"Addon instructions\n", prefix + "LICENSE": b"MIT\n",
        prefix + "tests/unrelated.lua": b"Must never be installed\n",
    }
    with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        for name, data in extra or []:
            archive.writestr(name, data)
    return content.getvalue()


class AddonInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root      = Path(self.temporary.name)
        self.client    = self.root / "World of Warcraft" / "_classic_beta_"
        self.client.mkdir(parents=True)
        (self.client / "WowB.exe").write_bytes(b"synthetic executable")
        self.package = installer._package_from_archive(make_archive(), COMMIT, "https://github.com/test/commit")
        self.target  = self.client / "Interface" / "AddOns" / "ForeverTome"
        self.addCleanup(self.temporary.cleanup)

    def test_normalizes_parent_or_beta_and_rejects_retail_and_missing_executable(self):
        self.assertEqual(installer.normalize_client(self.client), self.client.resolve())
        self.assertEqual(installer.normalize_client(self.client.parent), self.client.resolve())
        retail = self.client.parent / "_retail_"
        retail.mkdir()
        (retail / "Wow.exe").write_bytes(b"retail")
        with self.assertRaises(installer.InstallError):
            installer.normalize_client(retail)
        (self.client / "WowB.exe").unlink()
        with self.assertRaisesRegex(installer.InstallError, "must contain"):
            installer.normalize_client(self.client)

    def test_discovery_deduplicates_valid_clients_and_ignores_unrelated_locations(self):
        candidates = [self.client.parent, self.client, self.root / "missing", self.client / "WTF"]
        with patch.object(installer, "_candidate_paths", return_value=candidates):
            self.assertEqual(installer.detect_clients(), [self.client.resolve()])

    def test_candidates_include_preferences_source_ancestors_program_files_and_registry(self):
        source    = self.client / "WTF" / "Account" / "test" / "SavedVariables" / "ForeverTome.lua"
        preferred = self.root / "OtherClient" / "_classic_beta_"
        registry  = self.root / "RegistryClient"
        with patch.object(installer, "_registry_paths", return_value=[registry]), \
                patch.object(installer, "load_settings", return_value={"source": str(source), "client": str(preferred)}), \
                patch.dict(os.environ, {"ProgramFiles": str(self.root)}):
            candidates = installer._candidate_paths()
        self.assertIn(self.client, candidates)
        self.assertIn(preferred, candidates)
        self.assertIn(registry, candidates)
        self.assertIn(self.root / "World of Warcraft", candidates)

    def test_latest_download_is_pinned_to_validated_main_commit_and_whitelists_payload(self):
        with patch.object(installer, "_download", side_effect=[json.dumps({"sha": COMMIT}).encode(), make_archive()]) as download:
            package = installer.latest_addon()
        self.assertEqual(package.version, "0.2.3")
        self.assertEqual(package.commit, COMMIT)
        self.assertEqual(set(package.files), {"ForeverTome.toc", "Core.lua", "Bootstrap.lua", "README.md", "LICENSE"})
        self.assertEqual(download.call_args_list[0].args[0], installer.API_URL)
        self.assertEqual(download.call_args_list[1].args[0], f"https://codeload.github.com/Skold177/ForeverTome/zip/{COMMIT}")
        self.assertEqual(package.source_url, f"https://github.com/Skold177/ForeverTome/tree/{COMMIT}")

    def test_latest_rejects_invalid_api_and_commit_before_archive_download(self):
        for data in (b"not JSON", b"[]", b'{"sha":"../../bad"}', b'{"sha":true}'):
            with self.subTest(data=data), patch.object(installer, "_download", return_value=data) as download:
                with self.assertRaises(installer.InstallError):
                    installer.latest_addon()
                self.assertEqual(download.call_count, 1)

    def test_download_uses_timeout_https_and_size_cap(self):
        response = MagicMock()
        response.geturl.return_value = "https://codeload.github.com/archive.zip"
        response.read.return_value   = b"12345"
        context  = MagicMock()
        context.__enter__.return_value = response
        with patch.object(installer.urllib.request, "urlopen", return_value=context) as request:
            with self.assertRaisesRegex(installer.InstallError, "size limit"):
                installer._download("https://codeload.github.com/archive.zip", 4)
            self.assertEqual(request.call_args.kwargs["timeout"], 30)
            response.read.assert_called_once_with(5)
            response.geturl.return_value = "http://codeload.github.com/archive.zip"
            with self.assertRaisesRegex(installer.InstallError, "HTTPS"):
                installer._download("https://codeload.github.com/archive.zip", 10)

    def test_archive_rejects_traversal_duplicate_case_and_foreign_root(self):
        prefix = f"ForeverTome-{COMMIT}/"
        for path in (prefix + "../outside.lua", prefix + "tests\\outside.lua", prefix + "C:/outside.lua",
                     prefix + "forevertome/core.lua", "DifferentRepository/file.txt"):
            with self.subTest(path=path), self.assertRaises(installer.InstallError):
                content = make_archive([(path.replace("\\", "/"), b"bad")])
                content = content.replace(path.replace("\\", "/").encode(), path.encode())
                installer._package_from_archive(content, COMMIT, "https://example.com")

    def test_archive_rejects_symlinks_corrupt_zip_and_oversized_payload(self):
        link               = zipfile.ZipInfo(f"ForeverTome-{COMMIT}/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(installer.InstallError, "symbolic link"):
            installer._package_from_archive(make_archive([(link, b"outside")]), COMMIT, "https://example.com")
        with self.assertRaisesRegex(installer.InstallError, "archive"):
            installer._package_from_archive(b"not a ZIP", COMMIT, "https://example.com")
        with patch.object(installer, "MAX_PAYLOAD_FILE", 4), self.assertRaisesRegex(installer.InstallError, "too large"):
            installer._package_from_archive(make_archive(), COMMIT, "https://example.com")

    def test_archive_requires_sane_manifest_saved_variables_and_runtime_paths(self):
        for manifest in (
                MANIFEST.replace(b"ForeverTomeDB", b"OtherDB"),
                MANIFEST.replace(b"0.2.3", b"invalid-version"),
                MANIFEST.replace(b"Core.lua", b"../Core.lua"),
                MANIFEST + b"Core.lua\n", MANIFEST.replace(b"Bootstrap.lua\n", b"")):
            with self.subTest(manifest=manifest), self.assertRaises(installer.InstallError):
                installer._package_from_archive(make_archive(manifest=manifest), COMMIT, "https://example.com")

    def test_install_preserves_saved_variables_unknown_files_and_other_addons(self):
        self.target.mkdir(parents=True)
        saved = self.client / "WTF" / "Account" / "test" / "SavedVariables" / "ForeverTome.lua"
        saved.parent.mkdir(parents=True)
        saved.write_bytes(b"private saved recording")
        (self.target / "settings.json").write_bytes(b"user settings")
        (self.target / "Core.lua").write_bytes(b"old core")
        other = self.target.parent / "OtherAddon"
        other.mkdir()
        (other / "addon.lua").write_bytes(b"other addon")
        self.assertIsNone(installer.installed_version(self.client))
        target = installer.install_addon(self.package, self.client)
        self.assertEqual(target, self.target)
        self.assertEqual(installer.installed_version(self.client), "0.2.3")
        for name, content in self.package.files.items():
            self.assertEqual((target / name).read_bytes(), content)
        self.assertEqual(saved.read_bytes(), b"private saved recording")
        self.assertEqual((target / "settings.json").read_bytes(), b"user settings")
        self.assertEqual((other / "addon.lua").read_bytes(), b"other addon")
        self.assertFalse((target / "tests").exists())
        self.assertEqual(list(target.parent.glob(".ForeverTome-install-*")), [])

    def test_failed_replacement_rolls_back_existing_and_new_files(self):
        self.target.mkdir(parents=True)
        (self.target / "Core.lua").write_bytes(b"original core")
        (self.target / "ForeverTome.toc").write_bytes(MANIFEST.replace(b"0.2.3", b"0.2.2"))
        original = {path.name: path.read_bytes() for path in self.target.iterdir()}
        replace  = installer.os.replace
        calls    = []

        def interrupted(source, destination):
            calls.append((Path(source), Path(destination)))
            if len(calls) == 3:
                raise PermissionError("Synthetic write failure")
            replace(source, destination)

        with patch.object(installer.os, "replace", side_effect=interrupted):
            with self.assertRaisesRegex(installer.InstallError, "previous addon files were restored"):
                installer.install_addon(self.package, self.client)
        self.assertEqual({path.name: path.read_bytes() for path in self.target.iterdir()}, original)
        self.assertEqual(installer.installed_version(self.client), "0.2.2")
        self.assertEqual(list(self.target.parent.glob(".ForeverTome-install-*")), [])

    def test_reparse_destination_is_rejected_before_any_install_writes(self):
        original_lstat = Path.lstat
        addons         = self.client / "Interface" / "AddOns"

        def reparse_status(path):
            if path == addons:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original_lstat(path)

        with patch.object(Path, "lstat", reparse_status):
            with self.assertRaisesRegex(installer.InstallError, "junctions"):
                installer.install_addon(self.package, self.client)
        self.assertFalse((self.client / "Interface").exists())

    def test_package_cannot_supply_files_outside_its_manifest(self):
        files = dict(self.package.files)
        files["../escaped.lua"] = b"bad"
        package = installer.AddonPackage("0.2.3", COMMIT, files, "https://example.com")
        with self.assertRaisesRegex(installer.InstallError, "manifest"):
            installer.install_addon(package, self.client)
        self.assertFalse((self.client / "Interface").exists())

    def test_manual_client_preference_is_saved_without_a_recording(self):
        settings = self.root / "settings.json"
        desktop.save_settings("", self.root / "catalog", path=settings, client=self.client)
        self.assertEqual(desktop.load_settings(settings), {"output_dir": str(self.root / "catalog"), "client": str(self.client)})


if __name__ == "__main__":
    unittest.main()
