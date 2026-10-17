from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from maxkompilator.adapters import create_plan
from maxkompilator.adapters.python_adapter import native_target
from maxkompilator.detection import detect_project
from maxkompilator.models import PlanError


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "project with spaces"
        self.root.mkdir()

    def write(self, relative: str, content: str = "") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def python(self):
        self.write("main.py", "print('hello')")
        return detect_project(self.root)

    def dotnet(self, properties: str = ""):
        self.write("Application.csproj", (
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
            f'<TargetFramework>net8.0</TargetFramework>{properties}</PropertyGroup></Project>'
        ))
        return detect_project(self.root)

    def android(self, plugin: str = "application", wrapper: bool = True):
        self.write("settings.gradle.kts", 'include(":app")')
        self.write("app/build.gradle.kts", f'plugins {{ id("com.android.{plugin}") }}')
        self.write("app/src/main/AndroidManifest.xml", "<manifest/>")
        if wrapper:
            self.write("gradlew", "#!/bin/sh\nexit 99\n")
            self.write("gradlew.bat", "@exit /b 99\n")
        return detect_project(self.root)

    def test_pyinstaller_plan_is_native_structured_and_has_no_side_effects(self) -> None:
        project = self.python()
        plan = create_plan(project)
        command = plan.steps[0].command
        self.assertEqual(command[:3], (sys.executable, "-m", "PyInstaller"))
        self.assertIn("--onedir", command)
        self.assertEqual(command[-1], str(self.root / "main.py"))
        self.assertEqual(plan.target, native_target())
        self.assertEqual(plan.format, "executable")
        self.assertEqual(plan.steps[0].cwd, self.root)
        self.assertEqual(plan.artifact_patterns, (f"{project.name}/**/*",))
        self.assertFalse(plan.output_dir.exists())

    def test_pyinstaller_rejects_cross_os_and_architecture(self) -> None:
        project = self.python()
        family, architecture = native_target().split("-", 1)
        foreign_family = "linux" if family == "win" else "win"
        foreign_architecture = "arm64" if architecture == "x64" else "x64"
        for target in (f"{foreign_family}-{architecture}", f"{family}-{foreign_architecture}"):
            with self.subTest(target=target), self.assertRaisesRegex(PlanError, "cannot cross-build"):
                create_plan(project, target=target)

    def test_selected_python_interpreter_reports_its_actual_target(self) -> None:
        plan = create_plan(self.python(), python_executable=sys.executable)
        requirement = next(item for item in plan.requirements if item.name == "Python target")
        self.assertEqual(requirement.command[0], sys.executable)
        result = subprocess.run(requirement.command, cwd=self.root.parent,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual(metadata["target"], plan.target)
        self.assertEqual(metadata["expected_target"], plan.target)
        self.assertEqual(metadata["pointer_bits"], struct.calcsize("P") * 8)

    def test_python_target_probe_rejects_different_os_and_pointer_width(self) -> None:
        plan = create_plan(self.python(), python_executable=sys.executable)
        requirement = next(item for item in plan.requirements if item.name == "Python target")
        family, architecture = plan.target.split("-", 1)
        foreign_family = "linux" if family == "win" else "win"
        foreign_architecture = "x86" if struct.calcsize("P") == 8 else "x64"
        for target in (f"{foreign_family}-{architecture}", f"{family}-{foreign_architecture}"):
            with self.subTest(target=target):
                result = subprocess.run((*requirement.command[:-1], target), cwd=self.root.parent,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1, result.stderr)
                metadata = json.loads(result.stdout)
                self.assertEqual(metadata["target"], plan.target)
                self.assertEqual(metadata["expected_target"], target)

    def test_zipapp_is_source_package_not_dependency_bundle(self) -> None:
        plan = create_plan(self.python(), format="zipapp")
        self.assertEqual((plan.target, plan.internal_builder), ("python", "zipapp"))
        self.assertEqual(plan.steps, ())
        self.assertTrue(any("not bundled" in note for note in plan.notes))
        self.assertTrue(any("Python installation" in note for note in plan.notes))
        self.assertEqual(plan.artifact_patterns, (f"{plan.project.name}.pyz",))

    def test_python_missing_entry_requires_explicit_choice(self) -> None:
        self.write("pyproject.toml", '[project]\nname="library"\n')
        self.write("one.py")
        self.write("two.py")
        with self.assertRaisesRegex(PlanError, "entrypoint"):
            create_plan(detect_project(self.root))

    def test_python_resource_files_preserve_package_destination(self) -> None:
        project = self.python()
        resource = self.write("hello/message.json", '{"message":"hello"}')
        self.write("maxkompilator.toml", '[python]\ndata = ["hello/message.json"]\n')
        command = create_plan(project).steps[0].command
        position = command.index("--add-data")
        self.assertEqual(command[position + 1], f"{resource}:hello")

    def test_python_data_directory_preserves_directory_name(self) -> None:
        project = self.python()
        self.write("assets/settings/default.json", "{}")
        self.write("maxkompilator.toml", '[python]\ndata=["assets"]\n')
        command = create_plan(project).steps[0].command
        self.assertEqual(command[command.index("--add-data") + 1], f"{self.root / 'assets'}:assets")

    def test_python_resource_traversal_missing_and_wrong_type_rejected(self) -> None:
        project = self.python()
        (self.root.parent / "secret.txt").write_text("private", encoding="utf-8")
        for value in ('["../secret.txt"]', '["missing.json"]', '"not-a-list"', '[4]', '["."]'):
            self.write("maxkompilator.toml", f"[python]\ndata={value}\n")
            with self.subTest(value=value), self.assertRaises(PlanError):
                create_plan(project)

    def test_python_resource_symlink_escape_rejected(self) -> None:
        project = self.python()
        outside = self.root.parent / "secret.txt"
        outside.write_text("private", encoding="utf-8")
        try:
            (self.root / "asset.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable for this test user.")
        self.write("maxkompilator.toml", '[python]\ndata=["asset.txt"]\n')
        with self.assertRaisesRegex(PlanError, "escapes"):
            create_plan(project)

    def test_python_output_cannot_recursively_become_data(self) -> None:
        project = self.python()
        (self.root / "dist").mkdir()
        self.write("maxkompilator.toml", '[python]\ndata=["dist"]\n')
        with self.assertRaisesRegex(PlanError, "output directory"):
            create_plan(project)

    def test_output_resolution_is_project_relative_and_separate(self) -> None:
        project = self.python()
        self.assertEqual(create_plan(project, output_dir="results").output_dir, self.root / "results")
        with self.assertRaisesRegex(PlanError, "separate directory"):
            create_plan(project, output_dir=self.root)

    def test_dotnet_publish_includes_runtime_and_concrete_project(self) -> None:
        plan = create_plan(self.dotnet(), target="linux-x64")
        command = plan.steps[0].command
        self.assertEqual(command[:3], ("dotnet", "publish", str(self.root / "Application.csproj")))
        self.assertEqual(command[command.index("-r") + 1], "linux-x64")
        self.assertEqual(command[command.index("--self-contained") + 1], "true")
        self.assertEqual(plan.format, "directory")
        self.assertEqual(plan.artifact_patterns, ("**/*",))
        self.assertFalse(plan.output_dir.exists())

    def test_dotnet_macos_target_uses_dotnet_osx_rid(self) -> None:
        plan = create_plan(self.dotnet(), target="macos-arm64")
        self.assertEqual(plan.target, "osx-arm64")
        self.assertIn("osx-arm64", plan.steps[0].command)

    def test_dotnet_windows_desktop_rejects_linux_target(self) -> None:
        for property in ("UseWPF", "UseWindowsForms"):
            with self.subTest(property=property), self.assertRaisesRegex(PlanError, "Windows worker"):
                create_plan(self.dotnet(f"<{property}>true</{property}>"), target="linux-x64")

    def test_dotnet_aot_and_multi_target_are_explicitly_unsupported(self) -> None:
        cases = (
            ("<PublishAot>true</PublishAot>", "NativeAOT"),
            ("<TargetFrameworks>net8.0;net9.0</TargetFrameworks>", "Multi-target"),
        )
        for properties, message in cases:
            with self.subTest(properties=properties), self.assertRaisesRegex(PlanError, message):
                create_plan(self.dotnet(properties))

    def test_android_debug_apk_plan_does_not_execute_wrapper(self) -> None:
        plan = create_plan(self.android())
        self.assertEqual((plan.target, plan.format), ("android", "apk"))
        self.assertIn(":app:assembleDebug", plan.steps[0].command)
        expected_wrapper = "gradlew.bat" if os.name == "nt" else "gradlew"
        self.assertIn(str(self.root / expected_wrapper), plan.steps[0].command)
        self.assertEqual(plan.requirements[0].command, ("java", "-version"))
        self.assertTrue(Path(plan.artifact_patterns[0]).is_absolute())
        self.assertFalse(plan.output_dir.exists())

    def test_android_clean_precedes_both_build_tasks_without_running_at_plan_time(self) -> None:
        project = self.android()
        previous = self.write("app/build/outputs/apk/debug/previous.apk", "previous output")
        for format, task in (("apk", ":app:assembleDebug"), ("aab", ":app:bundleDebug")):
            with self.subTest(format=format):
                command = create_plan(project, format=format).steps[0].command
                self.assertLess(command.index(":app:clean"), command.index(task))
                self.assertTrue(previous.exists())

    def test_android_rejects_output_inside_cleaned_build_directory(self) -> None:
        project = self.android()
        for output in ("app/build", "app/build/maxkompilator", "app/build/reports/session"):
            with self.subTest(output=output), self.assertRaisesRegex(PlanError, "outside app/build"):
                create_plan(project, output_dir=output)

    def test_android_rejects_output_symlink_into_cleaned_directory(self) -> None:
        project = self.android()
        generated = self.root / "app" / "build"
        generated.mkdir()
        alias = self.root / "output-alias"
        try:
            alias.symlink_to(generated, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable for this test user.")
        with self.assertRaisesRegex(PlanError, "outside app/build"):
            create_plan(project, output_dir=alias / "reports")

    def test_android_artifact_patterns_select_only_debug_outputs(self) -> None:
        project = self.android()
        debug_apk = self.write("app/build/outputs/apk/debug/app-debug.apk")
        flavored_apk = self.write("app/build/outputs/apk/demo/debug/app-demo-debug.apk")
        self.write("app/build/outputs/apk/release/app-release.apk")
        debug_aab = self.write("app/build/outputs/bundle/debug/app-debug.aab")
        flavored_aab = self.write("app/build/outputs/bundle/demoDebug/app-demo-debug.aab")
        self.write("app/build/outputs/bundle/release/app-release.aab")
        for format, expected in (("apk", {debug_apk, flavored_apk}), ("aab", {debug_aab, flavored_aab})):
            with self.subTest(format=format):
                plan = create_plan(project, format=format)
                artifacts = {Path(path) for path in glob.glob(plan.artifact_patterns[0], recursive=True)}
                self.assertEqual(artifacts, expected)

    def test_android_missing_wrapper_is_actionable(self) -> None:
        with self.assertRaisesRegex(PlanError, "Gradle Wrapper"):
            create_plan(self.android(wrapper=False))

    def test_android_library_is_not_packaged_as_an_app(self) -> None:
        with self.assertRaisesRegex(PlanError, "Android library"):
            create_plan(self.android(plugin="library"))

    def test_android_rejects_unimplemented_target_and_format(self) -> None:
        project = self.android()
        for options in ({"target": "win-x64"}, {"format": "aar"}, {"format": "exe"}):
            with self.subTest(options=options), self.assertRaises(PlanError):
                create_plan(project, **options)


if __name__ == "__main__":
    unittest.main()
