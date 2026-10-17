"""Native PyInstaller plans and explicitly source-based Python zipapps."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import struct
import sys
import tomllib

from ..models import BuildPlan, BuildStep, PlanError, Project, ToolRequirement


def native_target() -> str:
    system = {"Windows": "win", "Linux": "linux", "Darwin": "macos"}.get(platform.system())
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x64", "x86_64": "x64", "x64": "x64",
        "aarch64": "arm64", "arm64": "arm64", "arm64e": "arm64",
        "x86": "x86", "i386": "x86", "i686": "x86", "i586": "x86",
        "armv7l": "arm", "armv8l": "arm",
    }.get(machine)
    if struct.calcsize("P") == 4:
        architecture = {"x64": "x86", "arm64": "arm"}.get(architecture, architecture)
    if system is None or architecture is None:
        raise PlanError(f"Unsupported host platform: {platform.system()} / {machine}.")
    return f"{system}-{architecture}"


def _interpreter_requirement(executable: str, expected_target: str) -> ToolRequirement:
    """Check the selected interpreter itself, not just the planning process."""
    probe = (
        "import json,platform,struct,sys; "
        "system=platform.system(); machine=platform.machine().lower(); bits=struct.calcsize('P')*8; "
        "family={'Windows':'win','Linux':'linux','Darwin':'macos'}.get(system,system.lower()); "
        "cpu={'amd64':'x64','x86_64':'x64','x64':'x64','aarch64':'arm64','arm64':'arm64',"
        "'arm64e':'arm64','x86':'x86','i386':'x86','i686':'x86','i586':'x86',"
        "'armv7l':'arm','armv8l':'arm'}.get(machine,machine); "
        "cpu=({'x64':'x86','arm64':'arm'}.get(cpu,cpu) if bits==32 else cpu); "
        "actual=family+'-'+cpu; expected=sys.argv[1]; "
        "expected_bits=64 if expected.rsplit('-',1)[-1] in ('x64','arm64') else 32; "
        "print(json.dumps({'system':system,'machine':machine,'pointer_bits':bits,"
        "'target':actual,'expected_target':expected})); "
        "sys.exit(0 if actual==expected and bits==expected_bits else 1)"
    )
    return ToolRequirement(
        "Python target", (executable, "-c", probe, expected_target),
        f"Select a Python interpreter for {expected_target}; its operating system and CPU architecture must match the build target.",
    )


def normalize_target(target: str) -> str:
    host = native_target()
    if target == "native":
        return host
    parts = target.lower().split("-", 1)
    family = {
        "windows": "win", "win": "win", "linux": "linux",
        "macos": "macos", "osx": "macos", "darwin": "macos", "mac": "macos",
    }.get(parts[0])
    if family is None:
        raise PlanError(f"Unsupported native target {target!r}; use win-x64, linux-x64, macos-arm64 or native.")
    architecture = parts[1] if len(parts) == 2 else host.split("-", 1)[1]
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(architecture, architecture)
    if architecture not in {"x64", "x86", "arm64", "arm"}:
        raise PlanError(f"Unsupported target architecture: {architecture}.")
    return f"{family}-{architecture}"


def _entry(project: Project) -> Path:
    if not project.entrypoint:
        raise PlanError("A Python entrypoint is required. Select an existing script with --entry.")
    root = project.root.resolve()
    path = (root / project.entrypoint).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() != ".py":
        raise PlanError("Python entrypoint must be an existing .py file inside the project directory.")
    return path


def _data_arguments(project: Project, output_dir: Path) -> tuple[str, ...]:
    config = project.root / "maxkompilator.toml"
    if not config.is_file():
        return ()
    if not config.resolve().is_relative_to(project.root.resolve()):
        raise PlanError("maxkompilator.toml must remain inside the project directory.")
    try:
        with config.open("rb") as stream:
            settings = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PlanError(f"Cannot read maxkompilator.toml: {exc}") from exc
    python_settings = settings.get("python", {})
    if not isinstance(python_settings, dict):
        raise PlanError("[python] must be a table in maxkompilator.toml.")
    data = python_settings.get("data", [])
    if not isinstance(data, list) or any(not isinstance(item, str) or not item for item in data):
        raise PlanError("[python].data must be a list of relative file or directory paths.")
    root = project.root.resolve()
    arguments: list[str] = []
    for item in data:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise PlanError(f"Python data must use a path inside the project directory: {item}")
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.exists():
            raise PlanError(f"Python data does not exist or escapes the project directory: {item}")
        if source.is_dir():
            if source == root or output_dir.is_relative_to(source):
                raise PlanError("Choose specific data folders which do not contain the build output directory.")
            # Explicit directories may contain symlinks; reject escapes before
            # delegating their recursive collection to PyInstaller.
            for directory, directories, files in os.walk(source, followlinks=False):
                for name in directories + files:
                    candidate = Path(directory) / name
                    if candidate.is_symlink():
                        raise PlanError(f"Python data directories must not contain symlinks: {candidate}")
        if not source.is_file() and not source.is_dir():
            raise PlanError(f"Python data must be a regular file or directory: {item}")
        relative_source = source.relative_to(root)
        destination = relative_source.as_posix() if source.is_dir() else relative_source.parent.as_posix()
        if ":" in destination or (os.name != "nt" and ":" in str(source)):
            raise PlanError("Python data paths containing ':' cannot be passed to PyInstaller.")
        arguments.extend(("--add-data", f"{source}:{destination}"))
    return tuple(arguments)


def create_python_plan(
    project: Project,
    target: str,
    format: str | None,
    output_dir: Path,
    python_executable: str | os.PathLike[str] | None,
) -> BuildPlan:
    entry = _entry(project)
    executable = str(python_executable or sys.executable)
    selected_format = format or "executable"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", project.name):
        raise PlanError("The project name must contain only letters, numbers, '.', '_' and '-'.")
    # Validate declared assets for either format, even though zipapp packages
    # source files itself and does not use PyInstaller's --add-data arguments.
    data_arguments = _data_arguments(project, output_dir)
    if selected_format == "zipapp":
        if target not in {"native", "python", "any", "portable"}:
            raise PlanError("zipapp is Python source packaging; use --target python or native.")
        return BuildPlan(
            project, "python", "zipapp", output_dir,
            artifact_patterns=(f"{project.name}.pyz",),
            notes=(
                "A .pyz requires a compatible Python installation on the destination computer.",
                "Third-party dependencies and a Python runtime are not bundled. Install dependencies separately.",
                "Packaging does not make operating-system-specific code portable.",
            ),
            internal_builder="zipapp",
        )
    if selected_format not in {"executable", "exe"}:
        raise PlanError("The Python adapter supports executable (PyInstaller) and zipapp formats.")
    selected_target = normalize_target(target)
    host_target = native_target()
    if selected_target != host_target:
        raise PlanError(
            f"PyInstaller cannot cross-build {selected_target} from {host_target}. "
            "Use a worker and Python interpreter matching the target OS and architecture."
        )
    if selected_format == "exe" and not selected_target.startswith("win-"):
        raise PlanError(".exe output requires a Windows worker. Use executable for the native system.")
    command = (
        executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--distpath", str(output_dir), "--workpath", str(output_dir / ".work"),
        "--specpath", str(output_dir / ".work"), "--name", project.name,
        *data_arguments, str(entry),
    )
    return BuildPlan(
        project, selected_target, "executable", output_dir,
        steps=(BuildStep("Build native application with PyInstaller", command, project.root),),
        requirements=(_interpreter_requirement(executable, selected_target), ToolRequirement(
            "PyInstaller", (executable, "-m", "PyInstaller", "--version"),
            f"Install PyInstaller in the selected interpreter: {executable} -m pip install pyinstaller",
        ),),
        artifact_patterns=(f"{project.name}/**/*",),
        notes=(
            "Keep the whole output application directory together; it includes runtime files and dependencies.",
            "The selected Python interpreter and native dependencies must match the target architecture.",
        ),
    )
