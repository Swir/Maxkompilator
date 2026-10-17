from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from maxkompilator.adapters import create_plan
from maxkompilator.config import load_config
from maxkompilator.detection import detect_project
from maxkompilator.engine import Cancelled, collect_artifacts, execute_build, identify_file, run_command, validate_output_directory
from maxkompilator.environment import external_environment, probe_tool, spawn_external
from maxkompilator.models import BuildPlan, BuildStep, MaxkompilatorError, Project, ToolRequirement


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        self.output = Path(self.temp.name) / "result"
        (self.root / "main.py").write_text("print('hello build')\n", encoding="utf-8")

    def zip_plan(self):
        return create_plan(detect_project(self.root), format="zipapp", output_dir=self.output)

    def test_zipapp_builds_and_runs_with_resources_outside_source(self):
        (self.root / "sample").mkdir()
        (self.root / "sample" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "sample" / "text.txt").write_text("zasób łódź", encoding="utf-8")
        (self.root / "main.py").write_text("from importlib.resources import files\nprint(files('sample').joinpath('text.txt').read_text(encoding='utf-8'))\n", encoding="utf-8")
        (self.root / ".env").write_text("PRIVATE=value")
        (self.root / "key.jks").write_text("private key fixture")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "old.bin").write_bytes(b"stale")
        report = execute_build(self.zip_plan(), smoke_test=True)
        self.assertEqual(report["status"], "built", report)
        self.assertEqual(report["smoke_test"]["status"], "passed")
        self.assertIn("zasób łódź", report["smoke_test"]["output_tail"])
        artifact = report["artifacts"][0]
        path = Path(artifact["path"])
        self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        with zipfile.ZipFile(path) as archive:
            self.assertNotIn(".env", archive.namelist())
            self.assertNotIn("key.jks", archive.namelist())
            self.assertNotIn("dist/old.bin", archive.namelist())
        persisted = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
        self.assertEqual(persisted["run_id"], report["run_id"])

    def test_zipapp_default_does_not_execute_project(self):
        report = execute_build(self.zip_plan())
        self.assertEqual(report["status"], "built")
        self.assertEqual(report["smoke_test"]["status"], "not_run")

    def test_failed_smoke_is_not_reported_as_success(self):
        (self.root / "main.py").write_text("raise SystemExit(7)\n")
        report = execute_build(self.zip_plan(), smoke_test=True)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["smoke_test"]["status"], "failed")
        self.assertTrue(report["artifacts"])

    def test_output_cannot_overwrite_project_root_or_parent(self):
        for target in (self.root, self.root.parent):
            plan = BuildPlan(Project(self.root, "python", "demo", "main.py"), "python", "zipapp", target)
            with self.assertRaises(MaxkompilatorError):
                validate_output_directory(plan)

    def test_missing_tool_yields_failed_report_without_build(self):
        plan = BuildPlan(Project(self.root, "python", "demo", "main.py"), "python", "zipapp", self.output,
                         requirements=(ToolRequirement("missing", ("maxkompilator-not-an-existing-tool",), "Install tool"),),
                         artifact_patterns=("demo.pyz",), internal_builder="zipapp")
        report = execute_build(plan)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["environment"]["ready"])
        self.assertEqual(report["artifacts"], [])

    def test_nonzero_exit_is_logged_and_reported(self):
        plan = BuildPlan(Project(self.root, "python", "demo"), "native", "directory", self.output,
                         steps=(BuildStep("failure", (sys.executable, "-c", "print('compiler failed'); raise SystemExit(9)"), self.root),))
        report = execute_build(plan)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["steps"][0]["returncode"], 9)
        self.assertIn("compiler failed", Path(report["log_path"]).read_text())

    def test_zero_exit_without_artifact_is_failure(self):
        plan = BuildPlan(Project(self.root, "python", "demo"), "native", "directory", self.output,
                         steps=(BuildStep("no output", (sys.executable, "-c", "pass"), self.root),), artifact_patterns=("demo.exe",))
        self.assertEqual(execute_build(plan)["status"], "failed")

    def test_old_output_cannot_make_noop_native_build_succeed(self):
        from maxkompilator.adapters.python_adapter import native_target
        old = self.output / "demo" / ("demo.exe" if os.name == "nt" else "demo")
        old.parent.mkdir(parents=True)
        old.write_bytes(Path(sys.executable).read_bytes())
        plan = BuildPlan(Project(self.root, "python", "demo"), native_target(), "executable", self.output,
                         steps=(BuildStep("no output", (sys.executable, "-c", "pass"), self.root),),
                         artifact_patterns=("demo/**/*",))
        report = execute_build(plan)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["artifacts"], [])
        self.assertTrue(old.is_file())

    def test_pre_cancelled_build_preserves_previous_artifact(self):
        first = execute_build(self.zip_plan())
        original = Path(first["artifacts"][0]["path"]).read_bytes()
        event = threading.Event()
        event.set()
        second = execute_build(self.zip_plan(), cancel_event=event)
        self.assertEqual(second["status"], "cancelled")
        self.assertEqual(Path(first["artifacts"][0]["path"]).read_bytes(), original)

    def test_running_process_can_be_cancelled(self):
        event = threading.Event()
        timer = threading.Timer(0.25, event.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(Cancelled):
            run_command((sys.executable, "-c", "import time; time.sleep(30)"), self.root, event, lambda _: None, timeout=5)
        self.assertLess(time.monotonic() - started, 5)

    def test_process_timeout(self):
        with self.assertRaises(MaxkompilatorError):
            run_command((sys.executable, "-c", "import time; time.sleep(30)"), self.root, threading.Event(), lambda _: None, timeout=0.2)

    @unittest.skipIf(os.name == "nt", "POSIX process-group regression")
    def test_orphaned_child_is_stopped_after_parent_exit(self):
        marker = self.root / "orphan_was_allowed_to_run"
        child = f"import time; from pathlib import Path; time.sleep(0.8); Path({str(marker)!r}).touch(); time.sleep(20)"
        parent = "import subprocess,sys; subprocess.Popen([sys.executable, '-c', " + repr(child) + "])"
        with self.assertRaises(MaxkompilatorError):
            run_command((sys.executable, "-c", parent), self.root, threading.Event(), lambda _: None, timeout=0.1)
        self.assertFalse(marker.exists())

    def test_nested_script_can_import_a_sibling_module(self):
        (self.root / "tools").mkdir()
        (self.root / "tools" / "__init__.py").write_text("")
        (self.root / "tools" / "helper.py").write_text("MESSAGE = 'nested sibling OK'\n")
        (self.root / "tools" / "main.py").write_text("import helper\nprint(helper.MESSAGE)\n")
        plan = create_plan(detect_project(self.root, entrypoint="tools/main.py"), format="zipapp", output_dir=self.output)
        report = execute_build(plan, smoke_test=True)
        self.assertEqual(report["smoke_test"]["status"], "passed", report)
        self.assertIn("nested sibling OK", report["smoke_test"]["output_tail"])

    def test_smoke_timeout_has_failed_runtime_status(self):
        (self.root / "main.py").write_text("import time; time.sleep(30)\n")
        report = execute_build(self.zip_plan(), smoke_test=True, smoke_timeout=0.15)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["smoke_test"]["status"], "failed")

    def test_library_alone_is_not_a_python_application(self):
        library = self.output / "demo" / "_internal" / "dependency.so"
        library.parent.mkdir(parents=True)
        # Use the current real interpreter binary when it is ELF or PE.
        library.write_bytes(Path(sys.executable).read_bytes())
        from maxkompilator.adapters.python_adapter import native_target
        plan = BuildPlan(Project(self.root, "python", "demo"), native_target(), "executable", self.output, artifact_patterns=("demo/**/*",))
        with self.assertRaises(MaxkompilatorError):
            collect_artifacts(plan)

    def test_lock_prevents_simultaneous_use_of_output(self):
        lock = self.output / ".maxkompilator" / "build.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text("existing task")
        with self.assertRaises(MaxkompilatorError):
            execute_build(self.zip_plan())
        self.assertEqual(lock.read_text(), "existing task")

    def test_fake_executable_cannot_pass_signature_check(self):
        self.output.mkdir()
        (self.output / "fake.exe").write_bytes(b"MZnot really an executable")
        self.assertEqual(identify_file(self.output / "fake.exe"), "invalid-pe")
        plan = BuildPlan(Project(self.root, "python", "fake"), "win-x64", "executable", self.output, artifact_patterns=("fake.exe",))
        with self.assertRaises(MaxkompilatorError):
            collect_artifacts(plan)

    def test_renamed_android_library_is_not_verified_apk(self):
        self.output.mkdir()
        fake = self.output / "renamed.apk"
        with zipfile.ZipFile(fake, "w") as archive:
            archive.writestr("AndroidManifest.xml", "<manifest/>")
            archive.writestr("classes.jar", b"not dex")
        self.assertEqual(identify_file(fake), "android-archive-unverified")
        plan = BuildPlan(Project(self.root, "android", "demo"), "android", "apk", self.output, artifact_patterns=("*.apk",))
        with self.assertRaises(MaxkompilatorError):
            collect_artifacts(plan)

    def test_nested_output_is_not_copied_into_zipapp(self):
        output = self.root / "custom" / "output"
        plan = create_plan(detect_project(self.root), format="zipapp", output_dir=output)
        first = execute_build(plan)
        second = execute_build(plan)
        self.assertEqual(first["status"], "built")
        with zipfile.ZipFile(second["artifacts"][0]["path"]) as archive:
            self.assertFalse(any(name.startswith("custom/output/") for name in archive.namelist()))

    def test_invalid_config_has_actionable_error(self):
        (self.root / "maxkompilator.toml").write_text('[build]\ntarget = 123\n')
        with self.assertRaises(MaxkompilatorError):
            load_config(self.root)


