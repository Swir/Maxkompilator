from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from maxkompilator.detection import detect_project
from maxkompilator.models import DetectionError


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "Example Project"
        self.root.mkdir()

    def write(self, relative: str, content: str = "") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def symlink(self, target: Path, link: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable for this test user.")

    def test_single_script_is_detected_without_execution(self) -> None:
        marker = self.root / "must-not-exist.txt"
        script = self.write("hello.py", f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
        project = detect_project(script)
        self.assertEqual((project.kind, project.name, project.entrypoint), ("python", "hello", "hello.py"))
        self.assertFalse(marker.exists())

    def test_pyproject_name_and_main_are_read_statically(self) -> None:
        self.write("pyproject.toml", '[project]\nname = "nice-project"\nversion = "0.1.0"\n')
        self.write("main.py", "raise RuntimeError('must never run during detection')")
        project = detect_project(self.root)
        self.assertEqual((project.kind, project.name, project.entrypoint, project.project_file),
                         ("python", "nice-project", "main.py", "pyproject.toml"))

    def test_packaged_project_does_not_guess_launcher(self) -> None:
        self.write("pyproject.toml", '[project]\nname = "package"\n')
        self.write("launcher.py", "print('application')")
        self.assertIsNone(detect_project(self.root).entrypoint)
        self.assertEqual(detect_project(self.root, entrypoint="launcher.py").entrypoint, "launcher.py")

    def test_directory_with_one_plain_script_can_infer_entry(self) -> None:
        self.write("calculate.py", "print(1 + 2)")
        self.assertEqual(detect_project(self.root).entrypoint, "calculate.py")

    def test_multiple_python_scripts_need_explicit_entry(self) -> None:
        self.write("first.py")
        self.write("second.py")
        self.assertIsNone(detect_project(self.root).entrypoint)

    def test_root_dunder_main_takes_precedence(self) -> None:
        self.write("__main__.py")
        self.write("main.py")
        self.assertEqual(detect_project(self.root).entrypoint, "__main__.py")

    def test_explicit_entry_cannot_escape_project(self) -> None:
        outside = self.root.parent / "outside.py"
        outside.write_text("pass", encoding="utf-8")
        self.write("main.py")
        with self.assertRaisesRegex(DetectionError, "inside"):
            detect_project(self.root, entrypoint="../outside.py")

    def test_entry_symlink_cannot_escape_project(self) -> None:
        outside = self.root.parent / "outside.py"
        outside.write_text("pass", encoding="utf-8")
        self.symlink(outside, self.root / "main.py")
        with self.assertRaisesRegex(DetectionError, "inside"):
            detect_project(self.root)

    def test_mixed_directory_requires_explicit_kind(self) -> None:
        self.write("main.py")
        self.write("Application.csproj", '<Project Sdk="Microsoft.NET.Sdk"/>')
        with self.assertRaisesRegex(DetectionError, "Ambiguous"):
            detect_project(self.root)
        self.assertEqual(detect_project(self.root, kind="python").kind, "python")
        self.assertEqual(detect_project(self.root, kind="dotnet").project_file, "Application.csproj")

    def test_multiple_csprojects_require_concrete_project_path(self) -> None:
        self.write("One.csproj", "<Project/>")
        second = self.write("src/Two/Two.csproj", "<Project/>")
        with self.assertRaisesRegex(DetectionError, "Multiple .csproj"):
            detect_project(self.root)
        self.assertEqual(detect_project(second).name, "Two")

    def test_nested_csproject_detected_but_build_tree_ignored(self) -> None:
        self.write("src/MyApp/MyApp.csproj", "<Project/>")
        self.write("obj/Generated.csproj", "<Project/>")
        self.write(".venv/Other.csproj", "<Project/>")
        project = detect_project(self.root)
        self.assertEqual(project.project_file, "src/MyApp/MyApp.csproj")

    def test_android_plugin_detected_without_running_wrapper(self) -> None:
        self.write("settings.gradle.kts", 'include(":app")')
        self.write("app/build.gradle.kts", 'plugins { id("com.android.application") }')
        self.write("gradlew", "exit 99\n")
        self.assertEqual(detect_project(self.root).kind, "android")

    def test_android_manifest_detects_plugin_alias_project(self) -> None:
        self.write("settings.gradle.kts", 'include(":app")')
        self.write("app/build.gradle.kts", "plugins { alias(libs.plugins.android.application) }")
        self.write("app/src/main/AndroidManifest.xml", "<manifest/>")
        self.assertEqual(detect_project(self.root).kind, "android")

    def test_regular_gradle_project_is_not_android(self) -> None:
        self.write("build.gradle", "plugins { id 'java' }")
        with self.assertRaisesRegex(DetectionError, "No supported"):
            detect_project(self.root)

    def test_commented_android_plugin_is_not_a_project(self) -> None:
        self.write("build.gradle", '// id("com.android.application")\n/* id("com.android.library") */\n')
        with self.assertRaises(DetectionError):
            detect_project(self.root)

    def test_invalid_pyproject_is_reported(self) -> None:
        self.write("pyproject.toml", "[project\n")
        with self.assertRaisesRegex(DetectionError, "Invalid pyproject"):
            detect_project(self.root)

    def test_unknown_paths_files_and_kinds_are_not_converted(self) -> None:
        binary = self.write("existing.exe", "This is not source code")
        for path, options in ((self.root / "missing", {}), (binary, {}), (self.root, {"kind": "all"})):
            with self.subTest(path=path, options=options), self.assertRaises(DetectionError):
                detect_project(path, **options)


if __name__ == "__main__":
    unittest.main()
