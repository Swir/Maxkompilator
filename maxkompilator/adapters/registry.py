"""Explicit, process-local extension API. Importing project files is forbidden."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Protocol

from ..models import BuildPlan, PlanError, Project

API_VERSION = 1
BUILTIN_KINDS = ("python", "dotnet", "android")


class PlanFactory(Protocol):
    def __call__(self, project: Project, target: str, format: str | None,
                 output_dir: Path, python_executable: str | None) -> BuildPlan: ...


_factories: dict[str, PlanFactory] = {}


def register_adapter(kind: str, factory: PlanFactory, *, api_version: int = API_VERSION) -> None:
    """Register trusted application code; no automatic plugin/project imports."""
    if api_version != API_VERSION:
        raise PlanError(f"Unsupported adapter API version: {api_version}.")
    if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", kind):
        raise PlanError("Adapter kind must be a lowercase identifier.")
    if kind in BUILTIN_KINDS or kind in _factories:
        raise PlanError(f"Adapter {kind!r} is already registered.")
    if not callable(factory):
        raise PlanError("Adapter factory must be callable.")
    _factories[kind] = factory


def unregister_adapter(kind: str) -> None:
    """Remove an explicitly registered extension, never a built-in adapter."""
    _factories.pop(kind, None)


def adapter_kinds() -> tuple[str, ...]:
    return (*BUILTIN_KINDS, *sorted(_factories))


def extension_plan(project: Project, target: str, format: str | None,
                   output: Path, python_executable: str | None) -> BuildPlan:
    factory = _factories.get(project.kind)
    if factory is None:
        raise PlanError(f"Unsupported project kind: {project.kind}")
    plan = factory(project, target, format, output, python_executable)
    if (not isinstance(plan, BuildPlan) or plan.project != project
            or plan.output_dir.resolve() != output or not plan.artifact_patterns
            or not plan.steps or plan.internal_builder is not None):
        raise PlanError("Extension violated the project, output or external build-plan contract.")
    return plan
