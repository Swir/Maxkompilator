"""Inspect project metadata without importing or executing project code."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tomllib

from .models import DetectionError, Project


SUPPORTED_KINDS = ("python", "android", "dotnet")
_IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", ".gradle", ".idea", "build", "dist", "bin", "obj",
    ".work", "target", ".tox", ".mypy_cache", ".pytest_cache",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DetectionError(f"Cannot read project metadata {path}: {exc}") from exc


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return name or "project"


def _within_root(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except (OSError, RuntimeError):
        return False


def _metadata_files(root: Path) -> list[Path]:
    """A bounded, pruned search also handles normal src/Application layouts."""
    result: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        depth = len(current.relative_to(root).parts)
        subdirectories[:] = sorted(
            name for name in subdirectories
            if name not in _IGNORED_DIRECTORIES
            and not (current / name).is_symlink()
            and depth < 3
        )
        for name in sorted(filenames):
            if name.endswith(".csproj") or name in {
                "build.gradle", "build.gradle.kts", "settings.gradle",
                "settings.gradle.kts", "AndroidManifest.xml",
            }:
                candidate = current / name
                if _within_root(candidate, root):
                    result.append(candidate)
    return result


def _python_name(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        if not _within_root(pyproject, root):
            raise DetectionError("pyproject.toml must remain inside the project directory.")
        try:
            data = tomllib.loads(_read_text(pyproject))
        except tomllib.TOMLDecodeError as exc:
            raise DetectionError(f"Invalid pyproject.toml: {exc}") from exc
        project = data.get("project", {})
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            return _safe_name(project["name"])
        tool = data.get("tool", {})
        poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
        if isinstance(poetry, dict) and isinstance(poetry.get("name"), str):
            return _safe_name(poetry["name"])
    return _safe_name(root.name)


def _python_entry(root: Path, entrypoint: str | os.PathLike[str] | None) -> str | None:
    if entrypoint is not None:
        candidate = Path(entrypoint).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if not candidate.is_relative_to(root):
            raise DetectionError("The Python entrypoint must remain inside the project directory.")
        if not candidate.is_file() or candidate.suffix.lower() != ".py":
            raise DetectionError(f"The entrypoint must be an existing .py file: {candidate}")
        return candidate.relative_to(root).as_posix()
    for name in ("__main__.py", "main.py"):
        if (root / name).is_file():
            return _python_entry(root, name)
    # A packaged project can have launchers, maintenance scripts and entry points
    # in metadata. Avoid silently picking a maintenance script as its app.
    if not (root / "pyproject.toml").exists():
        scripts = sorted(path for path in root.glob("*.py") if path.is_file())
        if len(scripts) == 1:
            return _python_entry(root, scripts[0])
    return None


def detect_project(
    path: str | os.PathLike[str],
    *,
    kind: str | None = None,
    entrypoint: str | os.PathLike[str] | None = None,
) -> Project:
    """Detect Python, Android or .NET; ambiguity must be resolved explicitly.

    No project file is imported, subprocess started, dependency installed or
    build script evaluated by this function.
    """
    if kind is not None:
        kind = kind.strip().lower()
        if kind not in SUPPORTED_KINDS:
            raise DetectionError(
                f"Unsupported project kind {kind!r}; choose {', '.join(SUPPORTED_KINDS)}."
            )
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise DetectionError(f"Project path does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() == ".py":
            if kind not in (None, "python"):
                raise DetectionError("A .py file can only use the python adapter.")
            return Project(
                source.parent, "python", _safe_name(source.stem),
                _python_entry(source.parent, entrypoint or source.name),
            )
        if source.suffix.lower() == ".csproj":
            if kind not in (None, "dotnet"):
                raise DetectionError("A .csproj file can only use the dotnet adapter.")
            if entrypoint is not None:
                raise DetectionError("--entry is supported only for Python projects.")
            return Project(source.parent, "dotnet", _safe_name(source.stem), project_file=source.name)
        raise DetectionError("Choose a project directory, a Python .py entrypoint, or a .csproj file.")
    if not source.is_dir():
        raise DetectionError(f"Project path is not a directory or regular file: {source}")

    metadata = _metadata_files(source)
    csprojects = sorted(path for path in metadata if path.suffix.lower() == ".csproj")
    gradle_files = [path for path in metadata if path.name.endswith((".gradle", ".gradle.kts"))]
    has_manifest = any(path.name == "AndroidManifest.xml" for path in metadata)
    has_android_plugin = False
    for gradle in gradle_files:
        text = re.sub(r"/\*.*?\*/", "", _read_text(gradle), flags=re.DOTALL)
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        if re.search(r"[\"']com\.android\.(?:application|library)[\"']", text):
            has_android_plugin = True
            break
    python_markers = ("pyproject.toml", "requirements.txt", "main.py", "__main__.py", "setup.py")
    has_python = any((source / name).is_file() for name in python_markers)
    has_python = has_python or any(path.is_file() for path in source.glob("*.py"))
    candidates: list[str] = []
    if has_python:
        candidates.append("python")
    if gradle_files and (has_manifest or has_android_plugin):
        candidates.append("android")
    if csprojects:
        candidates.append("dotnet")
    if kind is None:
        if not candidates:
            raise DetectionError(
                "No supported project found. Expected Python metadata/scripts, an Android "
                "Gradle project, or a .csproj file."
            )
        if len(candidates) > 1:
            raise DetectionError(
                f"Ambiguous project: found {', '.join(candidates)}. Select one with --kind."
            )
        kind = candidates[0]
    elif kind not in candidates:
        # A custom entrypoint is useful in src layouts without a top-level main.
        if kind != "python" or entrypoint is None:
            raise DetectionError(f"No {kind} project metadata found in {source}.")

    if kind == "python":
        return Project(
            source, kind, _python_name(source), _python_entry(source, entrypoint),
            "pyproject.toml" if (source / "pyproject.toml").is_file() else None,
        )
    if entrypoint is not None:
        raise DetectionError("--entry is supported only for Python projects.")
    if kind == "dotnet":
        if len(csprojects) != 1:
            names = ", ".join(path.relative_to(source).as_posix() for path in csprojects)
            raise DetectionError(
                f"Multiple .csproj files found ({names}). Pass the exact .csproj path."
            )
        csproject = csprojects[0]
        return Project(source, kind, _safe_name(csproject.stem), project_file=csproject.relative_to(source).as_posix())
    project_file = next(
        (path.relative_to(source).as_posix() for path in gradle_files
         if path.parent == source and path.name.startswith("build.")),
        None,
    )
    return Project(source, "android", _safe_name(source.name), project_file=project_file)
