"""Bounded probes of explicitly required tools."""

from __future__ import annotations

import errno
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

from .models import BuildPlan, ToolRequirement


_DLL_DIRECTORY_LOCK = threading.Lock()


def external_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy the environment, removing a frozen launcher's library search paths."""
    child_env = dict(os.environ if env is None else env)
    if not getattr(sys, "frozen", False):
        return child_env
    if sys.platform.startswith("linux"):
        if "LD_LIBRARY_PATH_ORIG" in child_env:
            child_env["LD_LIBRARY_PATH"] = child_env["LD_LIBRARY_PATH_ORIG"]
        else:
            child_env.pop("LD_LIBRARY_PATH", None)
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        bundle_path = os.path.normcase(os.path.realpath(bundle))

        def outside_bundle(entry: str) -> bool:
            if not entry:
                return True
            candidate = os.path.normcase(os.path.realpath(entry.strip('"')))
            try:
                return os.path.commonpath((bundle_path, candidate)) != bundle_path
            except ValueError:  # Different Windows drives cannot be descendants.
                return True

        variables = ("PATH", "DYLD_LIBRARY_PATH") if sys.platform == "darwin" else ("PATH",)
        for variable in variables:
            if variable in child_env:
                child_env[variable] = os.pathsep.join(
                    entry for entry in child_env[variable].split(os.pathsep) if outside_bundle(entry)
                )
    return child_env


@contextmanager
def _external_dll_directory():
    """Reset the process-wide Windows DLL directory only while creating a child."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        yield
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel32.GetDllDirectoryW
    get_directory.argtypes = [wintypes.DWORD, wintypes.LPWSTR]
    get_directory.restype = wintypes.DWORD
    set_directory = kernel32.SetDllDirectoryW
    set_directory.argtypes = [wintypes.LPCWSTR]
    set_directory.restype = wintypes.BOOL
    # SetDllDirectory affects all threads. Restore before the child is awaited.
    with _DLL_DIRECTORY_LOCK:
        length = get_directory(0, None)
        previous = None
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            copied = get_directory(len(buffer), buffer)
            if copied >= len(buffer):
                raise OSError("Katalog DLL zmienił się podczas przygotowania procesu.")
            previous = buffer.value
        if not set_directory(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            if not set_directory(previous):
                raise ctypes.WinError(ctypes.get_last_error())


def spawn_external(command, *, env: Mapping[str, str] | None = None,
                   extra_env: Mapping[str, str] | None = None, **kwargs) -> subprocess.Popen:
    """Start an external tool without leaking the frozen application's runtime."""
    child_env = external_environment(env)
    # Explicit per-command settings (UTF-8, caches, etc.) override inherited state.
    child_env.update(extra_env or {})
    with _external_dll_directory():
        return subprocess.Popen(command, env=child_env, **kwargs)


def _darwin_group_has_finished(pgid: int) -> bool:
    """Confirm a Darwin EPERM refers only to absent or zombie group members."""
    try:
        snapshot = subprocess.run(
            ["/bin/ps", "-axo", "pid=,pgid=,stat=,uid="],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="ascii", timeout=1.0, check=False,
            env=external_environment(),
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False
    rows = snapshot.stdout.splitlines()
    if snapshot.returncode or not rows:
        return False
    for row in rows:
        fields = row.split()
        if len(fields) != 4:
            return False
        try:
            pid, group, uid = int(fields[0]), int(fields[1]), int(fields[3])
        except ValueError:
            return False
        if min(pid, group, uid) < 0:
            return False
        # Check every UID: an unkillable live member must remain an error.
        if group == pgid and not fields[2].startswith("Z"):
            return False
    return True


def _signal_process_group(pgid: int, sig: int) -> bool:
    """Return false only when the group no longer contains running processes."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        # Darwin can report EPERM for a process group left with only zombies.
        # A failed inspection must not conceal a real permission failure.
        if sys.platform == "darwin" and exc.errno == errno.EPERM and _darwin_group_has_finished(pgid):
            return False
        raise
    return True


def stop_process(process: subprocess.Popen, *, grace: float = 2.0) -> None:
    """Stop the process group created for this task, including child tools."""
    if os.name == "nt":
        if process.poll() is not None:
            return
        # /T targets only this process and its descendants, not other builds.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        group_exists = _signal_process_group(process.pid, signal.SIGTERM)
        # The group can outlive its original process. Waiting only for the
        # parent would leave a compiler's child running after cancellation.
        deadline = time.monotonic() + grace
        while group_exists and time.monotonic() < deadline:
            process.poll()
            group_exists = _signal_process_group(process.pid, 0)
            if group_exists:
                time.sleep(0.03)
        if group_exists:
            _signal_process_group(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def process_options() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def probe_tool(requirement: ToolRequirement, *, timeout: float = 15.0) -> dict:
    command = requirement.command
    if command and command[0] == "java" and os.environ.get("JAVA_HOME"):
        java = Path(os.environ["JAVA_HOME"]) / "bin" / ("java.exe" if os.name == "nt" else "java")
        command = (str(java), *command[1:])
    result = {"name": requirement.name, "command": list(command),
              "available": False, "version": "", "hint": requirement.hint}
    # A temporary cwd prevents a project's java.py or PyInstaller.py from
    # shadowing a tool during the environment check.
    with tempfile.TemporaryDirectory(prefix="maxkompilator-probe-") as temp:
        try:
            process = spawn_external(command, cwd=temp, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, **process_options())
            try:
                output, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                stop_process(process)
                result["error"] = f"Przekroczono limit sprawdzania narzędzia ({timeout:g} s)."
                return result
            text = output.decode("utf-8", errors="replace").strip()
            result["available"] = process.returncode == 0
            result["version"] = text[:2000]
            if requirement.expected_version is not None:
                result["expected_version"] = requirement.expected_version
                version_match = re.search(r"(?<![\w.])" + re.escape(requirement.expected_version) + r"(?![\w.])", text)
                if process.returncode == 0 and version_match is None:
                    result["available"] = False
                    result["error"] = f"Expected pinned version {requirement.expected_version}; received {text[:200]}."
                    result["hint"] = result["error"] + " " + requirement.hint
            if process.returncode:
                result["error"] = f"Narzędzie zakończyło sprawdzenie kodem {process.returncode}."
        except OSError as exc:
            result["error"] = str(exc)
    return result


def _android_sdk(plan: BuildPlan) -> dict:
    paths = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")]
    properties = plan.project.root / "local.properties"
    if properties.is_file():
        for line in properties.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("sdk.dir="):
                raw = line.split("=", 1)[1].strip().replace("\\:", ":").replace("\\\\", "\\")
                candidate = Path(raw).expanduser()
                paths.append(str(candidate if candidate.is_absolute() else plan.project.root / candidate))
    for raw in paths:
        if raw:
            path = Path(raw).expanduser()
            if (path / "platforms").is_dir() and (path / "build-tools").is_dir():
                return {"name": "Android SDK", "available": True, "version": str(path), "hint": ""}
    return {"name": "Android SDK", "available": False, "version": "",
            "hint": "Skonfiguruj SDK przez ANDROID_HOME lub sdk.dir w local.properties; wymagane platforms i build-tools."}


def check_environment(plan: BuildPlan) -> dict:
    checks = [probe_tool(item) for item in plan.requirements]
    if plan.project.kind == "android":
        checks.append(_android_sdk(plan))
    return {"ready": all(item["available"] for item in checks), "checks": checks}