class CLIIntegrationTests(unittest.TestCase):
    def test_inspect_and_plan_are_read_only_and_json_is_parseable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "executed"
            (root / "main.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            for command in ("inspect", "plan"):
                args = [sys.executable, "-m", "maxkompilator", command, str(root), "--json"]
                if command == "plan":
                    args.extend(["--format", "zipapp"])
                result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("project", json.loads(result.stdout))
            self.assertFalse(marker.exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["main.py"])

    def test_build_json_stdout_is_single_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.py").write_text("print('cli fixture')\n")
            result = subprocess.run([sys.executable, "-m", "maxkompilator", "build", str(root), "--format", "zipapp", "--json", "--smoke-test"],
                                    input="", capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["smoke_test"]["status"], "passed")
            self.assertIn("cli fixture", result.stderr)

    def test_cp1252_parent_still_emits_utf8_json_and_smokes_unicode_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "projekt Łódź"
            package = root / "sample"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "text.txt").write_text("zasób łódź", encoding="utf-8")
            (root / "main.py").write_text(
                "from importlib.resources import files\n"
                "print(files('sample').joinpath('text.txt').read_text(encoding='utf-8'))\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-m", "maxkompilator", "build", str(root), "--format", "zipapp", "--json", "--smoke-test"],
                input="", capture_output=True, text=True, encoding="utf-8", timeout=30,
                env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "built")
            self.assertEqual(report["smoke_test"]["status"], "passed")
            self.assertIn("Łódź", result.stdout)
            self.assertIn("zasób łódź", report["smoke_test"]["output_tail"])
            self.assertIn("zasób łódź", result.stderr)


