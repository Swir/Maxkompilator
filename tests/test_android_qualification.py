"""Unit tests are deliberately simulated: real APK/SDK qualification is pending."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from maxkompilator.android_qualification import qualify_debug_apk, _build_tools
from maxkompilator.models import BuildPlan, BuildStep, MaxkompilatorError, Project


_CERT = '12ab' * 16


class AndroidQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="android qualification ")
        self.addCleanup(temp.cleanup)
        work = Path(temp.name).resolve()
        self.source = work / "my project źródła"
        self.source.mkdir()
        self.output = work / "dist"
        self.output.mkdir()
        self.sdk = work / "Android SDK"
        sdk_tools = self.sdk / "build-tools" / "35.0.0"
        (sdk_tools / "lib").mkdir(parents=True)
        (sdk_tools / "aapt").write_bytes(b'NOT EXECUTABLE - TEST FIXTURE')
        (sdk_tools / "aapt.exe").write_bytes(b'NOT EXECUTABLE - TEST FIXTURE')
        (sdk_tools / "lib" / "apksigner.jar").write_bytes(b'NOT A REAL JAR - TEST FIXTURE')
        relative = Path("app/build/outputs/apk/debug/app-debug.apk")
        self.original = self.source / relative
        self.original.parent.mkdir(parents=True)
        with zipfile.ZipFile(self.original, "w") as package:
            package.writestr("AndroidManifest.xml", b'\x03\x00\x08\x00\x08\x00\x00\x00')
            package.writestr("classes.dex", b'dex\n035\x00')
        self.copied = self.output / "artifacts" / relative
        self.copied.parent.mkdir(parents=True)
        self.copied.write_bytes(self.original.read_bytes())
        self.metadata = self.original.parent / "output-metadata.json"
        self.meta = {
            "version": 3, "applicationId": "com.example.hello", "variantName": "debug",
            "elements": [{"type": "SINGLE", "versionCode": 7, "versionName": "1.2", "outputFile": "app-debug.apk"}],
        }
        self._save_metadata()
        self.plan = BuildPlan(Project(self.source, "android", "app"), "android", "apk", self.output,
                              steps=(BuildStep("Android debug APK", ("gradlew", ":app:clean", ":app:assembleDebug"), self.source),))
        self.record = {
            "format": "apk", "path": str(self.copied), "sha256": hashlib.sha256(self.copied.read_bytes()).hexdigest(),
            "verified": False,
        }
        self.commands: list[list[str]] = []
        self.badging = "package: name='com.example.hello' versionCode='7' versionName='1.2'\napplication-debuggable"
        self.signers = f"Verified using v2 scheme: true\nSigner #1 certificate SHA-256 digest: {_CERT}"
        self.badge_exit = 0
        self.signer_exit = 0

    def _save_metadata(self) -> None:
        self.metadata.write_text(json.dumps(self.meta), encoding="utf-8")

    def _runner(self, command: list[str]) -> dict:
        self.commands.append(command)
        if "badging" in command:
            return {"returncode": self.badge_exit,
                    "matching_lines": self.badging.splitlines(),
                    "output_tail": "trailing resources list without metadata"}
        return {"returncode": self.signer_exit,
                "matching_lines": self.signers.splitlines(),
                "output_tail": self.signers}

    def qualify(self) -> dict:
        return qualify_debug_apk(self.plan, self.output, self.record, self.sdk, self._runner)

    @patch.dict("os.environ", {"JAVA_HOME": ""})
    def test_metadata_manifest_and_signature_all_verified(self) -> None:
        result = self.qualify()
        self.assertTrue(result["verified"])
        self.assertEqual(result["package"], "com.example.hello")
        self.assertEqual(result["version_code"], 7)
        self.assertEqual(result["version_name"], "1.2")
        self.assertEqual(result["variant"], "debug")
        self.assertEqual(result["signer_cert_sha256"], [_CERT])
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(self.commands[0][1:3], ["dump", "badging"])
        self.assertEqual(self.commands[1][:2], ["java", "-jar"])
        self.assertIn("device_install_not_tested", result["verification"])

    def test_rejects_tampered_copy_before_inspection(self) -> None:
        self.copied.write_bytes(b'APK CHANGED')
        with self.assertRaisesRegex(MaxkompilatorError, "differs"):
            self.qualify()
        self.assertEqual(self.commands, [])

    def test_rejects_report_checksum_mismatch(self) -> None:
        self.record["sha256"] = "0" * 64
        with self.assertRaisesRegex(MaxkompilatorError, "checksum"):
            self.qualify()

    def test_rejects_release_variant(self) -> None:
        self.meta["variantName"] = "release"
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "debug variant"):
            self.qualify()

    def test_rejects_metadata_referring_to_another_apk(self) -> None:
        self.meta["elements"][0]["outputFile"] = "other.apk"
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "exact APK"):
            self.qualify()

    def test_rejects_package_mismatch(self) -> None:
        self.meta["applicationId"] = "com.example.other"
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "package differs"):
            self.qualify()
        self.assertEqual(len(self.commands), 1)

    def test_rejects_version_code_mismatch(self) -> None:
        self.meta["elements"][0]["versionCode"] = 8
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "versionCode"):
            self.qualify()

    def test_rejects_version_name_mismatch(self) -> None:
        self.meta["elements"][0]["versionName"] = "1.3"
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "versionName"):
            self.qualify()

    def test_rejects_nondebuggable_apk(self) -> None:
        self.badging = self.badging.splitlines()[0]
        with self.assertRaisesRegex(MaxkompilatorError, "not marked debuggable"):
            self.qualify()

    def test_rejects_bad_aapt_exit(self) -> None:
        self.badge_exit = 1
        with self.assertRaisesRegex(MaxkompilatorError, "aapt"):
            self.qualify()

    def test_rejects_bad_signature(self) -> None:
        self.signer_exit = 1
        with self.assertRaisesRegex(MaxkompilatorError, "apksigner rejected"):
            self.qualify()

    def test_rejects_missing_signer_fingerprint(self) -> None:
        self.signers = 'Verified using v1 scheme: true'
        with self.assertRaisesRegex(MaxkompilatorError, "no signer certificate"):
            self.qualify()

    def test_rejects_missing_metadata(self) -> None:
        self.metadata.unlink()
        with self.assertRaisesRegex(MaxkompilatorError, "Missing or oversized"):
            self.qualify()

    def test_rejects_untrusted_gradle_task(self) -> None:
        self.plan = BuildPlan(self.plan.project, 'android', 'apk', self.output,
                              steps=(BuildStep('release', ('gradlew', ':app:assembleRelease'), self.source),))
        with self.assertRaisesRegex(MaxkompilatorError, "assembleDebug"):
            self.qualify()

    def test_rejects_path_from_outside_artifact_directory(self) -> None:
        self.record['path'] = str(self.original)
        with self.assertRaisesRegex(MaxkompilatorError, "not copied"):
            self.qualify()

    def test_rejects_duplicate_gradle_output_entries(self) -> None:
        self.meta["elements"].append(dict(self.meta["elements"][0]))
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "once"):
            self.qualify()

    def test_rejects_bool_version_code_even_though_bool_is_an_int(self) -> None:
        self.meta["elements"][0]["versionCode"] = True
        self._save_metadata()
        with self.assertRaisesRegex(MaxkompilatorError, "versionCode"):
            self.qualify()

    def test_rejects_no_manifest_package_line(self) -> None:
        self.badging = "application-debuggable"
        with self.assertRaisesRegex(MaxkompilatorError, "manifest package"):
            self.qualify()

    def test_rejects_outside_metadata_symlink(self) -> None:
        outside = self.source.parent / "outside-output.json"
        outside.write_text(self.metadata.read_text(encoding="utf-8"), encoding="utf-8")
        self.metadata.unlink()
        try:
            self.metadata.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable to this test process")
        with self.assertRaisesRegex(MaxkompilatorError, "metadata must remain inside"):
            self.qualify()

    def test_rejects_wrong_apk_format(self) -> None:
        self.record['format'] = 'zip'
        with self.assertRaisesRegex(MaxkompilatorError, "compiled Android APK"):
            self.qualify()

    def test_tool_versions_are_sorted_numerically(self) -> None:
        new = self.sdk / 'build-tools' / '36.0.0'
        (new / 'lib').mkdir(parents=True)
        (new / 'aapt').write_text('placeholder')
        (new / 'aapt.exe').write_text('placeholder')
        (new / 'lib' / 'apksigner.jar').write_text('placeholder')
        aapt, jar = _build_tools(self.sdk)
        self.assertEqual(aapt.parent.name, '36.0.0')
        self.assertEqual(jar.parent.parent.name, '36.0.0')

    def test_rejects_mismatched_tool_versions(self) -> None:
        (self.sdk / 'build-tools' / '35.0.0' / 'lib' / 'apksigner.jar').unlink()
        with self.assertRaisesRegex(MaxkompilatorError, "same build-tools version"):
            self.qualify()

    def test_does_not_accept_missing_signature_in_empty_success(self) -> None:
        self.signers = ''
        with self.assertRaisesRegex(MaxkompilatorError, "no signer"):
            self.qualify()


if __name__ == '__main__':
    unittest.main()
