"""Validate and run the known example from the report, outside source/PATH."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _archive_label(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError(f"Invalid {label} for the native archive: {value!r}")
    return value


def package_native(
    binary: Path,
    report_path: Path,
    qualification_path: Path,
    *,
    project_name: str,
    target: str,
    expected_sha256: str,
) -> dict:
    """Archive and verify an entire onedir without dereferencing symlinks.

    A tar file inside the uploaded CI artifact preserves POSIX permissions and
    link types independently from the artifact service's ZIP representation.
    This is a development artifact, not a signed release package.
    """
    project_name = _archive_label(project_name, "project name")
    target = _archive_label(target, "target")
    destination = report_path.parent / f"native-example-{target}.tar.gz"
    application = binary.parent
    expected: dict[str, tuple[Path, int, str | None]] = {
        project_name: (application, application.lstat().st_mode, None)
    }
    for directory, subdirectories, filenames in os.walk(application, followlinks=False):
        subdirectories[:] = sorted(name for name in subdirectories if name != ".work")
        for name in [*subdirectories, *sorted(filenames)]:
            if name == ".work":
                continue
            path = Path(directory) / name
            archived_name = project_name + "/" + path.relative_to(application).as_posix()
            mode = path.lstat().st_mode
            link = os.readlink(path) if stat.S_ISLNK(mode) else None
            expected[archived_name] = (path, mode, link)
    metadata = {"build-report.json": report_path, "native-qualification.json": qualification_path}
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)

    def omit_work(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
        return None if ".work" in PurePosixPath(member.name).parts else member

    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT, dereference=False, compresslevel=6) as archive:
            archive.add(application, arcname=project_name, filter=omit_work)
            for archived_name, source in metadata.items():
                archive.add(source, arcname=archived_name, recursive=False)
        with tarfile.open(temporary, "r:gz") as archive:
            members = archive.getmembers()
            entries = {member.name: member for member in members}
            if len(entries) != len(members) or set(entries) != set(expected) | set(metadata):
                raise ValueError("The native archive has missing, duplicate or unexpected members.")
            for archived_name, (_source, source_mode, link) in expected.items():
                member = entries[archived_name]
                if link is not None:
                    if not member.issym() or member.linkname != link:
                        raise ValueError(f"Symbolic link changed in archive: {archived_name}")
                elif stat.S_ISDIR(source_mode):
                    if not member.isdir():
                        raise ValueError(f"Directory changed in archive: {archived_name}")
                elif not (member.isfile() or member.islnk()):
                    raise ValueError(f"File changed in archive: {archived_name}")
                if os.name != "nt" and member.mode != stat.S_IMODE(source_mode):
                    raise ValueError(f"POSIX permissions changed in archive: {archived_name}")
            entry_name = project_name + "/" + binary.name
            entry = entries[entry_name]
            if os.name != "nt" and not entry.mode & 0o111:
                raise ValueError("The archived application has no executable permission bits.")
            stream = archive.extractfile(entry)
            if stream is None:
                raise ValueError("The archived application cannot be read.")
            with stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
                    raise ValueError("The archived application checksum does not match its build report.")
            for archived_name, source in metadata.items():
                stream = archive.extractfile(entries[archived_name])
                if stream is None:
                    raise ValueError(f"Missing archived evidence: {archived_name}")
                with stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != _sha256(source):
                        raise ValueError(f"Archived evidence changed: {archived_name}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "path": str(destination),
        "sha256": _sha256(destination),
        "size_bytes": destination.stat().st_size,
        "validated": True,
        "members": len(members),
        "symlinks_preserved": sum(link is not None for _path, _mode, link in expected.values()),
        "posix_permissions_checked": os.name != "nt",
        "binary_sha256_checked": True,
        "artifact_role": "development",
    }


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
    if _sha256(binary) != artifact["sha256"]:
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
    qualification_path = args.report.parent / "native-qualification.json"
    qualification_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    evidence["archive"] = package_native(
        binary, args.report, qualification_path,
        project_name=report["project"]["name"],
        target=report["plan"]["target"],
        expected_sha256=artifact["sha256"],
    )
    print(json.dumps(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
