"""Build adapters produce reviewable commands; they never execute them."""

from __future__ import annotations

import os
from pathlib import Path

from ..models import BuildPlan, PlanError, Project
from ..toolchain import pin_tools
from .registry import API_VERSION, adapter_kinds, extension_plan, register_adapter, unregister_adapter


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
        plan = create_python_plan(project, target, selected_format, output, python_executable)
    elif project.kind == "dotnet":
        from .dotnet_adapter import create_dotnet_plan
        plan = create_dotnet_plan(project, target, selected_format, output)
    elif project.kind == "android":
        from .android_adapter import create_android_plan
        plan = create_android_plan(project, target, selected_format, output)
    else:
        plan = extension_plan(project, target, selected_format, output, str(python_executable) if python_executable else None)
    return pin_tools(plan, str(python_executable) if python_executable else None)
