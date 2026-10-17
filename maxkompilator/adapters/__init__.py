"""Build adapters produce reviewable commands; they never execute them."""

from __future__ import annotations

import os
from pathlib import Path

from ..models import BuildPlan, PlanError, Project


def create_plan(
    project: Project,
    *,
    target: str = "native",
    format: str | None = None,
    output_dir: str | os.PathLike[str] | None = None,
    python_executable: str | os.PathLike[str] | None = None,
) -> BuildPlan:
    if output_dir is None:
        output = project.root / "dist" / "maxkompilator"
    else:
        output = Path(output_dir).expanduser()
        if not output.is_absolute():
            output = project.root / output
    output = output.resolve()
    if output == project.root.resolve():
        raise PlanError("Build output must use a separate directory, not the project root.")
    target = target.strip().lower()
    selected_format = format.strip().lower() if format else None
    if project.kind == "python":
        from .python_adapter import create_python_plan
        return create_python_plan(project, target, selected_format, output, python_executable)
    if project.kind == "dotnet":
        from .dotnet_adapter import create_dotnet_plan
        return create_dotnet_plan(project, target, selected_format, output)
    if project.kind == "android":
        from .android_adapter import create_android_plan
        return create_android_plan(project, target, selected_format, output)
    raise PlanError(f"Unsupported project kind: {project.kind}")
