"""App profile validation should never require compilers or read outside roots."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from maxkompilator.app_profile import load_app_profile, native_icon
from maxkompilator.models import PlanError


class ApplicationProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "app project"
        self.root.mkdir()

    def config(self, text):
        (self.root / "maxkompilator.toml").write_text(text, encoding="utf-8")

    def test_empty_profile_uses_project_name(self):
        p = load_app_profile(self.root, "Fallback")
        self.assertEqual((p.name, p.version, p.icon), ("Fallback", None, None))

    def test_unconfigured_name_preserves_preexisting_behavior(self):
        p = load_app_profile(self.root, "An Existing Name With Spaces")
        self.assertEqual(p.name, "An Existing Name With Spaces")
        self.assertFalse(p.explicit_name)

    def test_saved_name_version_and_icon_round_trip(self):
        icon = self.root / "logo.ico"
        icon.write_bytes(b"fake icon; only path contract is tested")
        self.config('[app]\nname="MyApp"\nversion="2.4.6-beta.2"\nicon="logo.ico"\n')
        p = load_app_profile(self.root, "Fallback")
        self.assertEqual((p.name, p.version, p.icon), ("MyApp", "2.4.6-beta.2", icon))
        self.assertEqual(native_icon(p, "win-x64"), icon)
        with self.assertRaisesRegex(PlanError, "must use .icns"):
            native_icon(p, "osx-arm64")

    def test_valid_four_component_version(self):
        self.config('[app]\nversion="2.4.6.100"\n')
        self.assertEqual(load_app_profile(self.root, "App").version, "2.4.6.100")

    def test_bad_names_rejected(self):
        for invalid in ("", "../escape", "-bad", "spaces not allowed", "A" * 81, "---", "-p:Bad=1", "CON", "con.txt", "LPT1", "COM9.log", "ending."):
            with self.subTest(invalid=invalid):
                self.config(f'[app]\nname="{invalid}"\n')
                with self.assertRaises(PlanError):
                    load_app_profile(self.root, "Fallback")

    def test_bad_versions_rejected(self):
        for invalid in ("v2.0", "1", "1.2;Injected=true", "1.99999", "1.0.0 --bad", "1.2\u00a0"):
            with self.subTest(invalid=invalid):
                self.config(f'[app]\nversion="{invalid}"\n')
                with self.assertRaises(PlanError):
                    load_app_profile(self.root, "Fallback")

    def test_wrong_types_and_unknown_fields_rejected(self):
        for text in ('[app]\nname=123\n', '[app]\nversion=true\n',
                     '[app]\nicon=12\n', '[app]\nrandom="ignored"\n', 'app="no table"\n'):
            with self.subTest(text=text):
                self.config(text)
                with self.assertRaises(PlanError):
                    load_app_profile(self.root, "Fallback")

    def test_icon_outside_or_missing_rejected(self):
        for icon in ("../outside.ico", "/tmp/icon.ico", "missing.ico", "bad.svg", "."):
            with self.subTest(icon=icon):
                self.config(f'[app]\nicon="{icon}"\n')
                with self.assertRaises(PlanError):
                    load_app_profile(self.root, "Fallback")

    def test_icon_symlink_is_rejected(self):
        outside = Path(self.temp.name) / "secret.ico"
        outside.write_bytes(b"secret")
        try:
            (self.root / "icon.ico").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink permissions")
        self.config('[app]\nicon="icon.ico"\n')
        with self.assertRaises(PlanError):
            load_app_profile(self.root, "Fallback")

    def test_linux_icon_is_rejected_instead_of_claiming_embedded(self):
        (self.root / "logo.png").write_bytes(b"fake")
        self.config('[app]\nicon="logo.png"\n')
        with self.assertRaisesRegex(PlanError, "not supported"):
            native_icon(load_app_profile(self.root, "Fallback"), "linux-x64")

    def test_no_filesystem_writes_during_profile_loading(self):
        self.config('[app]\nname="Safe"\nversion="1.0"\n')
        before = {str(p) for p in self.root.rglob("*")}
        load_app_profile(self.root, "Fallback")
        self.assertEqual(before, {str(p) for p in self.root.rglob("*")})


if __name__ == "__main__":
    unittest.main()
