"""Small, serializable contracts shared by the CLI and build adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any


class MaxkompilatorError(ValueError):
    """An actionable input, configuration, or build error."""


class DetectionError(MaxkompilatorError):
    pass


class PlanError(MaxkompilatorError):
    pass


@dataclass(frozen=True)
class Project:
    root: Path
    kind: str
    name: str
    entrypoint: str | None = None
    project_file: str | None = None


@dataclass(frozen=True)
class ToolRequirement:
    name: str
    command: tuple[str, ...]
    hint: str


@dataclass(frozen=True)
class BuildStep:
    name: str
    command: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class BuildPlan:
    project: Project
    target: str
    format: str
    output_dir: Path
    steps: tuple[BuildStep, ...] = ()
    requirements: tuple[ToolRequirement, ...] = ()
    artifact_patterns: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    internal_builder: str | None = None


def serializable(value: Any) -> Any:
    """Convert model objects into a stable JSON-compatible representation."""
    if is_dataclass(value) and not isinstance(value, type):
        return serializable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    return value
