"""Verify Android manifest evidence survives streaming output truncation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from maxkompilator.engine import run_command


class AndroidManifestCaptureTests(unittest.TestCase):
    def test_retain_manifest_header_when_tool_emits_large_output(self) -> None:
        script = (
            "print(\"package: name='com.example.hello' versionCode='1' versionName='1.0'\")\n"
            "print('application-debuggable')\n"
            "for index in range(200): print('resource entry', index)\n"
        )
        with tempfile.TemporaryDirectory(prefix="aapt output with spaces ") as temp:
            captured = []
            report = run_command(
                [sys.executable, "-c", script], Path(temp), threading.Event(), captured.append,
                capture_prefixes=("package:", "application-debuggable", "Signer #"), timeout=10,
            )
        self.assertEqual(report["returncode"], 0)
        self.assertIn("application-debuggable", report["matching_lines"])
        self.assertTrue(any(line.startswith("package:") for line in report["matching_lines"]))
        self.assertNotIn("package:", report["output_tail"])
        self.assertTrue(any("resource entry" in line for line in captured))

    def test_regular_command_preserves_preexisting_result_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = run_command([sys.executable, "-c", "print('PASS')"], Path(temp),
                                 threading.Event(), lambda _: None, timeout=10)
        self.assertEqual(report["returncode"], 0)
        self.assertIn("PASS", report["output_tail"])
        self.assertNotIn("matching_lines", report)


if __name__ == "__main__":
    unittest.main()
