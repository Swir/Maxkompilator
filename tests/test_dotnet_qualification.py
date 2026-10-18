"""Validate the .NET evidence checker with deliberately synthetic reports.

These tests do not claim to compile or run the .NET fixture. CI does that.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import struct

from maxkompilator.adapters.python_adapter import native_target
import tempfile
import unittest

from scripts.qualify_dotnet import qualify


class DotnetQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name).resolve() / "published"
        self.output.mkdir()
        (self.output / "Assets").mkdir()
        self.host = self.output / ("HelloDotnet.exe" if sys.platform == "win32" else "HelloDotnet")
        family, architecture = native_target().replace("macos-", "osx-", 1).split("-", 1)
        if family == "win":
            header = bytearray(136)
            header[:2] = b"MZ"
            struct.pack_into("<I", header, 60, 128)
            header[128:132] = b"PE\x00\x00"
            struct.pack_into("<H", header, 132, {"x64": 0x8664, "arm64": 0xAA64, "x86": 0x14C}[architecture])
        elif family == "linux":
            header = bytearray(64)
            header[:4] = b"\x7fELF"
            header[5] = 1  # little-endian
            header[18:20] = {"x64": 62, "arm64": 183, "x86": 3, "arm": 40}[architecture].to_bytes(2, "little")
        else:
            header = bytearray(b"\xcf\xfa\xed\xfe" + bytes(60))
        self.host.write_bytes(header)
        (self.output / "HelloDotnet.runtimeconfig.json").write_text('{"runtimeOptions":{}}', encoding="utf-8")
        (self.output / "HelloDotnet.deps.json").write_text('{"runtimeTarget":{}}', encoding="utf-8")
        (self.output / "Assets" / "greeting.txt").write_text("MAXKOMPILATOR_DOTNET_RESOURCE_OK\n", encoding="utf-8")
        runtime = (["hostfxr.dll", "hostpolicy.dll", "coreclr.dll"] if sys.platform == "win32"
                   else ["libhostfxr.dylib", "libhostpolicy.dylib", "libcoreclr.dylib"] if sys.platform == "darwin"
                   else ["libhostfxr.so", "libhostpolicy.so", "libcoreclr.so"])
        for filename in runtime:
            (self.output / filename).write_bytes(b"synthetic-runtime-not-real")
        self.report_path = Path(self.temp.name) / "build-report.json"
        self.report = {
            "status": "built",
            "plan": {"project": {"kind": "dotnet"},
                     "target": native_target().replace("macos-", "osx-", 1)},
            "execution_plan": {"format": "directory", "target": native_target().replace("macos-", "osx-", 1)},
            "artifact_directory": str(self.output),
            "smoke_test": {"status": "passed", "command": [str(Path(self.temp.name) / "staged" / "publish" / self.host.name)],
                           "source_command": [str(self.host)],
                           "relocation": {"mode": "copied_publish_tree",
                                          "source_sha256": hashlib.sha256(self.host.read_bytes()).hexdigest(),
                                          "staged_sha256": hashlib.sha256(self.host.read_bytes()).hexdigest(),
                                          "copied_files": len(runtime) + 4},
                           "output_tail": "MAXKOMPILATOR_DOTNET_RUNTIME_OK"},
            "steps": [{"returncode": 0, "command": ["dotnet", "publish", "demo.csproj", "--self-contained", "true"]}],
            "artifacts": [{"path": str(self.host),
                           "format": ("pe-" + native_target().split("-")[-1] if sys.platform == "win32" else
                                      "mach-o" if sys.platform == "darwin" else "elf-" + native_target().split("-")[-1]),
                           "verified": True,
                           "sha256": hashlib.sha256(self.host.read_bytes()).hexdigest()}],
        }

    def _qualify(self) -> dict:
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        return qualify(self.report_path)

    def test_evidence_contract_accepts_consistent_fixture(self) -> None:
        result = self._qualify()
        self.assertEqual(result["status"], "passed")
        self.assertTrue((self.report_path.parent / "dotnet-qualification.json").exists())

    def test_qualifier_rejects_tampered_host_checksum(self) -> None:
        self.report["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_wrong_rid(self) -> None:
        self.report["execution_plan"]["target"] = "win-arm64" if sys.platform != "win32" else "linux-x64"
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_runtime_not_relocated(self) -> None:
        self.report["smoke_test"]["command"] = [str(self.host)]
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_tampered_staged_checksum(self) -> None:
        self.report["smoke_test"]["relocation"]["staged_sha256"] = "0" * 64
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_incomplete_staged_directory(self) -> None:
        self.report["smoke_test"]["relocation"]["copied_files"] = 1
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_non_self_contained_build(self) -> None:
        self.report["steps"][0]["command"] = ["dotnet", "publish", "demo.csproj"]
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_checks_actual_binary_format(self) -> None:
        self.host.write_bytes(b"not an executable")
        self.report["artifacts"][0]["sha256"] = hashlib.sha256(self.host.read_bytes()).hexdigest()
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_missing_resource(self) -> None:
        (self.output / "Assets" / "greeting.txt").unlink()
        with self.assertRaises(AssertionError):
            self._qualify()

    def test_qualifier_rejects_unrun_or_failed_smoke(self) -> None:
        for status in ("not_run", "failed"):
            self.report["smoke_test"]["status"] = status
            with self.subTest(status=status), self.assertRaises(AssertionError):
                self._qualify()


if __name__ == "__main__":
    unittest.main()
