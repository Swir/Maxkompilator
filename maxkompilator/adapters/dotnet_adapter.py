"""Managed .NET publishing with explicit runtime identifiers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import xml.etree.ElementTree as ET

from ..app_profile import load_app_profile, native_icon
from ..models import BuildPlan, BuildStep, PlanError, Project, ToolRequirement
from .python_adapter import native_target, normalize_target


def create_dotnet_plan(
    project: Project, target: str, format: str | None, output_dir: Path,
) -> BuildPlan:
    if format not in {None, "directory", "executable"}:
        raise PlanError("The .NET adapter publishes a self-contained application directory.")
    if not project.project_file:
        raise PlanError("Select a concrete .csproj file for .NET publishing.")
    csproject = (project.root / project.project_file).resolve()
    if not csproject.is_relative_to(project.root.resolve()) or not csproject.is_file():
        raise PlanError("The .csproj file must exist inside the project directory.")
    try:
        tree = ET.parse(csproject)
    except (OSError, ET.ParseError) as exc:
        raise PlanError(f"Cannot read .csproj metadata: {exc}") from exc
    properties: dict[str, list[str]] = {}
    for element in tree.iter():
        key = element.tag.rsplit("}", 1)[-1]
        if element.text and element.text.strip():
            properties.setdefault(key, []).append(element.text.strip())
    if any(value.lower() == "true" for value in properties.get("PublishAot", [])):
        raise PlanError("NativeAOT projects are not supported by this adapter yet; select a managed .NET publish project.")
    target_frameworks = properties.get("TargetFrameworks", [])
    if any(len([part for part in value.split(";") if part.strip()]) > 1 for value in target_frameworks):
        raise PlanError("Multi-target .NET publishing requires an explicit framework; v0.1 supports a single TargetFramework.")
    selected_target = normalize_target(target)
    supported = {
        "win-x64", "win-x86", "win-arm64", "linux-x64", "linux-arm64", "linux-arm",
        "macos-x64", "macos-arm64",
    }
    if selected_target not in supported:
        raise PlanError(f"Unsupported .NET runtime target: {selected_target}")
    frameworks = properties.get("TargetFramework", []) + target_frameworks
    windows_desktop = any(
        value.lower() == "true"
        for key in ("UseWPF", "UseWindowsForms") for value in properties.get(key, [])
    ) or any("-windows" in value.lower() for value in frameworks)
    if windows_desktop and (
        not selected_target.startswith("win-") or not native_target().startswith("win-")
    ):
        raise PlanError("Windows desktop/WPF/WinForms projects require a Windows worker and a Windows target in v0.1.")
    profile = load_app_profile(project.root, project.name)
    if profile.icon is not None and not selected_target.startswith("win-"):
        raise PlanError(".NET ApplicationIcon embedding is currently supported only for Windows publish targets.")
    icon = native_icon(profile, selected_target)
    profile_arguments: list[str] = []
    if profile.explicit_name:
        profile_arguments.append(f"-p:AssemblyName={profile.name}")
        project = replace(project, name=profile.name)
    if profile.version:
        profile_arguments.append(f"-p:Version={profile.version}")
    if icon is not None:
        # An absolute path avoids ambiguity when a .csproj lives below the root.
        # The profile loader rejects MSBuild property separators and symlink escapes.
        profile_arguments.append(f"-p:ApplicationIcon={icon}")
    rid = selected_target.replace("macos-", "osx-", 1)
    command = (
        "dotnet", "publish", str(csproject), "-c", "Release", "-r", rid,
        "--self-contained", "true", *profile_arguments, "-o", str(output_dir),
    )
    return BuildPlan(
        project, rid, "directory", output_dir,
        steps=(BuildStep("Publish self-contained .NET application", command, project.root),),
        requirements=(ToolRequirement(
            ".NET SDK", ("dotnet", "--version"),
            "Install a .NET SDK compatible with the project and its global.json, if present.",
        ),),
        artifact_patterns=("**/*",),
        notes=(
            "Managed self-contained publishing includes the .NET runtime; NativeAOT is not enabled.",
            "Keep the whole publish directory. Validate cross-target builds on the destination operating system.",
            "Project dependencies and platform-specific APIs must support the selected runtime identifier.",
        ),
    )
