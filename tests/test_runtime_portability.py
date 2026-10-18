"""No .NET SDK is required for these staging-contract unit tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import shutil

from maxkompilator.models import MaxkompilatorError
from maxkompilator.runtime_portability import stage_dotnet_runtime


class DotnetRuntimeRelocationTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="maxkompilator-runtime-stage-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.publish = self.root / "repo" / "runs" / "job"
        self.publish.mkdir(parents=True)
        self.launcher = self.publish / "Demo.exe" if os.name == "nt" else self.publish / "Demo"
        if os.name == "nt":
            self.launcher.write_bytes(b"synthetic exe, not run")
        else:
            self.launcher.write_text(
                "#!" + sys.executable + "\n"
                "from pathlib import Path\n"
                "import sys\n"
                "base = Path(__file__).resolve().parent\n"
                "print((base / 'Assets' / 'greeting.txt').read_text().strip())\n"
                "sys.exit(0 if (base / 'Assets' / 'greeting.txt').read_text().strip() == 'PORTABLE' else 3)\n",
                encoding="utf-8",
            )
            self.launcher.chmod(0o755)
        (self.publish / "Assets").mkdir()
        (self.publish / "Assets" / "greeting.txt").write_text("PORTABLE\n", encoding="utf-8")
        (self.publish / "Demo.runtimeconfig.json").write_text("{}", encoding="utf-8")
        self.destination = self.root / "outside" / "temporary"
        self.destination.mkdir(parents=True)

    def test_portable_tree_copied_and_has_matching_binary_hash(self):
        staged = stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertEqual(staged.executable, self.destination / "publish" / self.launcher.name)
        self.assertEqual(staged.source_sha256, hashlib.sha256(self.launcher.read_bytes()).hexdigest())
        self.assertEqual(staged.staged_sha256, staged.source_sha256)
        self.assertEqual(staged.copied_files, 3)
        self.assertEqual((staged.executable.parent / "Assets" / "greeting.txt").read_text().strip(), "PORTABLE")
        self.assertFalse(staged.executable.is_relative_to(self.publish))

    @unittest.skipIf(os.name == "nt", "Windows fixture only validates file staging, not a fake EXE")
    def test_staged_application_runs_without_original_publish_tree(self):
        staged = stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        (self.publish / "Assets" / "greeting.txt").unlink()
        result = subprocess.run([str(staged.executable)], cwd=self.destination, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PORTABLE", result.stdout)

    def test_rejects_modified_asset_bytes_during_copy_and_removes_staging(self):
        original_copytree = shutil.copytree

        def corrupt_resource(*args, **kwargs):
            result = Path(original_copytree(*args, **kwargs))
            if Path(args[0]) != self.publish:
                return result
            (result / "Assets" / "greeting.txt").write_text("CORRUPTED\n", encoding="utf-8")
            return result

        with patch("maxkompilator.runtime_portability.shutil.copytree", side_effect=corrupt_resource):
            with self.assertRaisesRegex(MaxkompilatorError, "SHA-256 snapshot"):
                stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    def test_rejects_missing_runtime_asset_after_copy(self):
        original_copytree = shutil.copytree

        def omit_resource(*args, **kwargs):
            result = Path(original_copytree(*args, **kwargs))
            if Path(args[0]) != self.publish:
                return result
            (result / "Assets" / "greeting.txt").unlink()
            return result

        with patch("maxkompilator.runtime_portability.shutil.copytree", side_effect=omit_resource):
            with self.assertRaisesRegex(MaxkompilatorError, "SHA-256 snapshot"):
                stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    def test_rejects_unexpected_runtime_asset_after_copy(self):
        original_copytree = shutil.copytree

        def inject_resource(*args, **kwargs):
            result = Path(original_copytree(*args, **kwargs))
            if Path(args[0]) != self.publish:
                return result
            (result / "unverified.dll").write_bytes(b"INJECTED")
            return result

        with patch("maxkompilator.runtime_portability.shutil.copytree", side_effect=inject_resource):
            with self.assertRaisesRegex(MaxkompilatorError, "SHA-256 snapshot"):
                stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    @unittest.skipIf(os.name == "nt", "FIFO special files require POSIX")
    def test_rejects_nonregular_files_before_staging(self):
        pipe = self.publish / "unsafe-pipe"
        os.mkfifo(pipe)
        with self.assertRaisesRegex(MaxkompilatorError, "Unsupported .NET runtime file"):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    def test_rejects_executable_outside_publish_directory(self):
        foreign = self.root / "Demo"
        foreign.write_text("foreign", encoding="utf-8")
        with self.assertRaisesRegex(MaxkompilatorError, "directly inside"):
            stage_dotnet_runtime(self.publish, foreign, self.destination)

    def test_rejects_nested_launcher(self):
        path = self.publish / "Assets" / "Nested"
        path.write_bytes(b"invalid")
        with self.assertRaisesRegex(MaxkompilatorError, "directly inside"):
            stage_dotnet_runtime(self.publish, path, self.destination)

    def test_rejects_relative_staging_path_inside_source(self):
        with self.assertRaisesRegex(MaxkompilatorError, "disjoint"):
            stage_dotnet_runtime(self.publish, self.launcher, self.publish)

    def test_rejects_staging_to_source_parent(self):
        with self.assertRaisesRegex(MaxkompilatorError, "disjoint"):
            stage_dotnet_runtime(self.publish, self.launcher, self.publish.parent)

    def test_rejects_preexisting_destination(self):
        (self.destination / "publish").mkdir()
        with self.assertRaisesRegex(MaxkompilatorError, "already occupied"):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)

    def test_rejects_external_symlink_even_with_legitimate_host(self):
        extra = self.root / "outside" / "secret.txt"
        extra.write_text("leak", encoding="utf-8")
        try:
            (self.publish / "secret").symlink_to(extra)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink permission")
        with self.assertRaisesRegex(MaxkompilatorError, "outside"):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    def test_rejects_broken_symlink(self):
        try:
            (self.publish / "dangling").symlink_to(self.root / "no-such-file")
        except (OSError, NotImplementedError):
            self.skipTest("No symlink permission")
        with self.assertRaisesRegex(MaxkompilatorError, "Invalid .* symlink"):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)

    def test_preserves_internal_symlinks_as_copies(self):
        try:
            (self.publish / "linked.txt").symlink_to(self.publish / "Assets" / "greeting.txt")
        except (OSError, NotImplementedError):
            self.skipTest("No symlink permission")
        staged = stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertEqual((staged.executable.parent / "linked.txt").read_text().strip(), "PORTABLE")
        self.assertFalse((staged.executable.parent / "linked.txt").is_symlink())

    def test_rejects_internal_directory_symlink_to_prevent_copy_recursion(self):
        try:
            (self.publish / "recursive").symlink_to(self.publish, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("No directory symlink permission")
        with self.assertRaisesRegex(MaxkompilatorError, "directory symlinks"):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)
        self.assertFalse((self.destination / "publish").exists())

    def test_missing_binary_rejected(self):
        self.launcher.unlink()
        with self.assertRaises((FileNotFoundError, MaxkompilatorError)):
            stage_dotnet_runtime(self.publish, self.launcher, self.destination)


if __name__ == "__main__":
    unittest.main()
