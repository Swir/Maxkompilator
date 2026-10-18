"""Verify a real self-contained .NET apphost, resource and off-source smoke test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from maxkompilator.adapters.python_adapter import native_target
from maxkompilator.engine import identify_file


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def qualify(report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "built", report.get("error")
    assert report["plan"]["project"]["kind"] == "dotnet"
    assert report["execution_plan"]["format"] == "directory"
    target = native_target().replace("macos-", "osx-", 1)
    assert report["plan"]["target"] == target, "Build plan targets a different platform"
    assert report["execution_plan"]["target"] == target, "Published output is not native"
    assert any(
        "--self-contained" in step["command"]
        and step["command"][step["command"].index("--self-contained") + 1] == "true"
        for step in report["steps"]
    ), "Expected an explicit self-contained dotnet publish command"
    assert report["smoke_test"]["status"] == "passed", report["smoke_test"]
    assert "MAXKOMPILATOR_DOTNET_RUNTIME_OK" in report["smoke_test"]["output_tail"]
    assert report["steps"] and all(step["returncode"] == 0 for step in report["steps"])
    output = Path(report["artifact_directory"]).resolve()
    assert output.is_dir()
    host = output / ("HelloDotnet.exe" if sys.platform == "win32" else "HelloDotnet")
    runtimeconfig = output / "HelloDotnet.runtimeconfig.json"
    deps = output / "HelloDotnet.deps.json"
    resource = output / "Assets" / "greeting.txt"
    runtime = (
        ["hostfxr.dll", "hostpolicy.dll", "coreclr.dll"] if sys.platform == "win32"
        else ["libhostfxr.dylib", "libhostpolicy.dylib", "libcoreclr.dylib"] if sys.platform == "darwin"
        else ["libhostfxr.so", "libhostpolicy.so", "libcoreclr.so"]
    )
    for path in (host, runtimeconfig, deps, resource, *(output / name for name in runtime)):
        assert path.is_file() and path.stat().st_size > 0, f"Missing distribution file: {path}"
    assert resource.read_text(encoding="utf-8").strip() == "MAXKOMPILATOR_DOTNET_RESOURCE_OK"
    artifacts = [item for item in report["artifacts"] if Path(item["path"]).resolve() == host]
    assert len(artifacts) == 1, "Expected exactly one recorded .NET application host"
    record = artifacts[0]
    assert record["verified"] and record["sha256"] == sha256(host)
    family, architecture = target.split("-", 1)
    expected_format = {"win": "pe-", "linux": "elf-", "osx": "mach-o"}[family]
    if family != "osx":
        expected_format += architecture
    assert record["format"] == expected_format, record["format"]
    assert identify_file(host) == expected_format, "Apphost format does not match its report"
    smoke = report["smoke_test"]
    # The application must execute from a temporary *copy* of the entire
    # publish directory; a foreign CWD alone does not prove portability.
    assert smoke["source_command"] == [str(host)]
    staged = Path(smoke["command"][0])
    assert staged.name == host.name and staged.parent.name == "publish"
    assert not staged.is_relative_to(output), "Staged runtime must be outside the checkout build"
    relocation = smoke["relocation"]
    assert relocation["mode"] == "copied_publish_tree"
    assert relocation["source_sha256"] == sha256(host)
    assert relocation["staged_sha256"] == sha256(host)
    assert relocation["copied_files"] >= len(runtime) + 4
    result = {
        "status": "passed",
        "host": str(host),
        "host_format": record["format"],
        "host_sha256": sha256(host),
        "resource_sha256": sha256(resource),
        "self_contained_runtime_files": runtime,
        "smoke_test": "passed_outside_source_directory",
        "report_path": str(report_path.resolve()),
    }
    (report_path.parent / "dotnet-qualification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/qualify_dotnet.py BUILD-REPORT.json")
    print(json.dumps(qualify(Path(sys.argv[1]).resolve()), indent=2))
