"""Versioned JSON-lines worker for an authenticated stdio/SSH connection.

The operator chooses the workspace. Requests select existing projects beneath
it; no command or arbitrary host path is accepted from the client. Building
still executes trusted project code and is not an OS isolation boundary.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import threading

from . import __version__
from .adapters import create_plan
from .adapters.registry import API_VERSION, adapter_kinds
from .adapters.python_adapter import native_target
from .config import load_config
from .detection import detect_project
from .engine import execute_build
from .models import MaxkompilatorError

PROTOCOL = 1
MAX_REQUEST = 65536
MAX_CHUNK = 256 * 1024
_ID = re.compile(r"[a-f0-9]{32}\Z")


def relative_path(raw: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or len(raw) > 1024 or "\\" in raw or ":" in raw:
        raise ValueError("Expected a bounded relative POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise ValueError("Path traversal and absolute paths are not accepted")
    for part in path.parts:
        if any(ord(c) < 32 for c in part) or part.endswith((' ', '.')) or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part):
            raise ValueError("Reserved or ambiguous path component")
    return path


def capabilities() -> dict:
    return {"protocol": PROTOCOL, "application_version": __version__, "adapter_api": API_VERSION,
            "adapters": list(adapter_kinds()), "target": native_target(), "system": platform.system(),
            "python_version": platform.python_version(), "max_chunk_bytes": MAX_CHUNK,
            "operations": ["capabilities", "build", "cancel", "fetch"],
            "tool_paths": {tool: shutil.which(tool) for tool in ("dotnet", "java", "adb")},
            "tool_paths_are_probes": False}


def serve(workspace: Path) -> int:
    root = workspace.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Worker workspace must be an existing directory")
    jobs_root = root / ".maxkompilator-remote"
    if jobs_root.is_symlink():
        raise ValueError("Worker output root must not be a symlink")
    lock = threading.Lock()
    active: dict = {}
    completed: dict[str, dict] = {}
    seen: set[str] = set()

    def emit(request_id: str, event: str, payload: dict) -> None:
        with lock:
            try:
                print(json.dumps({"protocol": PROTOCOL, "id": request_id, "event": event, **payload}, ensure_ascii=False), flush=True)
            except (BrokenPipeError, OSError):
                if active:
                    active["cancel"].set()

    def build(request: dict, project_path: Path, job: Path, cancelled: threading.Event) -> None:
        request_id = request["id"]
        try:
            config = load_config(project_path)
            project_config, build_config = config.get("project", {}), config.get("build", {})
            project = detect_project(project_path, kind=request.get("kind") or project_config.get("kind"),
                                     entrypoint=request.get("entry") or project_config.get("entry"))
            plan = create_plan(project, target=request.get("target") or build_config.get("target", "native"),
                               format=request.get("format") or build_config.get("format"), output_dir=job / "output")
            report = execute_build(plan, cancel_event=cancelled, smoke_test=request.get("smoke_test", False),
                                   timeout=request.get("timeout", 1800),
                                   on_log=lambda line: emit(request_id, "log", {"text": line[:4096]}))
            artifacts = []
            if report["status"] == "built":
                for item in report["artifacts"]:
                    path = Path(item["path"])
                    resolved = path.resolve(strict=True)
                    if not path.is_relative_to(job) or not resolved.is_relative_to(job) or not path.is_file():
                        raise ValueError("Build artifact escaped its job directory")
                    artifacts.append({"id": path.relative_to(job).as_posix(), "size_bytes": item["size_bytes"],
                                      "sha256": item["sha256"], "mode": stat.S_IMODE(path.stat().st_mode) & 0o755})
                report_path = Path(report["report_path"])
                artifacts.append({"id": report_path.relative_to(job).as_posix(), "size_bytes": report_path.stat().st_size,
                                  "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()})
                completed[request_id] = {"root": job, "artifacts": {item["id"]: item for item in artifacts}}
            emit(request_id, "result", {"result": {"job_id": request_id, "status": report["status"],
                 "error": report["error"], "smoke_status": report["smoke_test"]["status"], "artifacts": artifacts}})
        except (OSError, ValueError, MaxkompilatorError) as exc:
            emit(request_id, "error", {"error": str(exc)})

    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_REQUEST + 1)
            if not line:
                break
            request_id = ""
            try:
                if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
                    raise ValueError("Request exceeds the protocol limit")
                request = json.loads(line)
                if not isinstance(request, dict) or request.get("protocol") != PROTOCOL:
                    raise ValueError("Unsupported protocol version")
                request_id = request.get("id", "")
                if not isinstance(request_id, str) or not _ID.fullmatch(request_id) or request_id in seen:
                    raise ValueError("Request ID must be a new 32-character hexadecimal ID")
                if len(seen) >= 100000:
                    raise ValueError("Connection request limit reached")
                seen.add(request_id)
                operation = request.get("operation")
                if operation == "capabilities":
                    emit(request_id, "result", {"result": capabilities()})
                elif operation == "cancel":
                    if not active or request.get("job_id") != active["id"] or not active["thread"].is_alive():
                        raise ValueError("No matching active job")
                    active["cancel"].set()
                    emit(request_id, "result", {"result": {"cancellation_requested": True}})
                elif operation == "build":
                    if active and active["thread"].is_alive():
                        raise ValueError("Worker is already building a job")
                    if len(completed) >= 64:
                        raise ValueError("Connection completed-job limit reached")
                    if set(request) - {"protocol", "id", "operation", "project", "kind", "entry", "target", "format", "smoke_test", "timeout"}:
                        raise ValueError("Unknown build fields")
                    for key in ("kind", "entry", "target", "format"):
                        if request.get(key) is not None and (not isinstance(request[key], str) or len(request[key]) > 1024):
                            raise ValueError(f"Invalid {key}")
                    if type(request.get("smoke_test", False)) is not bool:
                        raise ValueError("smoke_test must be boolean")
                    duration = request.get("timeout", 1800)
                    if type(duration) not in {int, float} or not 0 < duration <= 3600:
                        raise ValueError("Build timeout must be between 0 and 3600 seconds")
                    relative = relative_path(request.get("project"))
                    project_path = (root / relative).resolve(strict=True)
                    if not project_path.is_relative_to(root) or project_path.is_relative_to(jobs_root):
                        raise ValueError("Project escaped the configured workspace")
                    job = jobs_root / request_id
                    job.mkdir(parents=True, exist_ok=False)
                    if not job.resolve().is_relative_to(root):
                        raise ValueError("Job directory escaped the workspace")
                    cancel = threading.Event()
                    thread = threading.Thread(target=build, args=(request, project_path, job, cancel), daemon=True)
                    active = {"id": request_id, "cancel": cancel, "thread": thread}
                    thread.start()
                elif operation == "fetch":
                    job = completed.get(request.get("job_id"))
                    artifact_id = request.get("artifact_id")
                    if job is None or not isinstance(artifact_id, str) or artifact_id not in job["artifacts"]:
                        raise ValueError("Unknown successful-job artifact")
                    path = job["root"] / relative_path(artifact_id)
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(job["root"]) or not path.is_file():
                        raise ValueError("Artifact escaped its job directory")
                    offset, size = request.get("offset", 0), request.get("size", MAX_CHUNK)
                    if type(offset) is not int or offset < 0 or type(size) is not int or not 0 < size <= MAX_CHUNK:
                        raise ValueError("Invalid artifact chunk range")
                    with path.open("rb") as stream:
                        stream.seek(offset)
                        chunk = stream.read(size)
                    emit(request_id, "result", {"result": {"offset": offset, "data": base64.b64encode(chunk).decode("ascii")}})
                else:
                    raise ValueError("Unknown worker operation")
            except (OSError, ValueError, TypeError) as exc:
                emit(request_id, "error", {"error": str(exc)})
                if len(line) > MAX_REQUEST:
                    break
    finally:
        if active and active["thread"].is_alive():
            active["cancel"].set()
            active["thread"].join(timeout=15)
    return 0
