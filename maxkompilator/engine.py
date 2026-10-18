"""Run explicit build plans, preserve logs, and qualify their output files."""

from __future__ import annotations

import glob
import hashlib
import json
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipapp
import zipfile
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .environment import check_environment, process_options, spawn_external, stop_process
from .android_qualification import qualify_debug_apk
from .android_bundle_qualification import qualify_debug_aab
from .models import BuildPlan, MaxkompilatorError, serializable


IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
                "node_modules", "dist", "build", ".maxkompilator", ".idea", ".vscode", ".gradle"}
SECRET_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".pem", ".key"}


class Cancelled(MaxkompilatorError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_cancel(event: threading.Event) -> None:
    if event.is_set():
        raise Cancelled("Budowanie zostało anulowane.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(serializable(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_output_directory(plan: BuildPlan) -> Path:
    root = plan.project.root.resolve()
    output = plan.output_dir.expanduser().resolve()
    if output == root or root.is_relative_to(output):
        raise MaxkompilatorError("Katalog wynikowy nie może być katalogiem źródeł ani jego rodzicem.")
    if output.exists() and not output.is_dir():
        raise MaxkompilatorError("Ścieżka wynikowa musi wskazywać katalog.")
    return output


def build_zipapp(plan: BuildPlan, event: threading.Event, log: Callable[[str], None]) -> Path:
    """Package source and resources; dependencies/interpreter are not embedded."""
    root = plan.project.root.resolve()
    if not plan.project.entrypoint:
        raise MaxkompilatorError("PYZ wymaga wskazania pliku startowego przez --entry.")
    entry = (root / plan.project.entrypoint).resolve()
    if not entry.is_file() or not entry.is_relative_to(root) or entry.suffix != ".py":
        raise MaxkompilatorError("Plik startowy PYZ musi być plikiem .py wewnątrz projektu.")
    relative_entry = entry.relative_to(root)
    if relative_entry.stem == "__init__":
        raise MaxkompilatorError("Wskaż skrypt startowy, nie __init__.py pakietu.")
    if any(not part.isidentifier() for part in relative_entry.with_suffix("").parts):
        raise MaxkompilatorError("PYZ wymaga nazw modułów będących poprawnymi identyfikatorami Pythona.")
    output = validate_output_directory(plan)
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{plan.project.name}.pyz"
    if Path(plan.project.name).name != plan.project.name or plan.project.name in ("", ".", ".."):
        raise MaxkompilatorError("Nieprawidłowa nazwa programu.")
    with tempfile.TemporaryDirectory(prefix="maxkompilator-zipapp-") as temp:
        staging = Path(temp) / "source"
        staging.mkdir()
        copied = 0
        for directory, dirs, names in os.walk(root, followlinks=False):
            current = Path(directory)
            dirs[:] = [name for name in sorted(dirs)
                       if name not in IGNORED_DIRS and not name.endswith(".egg-info")
                       and not (current / name).is_symlink()
                       and not (current / name).resolve().is_relative_to(output)
                       and not (current / name).resolve().is_relative_to(Path(temp))]
            for name in sorted(names):
                _check_cancel(event)
                source = current / name
                if (source.is_symlink() or not source.is_file() or source.suffix in SECRET_SUFFIXES
                        or name == ".env" or name.startswith(".env.") or source.suffix in {".pyc", ".pyo"}
                        or name == "local.properties"):
                    continue
                if source.resolve().is_relative_to(output):
                    continue
                relative = source.relative_to(root)
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied += 1
        staged_entry = staging / relative_entry
        if not staged_entry.is_file():
            raise MaxkompilatorError("Plik startowy został wykluczony z paczki.")
        if relative_entry.as_posix() != "__main__.py":
            module = ".".join(relative_entry.with_suffix("").parts)
            (staging / "__main__.py").write_text(
                "# Generated by Maxkompilator.\nimport os, runpy, sys\n"
                f"sys.path.insert(0, os.path.join(os.path.dirname(__file__), {relative_entry.parent.as_posix()!r}))\n"
                f"runpy.run_module({module!r}, run_name='__main__')\n", encoding="utf-8")
        _check_cancel(event)
        archive = Path(temp) / "output.pyz"
        zipapp.create_archive(staging, target=archive, interpreter="/usr/bin/env python3", compressed=True)
        _check_cancel(event)
        # Install the completed file atomically on the output filesystem.
        temporary = output / f".{target.name}.{uuid.uuid4().hex}.tmp"
        try:
            shutil.copy2(archive, temporary)
            _check_cancel(event)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    log(f"Utworzono {target.name}; dołączono {copied} plików. PYZ wymaga zgodnego Pythona i zależności.")
    return target


def run_command(command: tuple[str, ...] | list[str], cwd: Path, event: threading.Event,
                log: Callable[[str], None], *, timeout: float = 1800.0,
                extra_env: dict[str, str] | None = None,
                capture_prefixes: tuple[str, ...] = ()) -> dict:
    """Stream child output without a shell, honour timeout and cancellation."""
    _check_cancel(event)
    started = time.monotonic()
    log("$ " + json.dumps(list(command), ensure_ascii=False))
    try:
        process = spawn_external(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 extra_env=extra_env, **process_options())
    except OSError as exc:
        raise MaxkompilatorError(f"Nie można uruchomić {command[0]}: {exc}") from exc
    messages: queue.Queue[bytes | None] = queue.Queue()

    def pump() -> None:
        assert process.stdout is not None
        try:
            for line in iter(process.stdout.readline, b""):
                messages.put(line)
        finally:
            messages.put(None)

    reader = threading.Thread(target=pump, name="maxkompilator-output", daemon=True)
    reader.start()
    excerpt: list[str] = []
    matched_lines: list[str] = []
    ended = False
    try:
        while not ended or process.poll() is None:
            if event.is_set():
                stop_process(process)
                raise Cancelled("Budowanie zostało anulowane; procesy zadania zatrzymano.")
            if time.monotonic() - started > timeout:
                stop_process(process)
                raise MaxkompilatorError(f"Przekroczono limit czasu zadania ({timeout:g} s).")
            try:
                item = messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                ended = True
            else:
                text = item.decode("utf-8", errors="replace").rstrip("\r\n")
                log(text)
                if (capture_prefixes and len(matched_lines) < 32
                        and any(text.startswith(prefix) for prefix in capture_prefixes)):
                    matched_lines.append(text[:1024])
                excerpt.append(text)
                if len(excerpt) > 30:
                    excerpt.pop(0)
        code = process.wait()
    finally:
        if process.poll() is None:
            stop_process(process)
        reader.join(timeout=1)
        if process.stdout:
            process.stdout.close()
    outcome = {"command": list(command), "returncode": code,
               "duration_seconds": round(time.monotonic() - started, 3), "output_tail": "\n".join(excerpt)}
    if capture_prefixes:
        outcome["matching_lines"] = matched_lines
    return outcome


def identify_file(path: Path) -> str:
    """Identify real container/executable signatures, never just a suffix."""
    with path.open("rb") as stream:
        header = stream.read(64)
        if header.startswith(b"MZ"):
            if len(header) < 64:
                return "invalid-pe"
            offset = struct.unpack_from("<I", header, 60)[0]
            if offset < 64 or offset + 6 > path.stat().st_size:
                return "invalid-pe"
            stream.seek(offset)
            pe = stream.read(6)
            if pe[:4] != b"PE\0\0":
                return "invalid-pe"
            machine = struct.unpack_from("<H", pe, 4)[0]
            return {0x8664: "pe-x64", 0xAA64: "pe-arm64", 0x14C: "pe-x86"}.get(machine, "pe-other")
        if header.startswith(b"\x7fELF") and len(header) >= 20:
            if header[5] not in (1, 2):
                return "invalid-elf"
            machine = int.from_bytes(header[18:20], "little" if header[5] == 1 else "big")
            return {62: "elf-x64", 183: "elf-arm64", 3: "elf-x86", 40: "elf-arm"}.get(machine, "elf-other")
        if header[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
            return "mach-o"
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if archive.testzip() is not None:
                    return "invalid-zip"
                if "AndroidManifest.xml" in names:
                    manifest = archive.read("AndroidManifest.xml")
                    binary_xml = len(manifest) >= 8 and manifest[:4] == b"\x03\x00\x08\x00" and int.from_bytes(manifest[4:8], "little") == len(manifest)
                    dex_files = [name for name in names if name.startswith("classes") and name.endswith(".dex") and "/" not in name]
                    has_dex = any(archive.read(name)[:4] == b"dex\n" for name in dex_files)
                    native = any(name.startswith("lib/") and name.endswith(".so") for name in names)
                    if binary_xml and (has_dex or native):
                        return "apk"
                    return "android-archive-unverified"
                if "base/manifest/AndroidManifest.xml" in names and "BundleConfig.pb" in names:
                    return "aab"
                if "__main__.py" in names:
                    return "pyz"
            return "zip"
        except (OSError, zipfile.BadZipFile):
            return "invalid-zip"
    return "data"


def collect_artifacts(plan: BuildPlan) -> list[dict]:
    output = validate_output_directory(plan)
    matches: set[Path] = set()
    for pattern in plan.artifact_patterns:
        expanded = pattern if Path(pattern).is_absolute() else str(output / pattern)
        for raw in glob.glob(expanded, recursive=True):
            path = Path(raw)
            if path.is_dir() and not path.is_symlink():
                matches.update(item for item in path.rglob("*") if item.is_file() and not item.is_symlink())
            elif path.is_file() and not path.is_symlink():
                matches.add(path)
    artifacts = []
    for source in sorted(matches):
        resolved = source.resolve()
        if source.is_relative_to(output) and any(part in {".work", ".maxkompilator"} for part in source.relative_to(output).parts):
            continue
        if source.name in {"build-report.json", "build-report.json.tmp", "build.log"}:
            continue
        if not resolved.is_relative_to(output):
            if not resolved.is_relative_to(plan.project.root.resolve()):
                raise MaxkompilatorError("Wynik zadania znajduje się poza projektem i katalogiem wynikowym.")
            # Android tooling writes under the module; preserve that relative
            # path so two flavours cannot silently overwrite each other.
            relative = resolved.relative_to(plan.project.root.resolve())
            destination = output / "artifacts" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, destination)
            source = destination
        if source.stat().st_size == 0:
            kind = "empty"
        else:
            kind = identify_file(source)
        artifacts.append({"path": str(source.resolve()), "size_bytes": source.stat().st_size,
                          "sha256": _sha256(source), "format": kind,
                          "verified": kind not in {"data", "empty", "invalid-pe", "invalid-elf", "invalid-zip", "apk", "aab", "android-archive-unverified"}})
    if not artifacts:
        raise MaxkompilatorError("Polecenie nie dostarczyło oczekiwanych plików wynikowych.")
    kinds = [item["format"] for item in artifacts]
    if plan.format == "zipapp" and "pyz" not in kinds:
        raise MaxkompilatorError("Wynik nie jest poprawnym archiwum Python PYZ.")
    if plan.format in {"apk", "aab"} and plan.format not in kinds:
        raise MaxkompilatorError(f"Wynik nie ma wymaganej struktury {plan.format.upper()}.")
    if plan.format in {"executable", "directory"}:
        if plan.target.startswith(("win", "windows")):
            prefix = "pe-"
        elif plan.target.startswith("linux"):
            prefix = "elf-"
        elif plan.target.startswith(("mac", "osx")):
            prefix = "mach-o"
        else:
            prefix = ""
        if prefix and not any(kind.startswith(prefix) for kind in kinds):
            raise MaxkompilatorError("Brak programu wykonywalnego dla zadeklarowanego systemu.")
        # PE/ELF machine types are checked against the selected CPU. Data and
        # optional managed DLLs do not override the actual program target.
        if prefix in {"pe-", "elf-"}:
            architecture = plan.target.rsplit("-", 1)[-1]
            expected = prefix + architecture
            if architecture in {"x64", "arm64", "x86"} and expected not in kinds:
                raise MaxkompilatorError(f"Brak pliku wykonywalnego dla architektury {architecture}.")
        if plan.project.kind == "python":
            main_name = plan.project.name + (".exe" if prefix == "pe-" else "")
            expected_main = (output / plan.project.name / main_name).resolve()
            main_files = [item for item in artifacts if Path(item["path"]) == expected_main]
            if len(main_files) != 1 or not main_files[0]["format"].startswith(prefix):
                raise MaxkompilatorError("Brak właściwego pliku startowego aplikacji Python; biblioteki nie zastępują programu.")
        if plan.project.kind == "dotnet":
            runtime_files = list(output.glob("*.runtimeconfig.json"))
            hosts = []
            for runtime_file in runtime_files:
                name = runtime_file.name.removesuffix(".runtimeconfig.json")
                host = (output / (name + (".exe" if prefix == "pe-" else ""))).resolve()
                hosts.extend(item for item in artifacts if Path(item["path"]) == host and item["format"].startswith(prefix))
            if not hosts:
                raise MaxkompilatorError("Brak pliku startowego .NET zgodnego z runtimeconfig.json.")
    return artifacts


def _smoke_command(plan: BuildPlan, artifacts: list[dict], python_executable: str) -> list[str] | None:
    if plan.format == "zipapp":
        return [python_executable, next(item["path"] for item in artifacts if item["format"] == "pyz")]
    if plan.project.kind == "dotnet" and plan.format == "directory":
        # Execute only on a native worker. A successful cross-RID publish
        # must not be mistaken for a runtime qualification.
        from .adapters.python_adapter import native_target
        host_target = native_target().replace("macos-", "osx-", 1)
        if plan.target != host_target:
            return None
        suffix = ".exe" if plan.target.startswith("win-") else ""
        family, architecture = plan.target.split("-", 1)
        prefix = {"win": "pe-", "linux": "elf-", "osx": "mach-o"}[family]
        expected_format = prefix if family == "osx" else prefix + architecture
        candidates: list[Path] = []
        for item in artifacts:
            if item.get("format") != expected_format or item.get("verified") is not True:
                continue
            executable = Path(str(item["path"])).resolve()
            if executable.parent != plan.output_dir.resolve():
                continue
            if suffix and executable.suffix.lower() != suffix:
                continue
            name = executable.name.removesuffix(suffix) if suffix else executable.name
            # Runtime configuration ties this apphost to a managed application.
            # Never execute an arbitrary DLL, hostfxr, or output from a prior run.
            if (executable.parent / f"{name}.runtimeconfig.json").is_file():
                candidates.append(executable)
        return [str(candidates[0])] if len(candidates) == 1 else None
    if plan.project.kind != "python" or plan.format != "executable":
        return None
    expected_name = plan.project.name + (".exe" if os.name == "nt" else "")
    candidates = [item["path"] for item in artifacts
                  if Path(item["path"]).name == expected_name and item["format"].startswith(("pe-", "elf-", "mach-o"))]
    return [candidates[0]] if len(candidates) == 1 else None


def isolated_native_plan(plan: BuildPlan, run_id: str) -> BuildPlan:
    """Give native tools a fresh destination so old files cannot pass a build."""
    if plan.project.kind not in {"python", "dotnet"} or plan.internal_builder:
        return plan
    destination = plan.output_dir / "runs" / run_id
    replacements = {
        str(plan.output_dir): str(destination),
        str(plan.output_dir / ".work"): str(destination / ".work"),
    }
    steps = tuple(replace(step, command=tuple(replacements.get(arg, arg) for arg in step.command))
                  for step in plan.steps)
    return replace(plan, output_dir=destination, steps=steps)


def execute_build(plan: BuildPlan, *, cancel_event: threading.Event | None = None,
                  on_log: Callable[[str], None] | None = None, smoke_test: bool = False,
                  timeout: float = 1800.0, smoke_timeout: float = 30.0,
                  python_executable: str = sys.executable) -> dict:
    event = cancel_event or threading.Event()
    output = validate_output_directory(plan)
    output.mkdir(parents=True, exist_ok=True)
    control = output / ".maxkompilator"
    control.mkdir(exist_ok=True)
    lock = control / "build.lock"
    try:
        lock_descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MaxkompilatorError("Ten katalog wynikowy jest zajęty przez inne zadanie. Wybierz inny katalog; po awarii sprawdź plik .maxkompilator/build.lock.") from exc
    run_id = uuid.uuid4().hex
    with os.fdopen(lock_descriptor, "w", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "run_id": run_id, "started_at": _now()}, stream)
    started = time.monotonic()
    run_dir = control / run_id
    run_dir.mkdir()
    execution_plan = isolated_native_plan(plan, run_id)
    report = {"run_id": run_id, "started_at": _now(), "status": "running", "output_dir": str(output),
              "project": serializable(plan.project), "plan": serializable(plan), "execution_plan": serializable(execution_plan),
              "artifact_directory": str(execution_plan.output_dir), "artifacts": [], "steps": [],
              "smoke_test": {"status": "not_run", "reason": "Test uruchomienia nie został zlecony."},
              "log_path": str(run_dir / "build.log"), "report_path": str(run_dir / "build-report.json"), "error": None}
    try:
        with (run_dir / "build.log").open("w", encoding="utf-8") as stream:
            def log(message: str) -> None:
                stream.write(message + "\n")
                stream.flush()
                if on_log:
                    on_log(message)

            try:
                _check_cancel(event)
                environment = check_environment(plan)
                report["environment"] = environment
                missing = [item for item in environment["checks"] if not item["available"]]
                if missing:
                    raise MaxkompilatorError("Brakuje wymaganego środowiska: " + "; ".join(f"{item['name']}: {item['hint']}" for item in missing))
                if plan.internal_builder == "zipapp":
                    build_zipapp(plan, event, log)
                elif plan.internal_builder:
                    raise MaxkompilatorError(f"Nieobsługiwany moduł budowania: {plan.internal_builder}")
                else:
                    for step in execution_plan.steps:
                        log(f"Etap: {step.name}")
                        outcome = run_command(step.command, step.cwd, event, log, timeout=timeout,
                                              extra_env={"PYINSTALLER_CONFIG_DIR": str(run_dir / "tool-cache")})
                        report["steps"].append(outcome)
                        if outcome["returncode"] != 0:
                            raise MaxkompilatorError(f"Etap {step.name} zakończył się kodem {outcome['returncode']}.")
                _check_cancel(event)
                report["artifacts"] = collect_artifacts(execution_plan)
                if plan.project.kind == "android" and plan.format == "apk":
                    sdk_check = next(item for item in environment["checks"] if item["name"] == "Android SDK")
                    sdk = Path(sdk_check["version"])

                    def run_android_tool(command: list[str]) -> dict:
                        return run_command(
                            command, plan.project.root, event, log, timeout=30,
                            capture_prefixes=("package:", "application-debuggable", "Signer #",
                                              "V1 Signer:", "V2 Signer:", "V3 Signer:",
                                              "V3.1 Signer:", "V3.2 Signer:", "V4 Signer:"),
                        )

                    for artifact in report["artifacts"]:
                        if artifact["format"] != "apk":
                            continue
                        # Only grant verified=True after output metadata, package,
                        # debug variant and signer certificate all agree.
                        artifact.update(qualify_debug_apk(
                            plan, execution_plan.output_dir, artifact, sdk, run_android_tool,
                        ))
                if plan.project.kind == "android" and plan.format == "aab":
                    def run_bundle_tool(command: list[str], cwd: Path) -> dict:
                        return run_command(
                            command, cwd, event, log, timeout=60,
                            capture_prefixes=("\t SHA256:", " SHA256:", "SHA256:",
                                              "jar verified.", "jar is unsigned.",
                                              "This jar contains unsigned entries"),
                        )

                    for artifact in report["artifacts"]:
                        if artifact["format"] != "aab":
                            continue
                        artifact.update(qualify_debug_aab(
                            plan, execution_plan.output_dir, artifact, run_bundle_tool,
                        ))
                report["status"] = "built"
                if smoke_test:
                    command = _smoke_command(execution_plan, report["artifacts"], python_executable)
                    if command is None:
                        report["smoke_test"] = {"status": "not_run", "reason": "Ten adapter wymaga testu na osobnym urządzeniu lub jawnego scenariusza testowego."}
                    else:
                        # Test from outside the source tree: imports and resources
                        # must resolve from the distribution, not the workspace.
                        try:
                            with tempfile.TemporaryDirectory(prefix="maxkompilator-smoke-") as temp:
                                smoke_env = {"PYTHONIOENCODING": "utf-8"} if execution_plan.format == "zipapp" else None
                                smoke_cwd = Path(temp) / "cwd"
                                smoke_cwd.mkdir()
                                # A foreign working directory alone is not enough:
                                # an apphost still points into a publish tree within
                                # the source checkout. Copy the *whole* runtime first.
                                relocation = None
                                if execution_plan.project.kind == "dotnet":
                                    from .runtime_portability import stage_dotnet_runtime
                                    original_command = list(command)
                                    staged = stage_dotnet_runtime(execution_plan.output_dir, Path(command[0]), Path(temp))
                                    command = [str(staged.executable)]
                                    relocation = {
                                        "mode": "copied_publish_tree",
                                        "source_sha256": staged.source_sha256,
                                        "staged_sha256": staged.staged_sha256,
                                        "copied_files": staged.copied_files,
                                    }
                                outcome = run_command(command, smoke_cwd, event, log,
                                                      timeout=smoke_timeout, extra_env=smoke_env)
                                if relocation is not None:
                                    outcome["source_command"] = original_command
                                    outcome["relocation"] = relocation
                        except Cancelled:
                            report["smoke_test"] = {"status": "cancelled", "reason": "Test uruchomienia anulowano."}
                            raise
                        except (MaxkompilatorError, OSError) as exc:
                            report["smoke_test"] = {"status": "failed", "reason": str(exc)}
                            raise
                        report["smoke_test"] = {"status": "passed" if outcome["returncode"] == 0 else "failed", **outcome}
                        if outcome["returncode"]:
                            raise MaxkompilatorError("Program został zbudowany, ale test uruchomienia zakończył się błędem.")
                log(f"Wynik: {report['status']}; pliki: {len(report['artifacts'])}; test: {report['smoke_test']['status']}")
            except Cancelled as exc:
                report["status"] = "cancelled"
                report["error"] = str(exc)
                log(str(exc))
            except (MaxkompilatorError, OSError, zipfile.BadZipFile) as exc:
                report["status"] = "failed"
                report["error"] = str(exc)
                log(str(exc))
    finally:
        report["finished_at"] = _now()
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        try:
            _write_json_atomic(run_dir / "build-report.json", report)
            _write_json_atomic(output / "build-report.json", report)
        finally:
            lock.unlink(missing_ok=True)
    return report
