"""Use an existing project's Gradle Wrapper to build debug Android artifacts."""

from __future__ import annotations

import os
from pathlib import Path
import re

from ..models import BuildPlan, BuildStep, PlanError, Project, ToolRequirement


def create_android_plan(
    project: Project, target: str, format: str | None, output_dir: Path,
) -> BuildPlan:
    if target not in {"native", "android"}:
        raise PlanError("The Android adapter uses --target android; ABI selection belongs to the Gradle project.")
    selected_format = format or "apk"
    if selected_format not in {"apk", "aab"}:
        raise PlanError("The Android adapter currently builds debug APK or AAB; AAR/release signing is not implemented yet.")
    root = project.root.resolve()
    module = root / "app"
    build_files = [module / "build.gradle.kts", module / "build.gradle"]
    module_build = next((path for path in build_files if path.is_file()), None)
    if module_build is None or not module.resolve().is_relative_to(root):
        raise PlanError("The Android adapter requires an application module named app with its own build.gradle(.kts).")
    if not module_build.resolve().is_relative_to(root):
        raise PlanError("The Android module build file must remain inside the project directory.")
    if output_dir.resolve().is_relative_to((module / "build").resolve()):
        raise PlanError("Android output must remain outside app/build because :app:clean removes that generated directory.")
    try:
        build_text = module_build.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise PlanError(f"Cannot read Android module metadata: {exc}") from exc
    if re.search(r"[\"']com\.android\.library[\"']", build_text):
        raise PlanError("The app module declares an Android library. APK/AAB output requires an application module.")
    wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not wrapper.is_file() or not wrapper.resolve().is_relative_to(root):
        raise PlanError(f"Missing project-local Gradle Wrapper: {wrapper.name}. Generate it using the project's Gradle version.")
    task = ":app:assembleDebug" if selected_format == "apk" else ":app:bundleDebug"
    launcher = ("cmd.exe", "/d", "/c", str(wrapper)) if os.name == "nt" else ("sh", str(wrapper))
    # Absolute patterns are intentional: the runner collects these Gradle
    # artifacts and copies them to output_dir after a successful build.
    artifact_directory = module / "build" / "outputs"
    pattern = (
        str(artifact_directory / "apk" / "**" / "debug" / "*.apk")
        if selected_format == "apk"
        else str(artifact_directory / "bundle" / "*[dD]ebug" / "*.aab")
    )
    return BuildPlan(
        project, "android", selected_format, output_dir,
        steps=(BuildStep(
            f"Clean and build Android debug {selected_format.upper()}",
            (*launcher, ":app:clean", task, "--console=plain"), root,
        ),),
        requirements=(ToolRequirement(
            "Java (JDK)", ("java", "-version"),
            "Install the JDK required by the project's Gradle and Android Gradle Plugin versions.",
        ),),
        artifact_patterns=(pattern,),
        notes=(
            "The app module's generated build results are cleaned before building to exclude older APK/AAB files.",
            "Requires an Android SDK configured through ANDROID_HOME or sdk.dir in local.properties.",
            "The project's Gradle Wrapper may download its configured Gradle distribution and dependencies.",
            "This is a debug build signed for testing. Store-ready release signing is not configured by v0.1.",
            "An AAB cannot be installed directly on a phone; choose APK for device tests.",
        ),
    )