class ExternalProcessTests(unittest.TestCase):
    def test_frozen_environment_is_an_isolated_copy_and_preserves_sibling_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = str(Path(temp) / "bundle")
            sibling = str(Path(temp) / "bundle-other")
            external = str(Path(temp) / "tools")
            supplied = {
                "PATH": os.pathsep.join((bundle, str(Path(bundle) / "bin"), sibling, external)),
                "LD_LIBRARY_PATH": bundle,
                "LD_LIBRARY_PATH_ORIG": external,
                "CUSTOM_SETTING": "retained",
            }
            original = supplied.copy()
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", bundle, create=True), patch.object(sys, "platform", "linux"):
                clean = external_environment(supplied)
                no_original = external_environment({"LD_LIBRARY_PATH": bundle})
            self.assertEqual(clean["PATH"], os.pathsep.join((sibling, external)))
            self.assertEqual(clean["LD_LIBRARY_PATH"], external)
            self.assertEqual(clean["CUSTOM_SETTING"], "retained")
            self.assertNotIn("LD_LIBRARY_PATH", no_original)
            clean["CUSTOM_SETTING"] = "child only"
            self.assertEqual(supplied, original)

    def test_source_mode_preserves_library_environment_and_command_overrides(self):
        supplied = {"PATH": "tools", "LD_LIBRARY_PATH": "custom", "CACHE": "old"}
        with patch.object(sys, "frozen", False, create=True), patch("maxkompilator.environment.subprocess.Popen") as popen:
            spawn_external(["tool"], env=supplied, extra_env={"CACHE": "new"})
        self.assertEqual(popen.call_args.kwargs["env"], {**supplied, "CACHE": "new"})
        self.assertEqual(supplied["CACHE"], "old")

    def test_windows_dll_directory_is_restored_after_spawn_and_spawn_failure(self):
        import ctypes

        previous = r"C:\Maxkompilator\_internal"
        for fail in (False, True):
            with self.subTest(spawn_failure=fail):
                events = []
                kernel = Mock()

                def get_directory(size, buffer):
                    if size:
                        buffer.value = previous
                        return len(previous)
                    return len(previous) + 1

                kernel.GetDllDirectoryW.side_effect = get_directory
                kernel.SetDllDirectoryW.side_effect = lambda value: events.append(("dll", value)) or 1

                def popen(*args, **kwargs):
                    events.append(("spawn", kwargs["env"]["CUSTOM_SETTING"]))
                    if fail:
                        raise OSError("fixture spawn failure")
                    return object()

                with patch.object(sys, "frozen", True, create=True), patch.object(sys, "platform", "win32"), patch.object(ctypes, "WinDLL", return_value=kernel, create=True), patch("maxkompilator.environment.subprocess.Popen", side_effect=popen):
                    if fail:
                        with self.assertRaises(OSError):
                            spawn_external(["tool"], env={"CUSTOM_SETTING": "value"})
                    else:
                        spawn_external(["tool"], env={"CUSTOM_SETTING": "value"})
                self.assertEqual(events, [("dll", None), ("spawn", "value"), ("dll", previous)])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux frozen library environment")
    def test_probe_and_build_process_receive_sanitized_frozen_environment(self):
        code = "import json,os; print(json.dumps({'library': os.environ.get('LD_LIBRARY_PATH'), 'cache': os.environ.get('MAXK_TEST_CACHE')}))"
        command = (sys.executable, "-c", code)
        with tempfile.TemporaryDirectory() as temp:
            bundle = str(Path(temp) / "bundle")
            overrides = {"LD_LIBRARY_PATH": bundle, "LD_LIBRARY_PATH_ORIG": "", "MAXK_TEST_CACHE": "inherited"}
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", bundle, create=True), patch.dict(os.environ, overrides):
                probe = probe_tool(ToolRequirement("test Python", command, ""))
                result = run_command(command, Path(temp), threading.Event(), lambda _: None,
                                     extra_env={"MAXK_TEST_CACHE": "override"})
                self.assertEqual(os.environ["LD_LIBRARY_PATH"], bundle)
            self.assertTrue(probe["available"], probe)
            self.assertEqual(json.loads(probe["version"]), {"library": "", "cache": "inherited"})
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(json.loads(result["output_tail"]), {"library": "", "cache": "override"})


if __name__ == "__main__":
    unittest.main()
