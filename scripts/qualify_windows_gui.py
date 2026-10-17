#!/usr/bin/env python3
"""Qualify the actual portable Windows desktop EXE, then close and reopen it.

The complete bundle is copied outside the checkout into a path with spaces and
Unicode. Both GUI launches run from an unrelated directory without PYTHONPATH,
PYTHONHOME or checkout entries in PATH. The bundled diagnostic mode drives real
Qt controls and verifies the OS identity of every compiled console worker.

The hosted Windows runner still has Python for the generated PYZ's runtime.
This automated offscreen gate is not a clean-machine or manual Windows 11 test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHECKS = {
    "frozen_gui_imports_and_portable_worker_present",
    "initial_window_icon_and_controls",
    "inspect_and_plan_unicode_path_auto_defaults",
    "environment_doctor_and_smoke_flag_scoping",
    "zipapp_build_real_runtime_and_persisted_report",
    "open_results_and_copy_log_buttons",
    "cancel_button_stops_running_build",
    "cancelled_worker_and_descendant_are_stopped",
    "all_five_tasks_used_verified_frozen_console_worker",
}


def require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def executable_info(path: Path, *, subsystem: int) -> dict[str, Any]:
    """Confirm x64 PE type and GUI/console subsystem from the actual file."""
    require(path.is_file(), "Executable is missing: " + str(path))
    with path.open("rb") as stream:
        dos = stream.read(64)
        require(len(dos) == 64 and dos[:2] == b"MZ", "Executable is not a PE file: " + str(path))
        stream.seek(struct.unpack_from("<I", dos, 0x3C)[0])
        header = stream.read(96)
    require(len(header) >= 94 and header[:4] == b"PE\0\0", "Invalid PE header: " + str(path))
    machine = struct.unpack_from("<H", header, 4)[0]
    optional_magic = struct.unpack_from("<H", header, 24)[0]
    actual_subsystem = struct.unpack_from("<H", header, 24 + 68)[0]
    require(machine == 0x8664 and optional_magic == 0x20B, "The Windows x64 bundle contains another architecture: " + str(path))
    require(actual_subsystem == subsystem, "Unexpected GUI/console subsystem: " + str(path))
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256(path), "format": "PE", "architecture": "x64", "subsystem": "windows_gui" if subsystem == 2 else "windows_console"}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def detached_environment() -> dict[str, str]:
    removed = {"PYTHONPATH", "PYTHONHOME", "__PYVENV_LAUNCHER__", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"}
    environment = {name: value for name, value in os.environ.items() if name.upper() not in removed}
    path_name = next((name for name in environment if name.upper() == "PATH"), "PATH")
    entries = []
    for entry in environment.get(path_name, "").split(os.pathsep):
        if not entry:
            continue
        try:
            if Path(entry).resolve().is_relative_to(REPO_ROOT):
                continue
        except (OSError, ValueError):
            continue
        entries.append(entry)
    environment[path_name] = os.pathsep.join(entries)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def validate_run(report: dict[str, Any], *, run_id: str, pid: int, executable: Path, cwd: Path, screenshot: Path, icon_sha256: str) -> None:
    require(report.get("schema_version") == 1, "Unknown GUI qualification report schema")
    require(report.get("status") == "passed", "The packaged GUI harness failed: " + str(report.get("error")))
    require(report.get("run_id") == run_id and report.get("process_id") == pid, "The report does not belong to this newly launched GUI process")
    require(report.get("frozen") is True and report.get("mode") == "packaged", "The report came from a source GUI")
    require(Path(report.get("executable", "")).resolve() == executable, "The report came from an unexpected executable")
    require(Path(report.get("working_directory", "")).resolve() == cwd, "The GUI was not launched from the unrelated working directory")
    require(report.get("qt_platform") == "offscreen", "The report did not identify the requested offscreen backend")
    require(report.get("window_closed") is True, "The GUI window did not close cleanly")
    require(EXPECTED_CHECKS <= set(report.get("checks", [])), "The packaged GUI report is missing workflow checks")
    bundle_root = executable.parent / "_internal"
    require(Path(report.get("bundle_root", "")).resolve() == bundle_root, "The GUI loaded an unexpected portable runtime")
    icon = report.get("icon") or {}
    require(icon.get("sha256") == icon_sha256 and Path(icon.get("path", "")).resolve().is_relative_to(bundle_root), "The GUI icon does not match the packaged PNG asset")
    modules = report.get("module_files", {})
    require(set(modules) == {"gui", "qualification"}, "Missing bundled module origins")
    require(all(Path(path).resolve().is_relative_to(bundle_root) for path in modules.values()), "GUI modules were rescued by files outside the relocated bundle")
    search_path = report.get("python_search_path", [])
    require(search_path and all(path and Path(path).resolve().is_relative_to(bundle_root) for path in search_path), "The frozen import path contains locations outside its own runtime")
    processes = report.get("worker_processes", [])
    require([item.get("action") for item in processes] == ["inspect", "plan", "doctor", "build", "build"], "Unexpected GUI worker sequence")
    require([item.get("exit_code") for item in processes] == [0, 0, 0, 0, 130], "Unexpected compiled worker exit codes")
    worker = executable.with_name("MaxkompilatorCLI.exe")
    for item in processes:
        require(item.get("pid", 0) > 0 and item.get("exit_status") == "NormalExit", "A compiled worker did not exit normally")
        require(Path(item.get("program", "")).resolve() == worker and Path(item.get("image_path", "")).resolve() == worker, "A task used a source worker or compatibility fallback")
        require(item.get("arguments", [])[:2] == ["--cli", item["action"]], "A task bypassed the real compiled CLI protocol")
        require(Path(item.get("working_directory", "")).resolve().is_relative_to(bundle_root), "A worker depended on a checkout working directory")
    require(screenshot.is_file() and screenshot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "A launch did not save a valid PNG screenshot")
    require(Path(report.get("screenshot", "")).resolve() == screenshot, "The screenshot path does not match this launch")


def run_gui(executable: Path, *, cwd: Path, environment: dict[str, str], output: Path, label: str, timeout: float, held_processes: list[subprocess.Popen], icon_sha256: str) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    report_path = output / (label + ".json")
    screenshot = output / (label + ".png")
    # A previous report cannot qualify a later launch that crashes before writing.
    report_path.unlink(missing_ok=True)
    screenshot.unlink(missing_ok=True)
    command = [str(executable), "--qualify-gui", "--require-frozen-worker", "--run-id", run_id,
               "--report", str(report_path), "--screenshot", str(screenshot), "--timeout", str(timeout)]
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    held_processes.append(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout + 30)
    except subprocess.TimeoutExpired:
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        finally:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        (output / (label + ".stdout.log")).write_bytes(stdout)
        (output / (label + ".stderr.log")).write_bytes(stderr)
        raise RuntimeError(label + ": the packaged GUI exceeded its external deadline")
    (output / (label + ".stdout.log")).write_bytes(stdout)
    (output / (label + ".stderr.log")).write_bytes(stderr)
    launch = {"run_id": run_id, "process_id": process.pid, "return_code": process.returncode,
              "duration_seconds": round(time.monotonic() - started, 3), "report": str(report_path), "screenshot": str(screenshot)}
    write_json(output / (label + ".process.json"), launch)
    require(process.returncode == 0, label + ": the real GUI executable returned " + str(process.returncode))
    require(report_path.is_file(), label + ": the real GUI executable did not write its report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    validate_run(report, run_id=run_id, pid=process.pid, executable=executable, cwd=cwd, screenshot=screenshot, icon_sha256=icon_sha256)
    launch.update({"status": "passed", "checks": report["checks"], "worker_count": len(report["worker_processes"]), "screenshot_sha256": sha256(screenshot)})
    print(label + ": PASS — actual frozen GUI, five verified frozen workers, build/run/cancel and clean close", flush=True)
    return launch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="dist/Maxkompilator/Maxkompilator.exe")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "build" / "packaged-gui", help="Qualification reports and screenshots directory")
    parser.add_argument("--timeout", type=float, default=90.0, help="Each GUI launch's internal deadline in seconds")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("This gate must run against a real Windows desktop bundle on Windows")
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be greater than 0 and at most 600 seconds")
    source_executable = args.executable.expanduser().resolve()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "scope": "Automated offscreen qualification of a relocated, fully frozen Windows x64 GUI and its compiled console worker, with two independent GUI launches.",
        "limitations": ["The hosted runner has Python installed for the generated PYZ runtime.", "This is not a manual interactive Windows 11 test or a clean machine without Python."],
        "executables": {},
        "launches": [],
        "checks": [],
        "error": None,
    }
    held_processes: list[subprocess.Popen] = []
    try:
        result["executables"] = {
            "desktop": executable_info(source_executable, subsystem=2),
            "worker": executable_info(source_executable.with_name("MaxkompilatorCLI.exe"), subsystem=3),
        }
        result["checks"].append("x64_pe_gui_and_console_subsystems")
        icon = source_executable.parent / "_internal" / "maxkompilator" / "assets" / "maxkompilator.png"
        require(icon.is_file(), "The portable PNG icon is missing")
        result["icon"] = {"path": str(icon), "sha256": sha256(icon), "size_bytes": icon.stat().st_size}
        with tempfile.TemporaryDirectory(prefix="maxkompilator-packaged-") as temporary:
            temporary_root = Path(temporary).resolve()
            require(not temporary_root.is_relative_to(REPO_ROOT), "The relocation directory must be outside the source checkout")
            portable = temporary_root / "portable ze spacją Łódź" / "Maxkompilator"
            shutil.copytree(source_executable.parent, portable)
            executable = portable / source_executable.name
            cwd = temporary_root / "unrelated working directory"
            cwd.mkdir()
            environment = detached_environment()
            result["environment"] = {"relocated_bundle": str(portable), "working_directory": str(cwd),
                                     "pythonpath_removed": not any(name.upper() == "PYTHONPATH" for name in environment),
                                     "pythonhome_removed": not any(name.upper() == "PYTHONHOME" for name in environment),
                                     "external_python": shutil.which("python", path=next((value for name, value in environment.items() if name.upper() == "PATH"), ""))}
            for label in ("first-launch", "reopened"):
                result["launches"].append(run_gui(executable, cwd=cwd, environment=environment, output=output, label=label, timeout=args.timeout, held_processes=held_processes, icon_sha256=result["icon"]["sha256"]))
            require(result["launches"][0]["process_id"] != result["launches"][1]["process_id"], "Reopen must create a second independent GUI process")
            require(sha256(executable) == result["executables"]["desktop"]["sha256"], "The relocated GUI executable changed during qualification")
            require(sha256(executable.with_name("MaxkompilatorCLI.exe")) == result["executables"]["worker"]["sha256"], "The relocated console worker changed during qualification")
            result["checks"].extend(["relocated_bundle_outside_checkout", "frozen_module_and_process_origins", "real_gui_workflow_and_cancellation", "clean_close_and_independent_reopen"])
        result["status"] = "passed"
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    destination = output / "qualification.json"
    write_json(destination, result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
