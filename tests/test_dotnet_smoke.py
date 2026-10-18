"""Native .NET smoke commands must target one current, runnable apphost."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from maxkompilator.adapters.python_adapter import native_target
from maxkompilator.engine import _smoke_command
from maxkompilator.models import BuildPlan, Project


class DotnetSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "published"
        self.output.mkdir()
        self.target = native_target().replace("macos-", "osx-", 1)
        self.project = Project(self.root, "dotnet", "Demo", project_file="Demo.csproj")
        self.plan = BuildPlan(self.project, self.target, "directory", self.output)

    def _host(self, name: str = "Demo") -> Path:
        suffix = ".exe" if self.target.startswith("win-") else ""
        host = self.output / (name + suffix)
        host.write_bytes(b"fixture")
        (self.output / (name + ".runtimeconfig.json")).write_text("{}", encoding="utf-8")
        return host

    def _artifact(self, host: Path) -> list[dict]:
        family = self.target.split("-", 1)[0]
        architecture = self.target.rsplit("-", 1)[-1]
        return [{"path": str(host),
                 "format": {"win": "pe-", "linux": "elf-", "osx": "mach-o"}[family]
                           + (architecture if family != "osx" else ""),
                 "verified": True}]

    def test_one_native_apphost_with_matching_runtimeconfig_is_selected(self) -> None:
        host = self._host()
        self.assertEqual(_smoke_command(self.plan, self._artifact(host), "unused"), [str(host)])

    def test_wrong_architecture_apphost_is_not_executed(self) -> None:
        host = self._host()
        record = self._artifact(host)
        record[0]["format"] = "pe-x86" if self.target.startswith("win-") else (
            "elf-arm64" if self.target.startswith("linux-") else "data"
        )
        self.assertIsNone(_smoke_command(self.plan, record, "unused"))

    def test_unverified_apphost_is_not_executed(self) -> None:
        host = self._host()
        record = self._artifact(host)
        record[0]["verified"] = False
        self.assertIsNone(_smoke_command(self.plan, record, "unused"))

    def test_missing_runtimeconfig_does_not_run_random_executable(self) -> None:
        host = self._host()
        (self.output / "Demo.runtimeconfig.json").unlink()
        self.assertIsNone(_smoke_command(self.plan, self._artifact(host), "unused"))

    def test_ambiguous_apphosts_are_not_run(self) -> None:
        one = self._host("First")
        two = self._host("Second")
        self.assertIsNone(_smoke_command(self.plan, self._artifact(one) + self._artifact(two), "unused"))

    def test_old_or_external_apphost_is_not_run(self) -> None:
        external = self._host()
        moved = self.root / external.name
        moved.write_bytes(b"fixture")
        self.assertIsNone(_smoke_command(self.plan, self._artifact(moved), "unused"))

    def test_foreign_rid_never_claims_runtime_success(self) -> None:
        host = self._host()
        foreign = "win-arm64" if self.target != "win-arm64" else "linux-x64"
        self.assertIsNone(_smoke_command(replace(self.plan, target=foreign), self._artifact(host), "unused"))


if __name__ == "__main__":
    unittest.main()
