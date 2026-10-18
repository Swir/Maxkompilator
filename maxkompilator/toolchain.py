"""Project-owned exact tool versions, checked before any build command."""
from __future__ import annotations

from dataclasses import replace
import re
import sys

from .config import load_config
from .models import BuildPlan, PlanError, ToolRequirement


def pin_tools(plan: BuildPlan, python_executable: str | None = None) -> BuildPlan:
    pins = load_config(plan.project.root).get("tools", {})
    if not isinstance(pins, dict):
        raise PlanError("[tools] must be a TOML table of exact tool versions.")
    allowed = {"python": {"python", "pyinstaller"}, "dotnet": {"dotnet"}, "android": {"java"}}.get(plan.project.kind, set())
    if set(pins) - allowed:
        raise PlanError(f"Unsupported tool pins for {plan.project.kind}: {', '.join(sorted(set(pins) - allowed))}.")
    if any(not isinstance(v, str) or not re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?", v) for v in pins.values()):
        raise PlanError("[tools] values must be exact versions, such as 3.11.14 or 6.22.3.")
    requirements = list(plan.requirements)
    names = {"pyinstaller": "PyInstaller", "dotnet": ".NET SDK", "java": "Java (JDK)"}
    for key, version in pins.items():
        if key == "python":
            requirements.append(ToolRequirement("Python version", (python_executable or sys.executable, "--version"),
                                                "Select the Python interpreter pinned in [tools].", version))
        else:
            matching = [i for i, item in enumerate(requirements) if item.name == names[key]]
            if len(matching) != 1:
                raise PlanError(f"The selected format does not use the pinned {key} tool.")
            index = matching[0]
            requirements[index] = replace(requirements[index], expected_version=version)
    return replace(plan, requirements=tuple(requirements))
