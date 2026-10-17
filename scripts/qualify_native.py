"""Validate and run the known example from the report, outside source/PATH."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if report["status"] != "built" or report["smoke_test"]["status"] != "passed":
        raise SystemExit("The build and smoke test must pass before qualification.")
    name = report["project"]["name"] + (".exe" if os.name == "nt" else "")
    candidates = [item for item in report["artifacts"] if Path(item["path"]).name == name]
    if len(candidates) != 1:
        raise SystemExit("Expected exactly one application entry point.")
    artifact = candidates[0]
    binary = Path(artifact["path"])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != artifact["sha256"]:
        raise SystemExit("Artifact checksum changed after the build.")
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32") if os.name == "nt" else "/usr/bin:/bin"
    with tempfile.TemporaryDirectory(prefix="maxkompilator-native-") as directory:
        result = subprocess.run([str(binary)], cwd=directory, env=environment,
                                capture_output=True, text=True, timeout=30, check=True)
    if "Maxkompilator: build and resource check OK" not in result.stdout:
        raise SystemExit("The example did not confirm its bundled resource.")
    evidence = {"status": "passed", "binary": str(binary), "sha256": artifact["sha256"],
                "format": artifact["format"], "outside_source": True, "python_environment_removed": True,
                "stdout": result.stdout.strip()}
    (args.report.parent / "native-qualification.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
