"""Android bundle validation: simulated Gradle inputs and real JDK signing checks."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from maxkompilator.android_bundle_qualification import qualify_debug_aab
from maxkompilator.models import BuildPlan, BuildStep, MaxkompilatorError, Project

_CERT = "ab" * 32


class DebugAabTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="aab validation unicode żółw ")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.project = root / "project with spaces"
        self.project.mkdir()
        self.output = root / "output"
        self.output.mkdir()
        self.relative = Path("app/build/outputs/bundle/debug/app-debug.aab")
        self.source = self.project / self.relative
        self.source.parent.mkdir(parents=True)
        self.copy = self.output / "artifacts" / self.relative
        self.copy.parent.mkdir(parents=True)
        self._create_archive(self.source)
        self.copy.write_bytes(self.source.read_bytes())
        self.record = {"path": str(self.copy), "format": "aab", "sha256": self._digest(self.copy), "verified": False}
        self.plan = BuildPlan(Project(self.project, "android", "app"), "android", "aab", self.output,
                              steps=(BuildStep("Build bundle", ("gradlew", ":app:clean", ":app:bundleDebug"), self.project),))
        self.result_mode = "signed"
        self.commands = []

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _create_archive(path: Path, additions: dict[str, bytes] | None = None) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("BundleConfig.pb", b"\x08\x01")
            z.writestr("base/manifest/AndroidManifest.xml", b"\x0a\x08binary proto")
            z.writestr("base/dex/classes.dex", b"dex\n035\0")
            for name, data in (additions or {}).items():
                z.writestr(name, data)

    def _runner(self, command: list[str], cwd: Path) -> dict:
        self.assertEqual(self._digest(cwd / 'bundle.aab'), self.record['sha256'])
        self.commands.append(command)
        if "jarsigner" in command[0]:
            if self.result_mode == "unsigned":
                return {"returncode": 0, "output_tail": "jar is unsigned."}
            if self.result_mode == "bad_signature":
                return {"returncode": 1, "output_tail": "signature failed"}
            if self.result_mode == "partial":
                return {"returncode": 0, "output_tail": "jar verified.\nThis jar contains unsigned entries."}
            if self.result_mode == "unconfirmed":
                return {"returncode": 0, "output_tail": ""}
            return {"returncode": 0, "output_tail": "jar verified."}
        if "keytool" in command[0]:
            return {"returncode": 0, "matching_lines": ["\t SHA256: " + ":".join(_CERT[i:i+2].upper() for i in range(0,64,2))],
                    "output_tail": "extensions"}
        raise AssertionError("Unexpected command " + str(command))

    def qualify(self) -> dict:
        return qualify_debug_aab(self.plan, self.output, self.record, self._runner)

    def _sync(self) -> None:
        self.copy.write_bytes(self.source.read_bytes())
        self.record["sha256"] = self._digest(self.copy)

    def test_signed_bundle_report_does_not_claim_device_or_release(self) -> None:
        result = self.qualify()
        self.assertFalse(result["verified"])
        self.assertTrue(result["signature_verified"])
        self.assertEqual(result["variant"], "debug")
        self.assertEqual(result["signature_status"], "jar_signed")
        self.assertEqual(result["signer_cert_sha256"], [_CERT])
        self.assertIn("device_store_not_tested", result["verification"])
        self.assertEqual(len(self.commands), 2)

    def test_unsigned_bundle_is_built_but_unqualified(self) -> None:
        self.result_mode = "unsigned"
        result = self.qualify()
        self.assertFalse(result["verified"])
        self.assertEqual(result["signature_status"], "unsigned")
        self.assertEqual(len(self.commands), 1)

    def test_missing_certificate_fingerprint_fails(self) -> None:
        def without_sha256(command: list[str], cwd: Path) -> dict:
            if "keytool" in command[0]:
                return {"returncode": 0, "output_tail": "Signer #1: no fingerprint"}
            return self._runner(command, cwd)
        with self.assertRaisesRegex(MaxkompilatorError, "No SHA-256"):
            qualify_debug_aab(self.plan, self.output, self.record, without_sha256)

    def test_bad_signature_fails(self) -> None:
        self.result_mode = "bad_signature"
        with self.assertRaisesRegex(MaxkompilatorError, "rejected"):
            self.qualify()

    def test_partially_signed_jar_must_fail_even_when_jarsigner_returns_zero(self) -> None:
        self.result_mode = "partial"
        with self.assertRaisesRegex(MaxkompilatorError, "unsigned entries"):
            self.qualify()

    def test_nonverification_is_rejected(self) -> None:
        self.result_mode = "unconfirmed"
        with self.assertRaisesRegex(MaxkompilatorError, "did not confirm"):
            self.qualify()

    def test_report_sha_mismatch_fails_before_launch(self) -> None:
        self.record["sha256"] = "0" * 64
        with self.assertRaisesRegex(MaxkompilatorError, "SHA-256"):
            self.qualify()
        self.assertEqual(self.commands, [])

    def test_copied_bytes_mismatch_fails_before_launch(self) -> None:
        self.copy.write_bytes(b"changed")
        with self.assertRaisesRegex(MaxkompilatorError, "differs"):
            self.qualify()

    def test_wrong_gradle_task_is_rejected(self) -> None:
        self.plan = BuildPlan(self.plan.project, "android", "aab", self.output,
                              steps=(BuildStep("wrong", ("gradlew", ":app:bundleRelease"), self.project),))
        with self.assertRaisesRegex(MaxkompilatorError, "bundleDebug"):
            self.qualify()

    def test_release_output_folder_is_rejected(self) -> None:
        self.record["path"] = str(self.source)
        with self.assertRaisesRegex(MaxkompilatorError, "artifact directory"):
            self.qualify()

    def test_other_flavor_folder_rejected_without_explicit_task(self) -> None:
        other = self.output / "artifacts/app/build/outputs/bundle/release/app-release.aab"
        other.parent.mkdir(parents=True)
        other.write_bytes(self.copy.read_bytes())
        self.record["path"] = str(other)
        with self.assertRaisesRegex(MaxkompilatorError, "bundle/debug"):
            self.qualify()

    def test_missing_protobuf_or_manifest_rejected(self) -> None:
        self._create_archive(self.source, {"base/assets/file.txt": b"hello"})
        with zipfile.ZipFile(self.source, "w") as z:
            z.writestr("BundleConfig.pb", b"\x08\x01")
        self._sync()
        with self.assertRaisesRegex(MaxkompilatorError, "base manifest"):
            self.qualify()

    def test_corrupted_zip_rejected(self) -> None:
        self.copy.write_bytes(b"not a ZIP")
        self.source.write_bytes(b"not a ZIP")
        self.record["sha256"] = self._digest(self.copy)
        with self.assertRaisesRegex(MaxkompilatorError, "Invalid or unreadable"):
            self.qualify()

    def test_zip_path_escape_rejected(self) -> None:
        self._create_archive(self.source, {"../evil.txt": b"bad"})
        self._sync()
        with self.assertRaisesRegex(MaxkompilatorError, "unsafe entry"):
            self.qualify()

    def test_zip_duplicate_entry_rejected(self) -> None:
        with zipfile.ZipFile(self.source, "a") as z:
            z.writestr("BundleConfig.pb", b"duplicate")
        self._sync()
        with self.assertRaisesRegex(MaxkompilatorError, "duplicate"):
            self.qualify()

    def test_symlink_zip_entry_rejected(self) -> None:
        entry = zipfile.ZipInfo("base/lib/link")
        entry.create_system = 3
        entry.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(self.source, "a") as z:
            z.writestr(entry, b"../manifest/")
        self._sync()
        with self.assertRaisesRegex(MaxkompilatorError, "symlink"):
            self.qualify()

    def test_cross_directory_copied_file_rejected(self) -> None:
        copied = self.output / "leaked.aab"
        copied.write_bytes(self.copy.read_bytes())
        self.record["path"] = str(copied)
        with self.assertRaisesRegex(MaxkompilatorError, "artifact directory"):
            self.qualify()

    @unittest.skipUnless(all(shutil.which(name) for name in ("keytool", "jarsigner")), "JDK signing tools unavailable")
    def test_real_jdk_jar_signing_and_unsigned_entry_attack(self) -> None:
        keystore = self.output / "debug-test.keystore"
        def real_run(command: list[str], cwd: Path) -> dict:
            self.assertTrue(all(value.isascii() for value in command[1:]))
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=False, timeout=20)
            stdout = result.stdout + "\n" + result.stderr
            return {"returncode": result.returncode, "output_tail": stdout,
                    "matching_lines": [line for line in stdout.splitlines() if line.lstrip().startswith("SHA256:")]}

        unsigned = qualify_debug_aab(self.plan, self.output, self.record, real_run)
        self.assertFalse(unsigned["verified"])
        self.assertEqual(unsigned["signature_status"], "unsigned")

        subprocess.run(["keytool", "-genkeypair", "-alias", "test", "-keyalg", "RSA",
                        "-keysize", "2048", "-validity", "30", "-dname", "CN=Maxkompilator CI, C=NO",
                        "-keystore", keystore.name, "-storepass", "changeit",
                        "-keypass", "changeit", "-noprompt"], cwd=self.output, check=True, capture_output=True, timeout=25)
        subprocess.run(["jarsigner", "-keystore", keystore.name, "-storepass", "changeit",
                        "-keypass", "changeit", os.path.relpath(self.source, self.output), "test"],
                       cwd=self.output, check=True, capture_output=True, timeout=25)
        self._sync()

        signed = qualify_debug_aab(self.plan, self.output, self.record, real_run)
        self.assertFalse(signed["verified"])
        self.assertTrue(signed["signature_verified"])
        self.assertEqual(signed["signature_status"], "jar_signed")
        self.assertEqual(len(signed["signer_cert_sha256"]), 1)

        # jarsigner -verify returns *zero* for a partial-signature JAR. Ensure
        # we reject added payload even if source, copy, and report all match.
        with zipfile.ZipFile(self.source, "a") as z:
            z.writestr("base/assets/injected.txt", b"unexpected unsigned payload")
        self._sync()
        with self.assertRaisesRegex(MaxkompilatorError, "unsigned entries"):
            qualify_debug_aab(self.plan, self.output, self.record, real_run)


if __name__ == "__main__":
    unittest.main()
