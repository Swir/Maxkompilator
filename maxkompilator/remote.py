"""Authenticated SSH transport and verified artifact downloads for worker v1."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shlex
import subprocess
import threading
import time
import uuid

from .environment import process_options, spawn_external, stop_process
from .worker import MAX_CHUNK, PROTOCOL, relative_path


class WorkerClient:
    def __init__(self, command: list[str], *, cwd: Path | None = None):
        self.process = spawn_external(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, **process_options())
        self.messages: queue.Queue = queue.Queue()
        self.stderr_tail: list[str] = []
        self.ignored_ids: set[str] = set()

        def read():
            try:
                while True:
                    line = self.process.stdout.readline(2 * 1024 * 1024)
                    if not line:
                        break
                    if not line.endswith(b"\n"):
                        raise ValueError("Worker response exceeds the protocol limit")
                    self.messages.put(json.loads(line))
            except Exception as exc:
                self.messages.put(exc)
            finally:
                self.messages.put(EOFError("Worker connection closed"))

        def drain_errors():
            for line in iter(self.process.stderr.readline, b""):
                self.stderr_tail.append(line.decode("utf-8", errors="replace")[-4096:])
                del self.stderr_tail[:-20]

        self.reader = threading.Thread(target=read, daemon=True)
        self.errors = threading.Thread(target=drain_errors, daemon=True)
        self.reader.start()
        self.errors.start()

    @classmethod
    def ssh(cls, host: str, workspace: str, *, python: str = "python3") -> WorkerClient:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,253}", host):
            raise ValueError("Use a configured SSH host alias or user@hostname")
        if any("\n" in value or "\r" in value for value in (workspace, python)):
            raise ValueError("SSH arguments cannot contain newlines")
        remote = shlex.join([python, "-m", "maxkompilator", "worker", "--workspace", workspace])
        return cls(["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", host, remote])

    def _send(self, operation: str, fields: dict) -> str:
        request_id = uuid.uuid4().hex
        payload = json.dumps({"protocol": PROTOCOL, "id": request_id, "operation": operation, **fields}).encode("utf-8") + b"\n"
        if len(payload) > 65536:
            raise ValueError("Request exceeds protocol limit")
        self.process.stdin.write(payload)
        self.process.stdin.flush()
        return request_id

    def request(self, operation: str, *, wait_timeout: float = 60, on_log=None, cancel_event=None, **fields) -> dict:
        request_id = self._send(operation, fields)
        deadline = time.monotonic() + wait_timeout
        cancel_id = None
        while True:
            if time.monotonic() > deadline:
                self.close()
                raise TimeoutError("Worker response timed out; connection closed and job cancelled")
            if cancel_event is not None and cancel_event.is_set() and cancel_id is None and operation == "build":
                cancel_id = self._send("cancel", {"job_id": request_id})
                self.ignored_ids.add(cancel_id)
            try:
                message = self.messages.get(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if isinstance(message, Exception):
                raise RuntimeError(str(message) + ": " + "".join(self.stderr_tail)) from message
            if not isinstance(message, dict) or message.get("protocol") != PROTOCOL:
                raise ValueError("Invalid worker protocol response")
            if message.get("id") in self.ignored_ids:
                self.ignored_ids.discard(message["id"])
                continue
            if message.get("id") != request_id:
                raise ValueError("Worker response belongs to a different request")
            if message.get("event") == "log":
                if on_log:
                    on_log(message["text"])
            elif message.get("event") == "error":
                raise ValueError(message["error"])
            elif message.get("event") == "result":
                return message["result"]
            else:
                raise ValueError("Unknown worker event")

    def download(self, result: dict, destination: Path) -> list[dict]:
        if result.get("status") != "built":
            raise ValueError("Only successful-job artifacts can be downloaded")
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=False)
        receipts = []
        for artifact in result["artifacts"]:
            relative = relative_path(artifact["id"])
            target = destination / relative
            size = artifact["size_bytes"]
            if type(size) is not int or not 0 <= size <= 2 * 1024**3:
                raise ValueError("Invalid remote artifact size")
            mode = artifact.get('mode', 0o644)
            if type(mode) is not int or mode < 0 or mode & ~0o755:
                raise ValueError('Invalid artifact permissions')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.parent.resolve().is_relative_to(destination):
                raise ValueError("Download escaped its destination")
            temporary = target.with_name(target.name + ".part")
            digest = hashlib.sha256()
            try:
                with temporary.open("xb") as stream:
                    offset = 0
                    while offset < size:
                        requested = min(MAX_CHUNK, size - offset)
                        chunk = self.request("fetch", job_id=result["job_id"], artifact_id=artifact["id"], offset=offset, size=requested)
                        data = base64.b64decode(chunk["data"], validate=True)
                        if chunk.get("offset") != offset or len(data) != requested:
                            raise ValueError("Truncated or misordered artifact chunk")
                        stream.write(data)
                        digest.update(data)
                        offset += len(data)
                if digest.hexdigest() != artifact["sha256"]:
                    raise ValueError("Remote artifact checksum mismatch")
                if target.exists():
                    raise ValueError("Duplicate remote artifact name")
                if os.name != 'nt':
                    temporary.chmod(mode)
                os.replace(temporary, target)
                receipts.append({**artifact, "local_path": str(target), "checksum_verified": True})
            finally:
                temporary.unlink(missing_ok=True)
        return receipts

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            stop_process(self.process)
        self.reader.join(timeout=2)
        self.errors.join(timeout=2)
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
