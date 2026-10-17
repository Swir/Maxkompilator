#!/usr/bin/env python3
"""Exercise the real Qt window, CLI subprocesses and zipapp build headlessly.

Usage: python scripts/gui_smoke.py [--screenshot qualification/gui.png]

The fixture is temporary, contains spaces and Unicode, and needs no dependency
downloads. The platform folder opener is captured through Qt's public URL
handler API; inspection, diagnostics, building and cancellation run for real.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _pid_running(pid: int) -> bool:
    """Check our fixture PIDs without sending termination signals on Windows."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied still means a process exists.
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    try:
        # A reaped job can briefly have a zombie descendant; it cannot execute.
        if stat.is_file() and stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path, help="Optional PNG of the successful build window.")
    parser.add_argument("--timeout", type=float, default=90.0, help="Overall test deadline in seconds (default: 90).")
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be greater than 0 and at most 600 seconds")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PySide6.QtCore import QObject, QTimer, QUrl, Slot
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QLabel, QLineEdit,
            QPlainTextEdit, QProgressBar, QPushButton,
        )
    except ImportError as exc:
        print(f"GUI smoke requires the gui extra: {exc}", file=sys.stderr)
        return 2
    from maxkompilator.gui import launch_gui

    class UrlCapture(QObject):
        def __init__(self, parent: QObject) -> None:
            super().__init__(parent)
            self.paths: list[Path] = []

        @Slot(QUrl)
        def receive(self, url: QUrl) -> None:
            self.paths.append(Path(url.toLocalFile()).resolve())

    class SmokeHarness(QObject):
        def __init__(self, app: QApplication, fixture: Path, marker: Path, cancel_pids: Path) -> None:
            super().__init__(app)
            self.app = app
            self.fixture = fixture
            self.marker = marker
            self.cancel_pids = cancel_pids
            self.window: Any = None
            self.controls: dict[str, Any] = {}
            self.phase = "find_window"
            self.started = time.monotonic()
            self.cancel_started = 0.0
            self.cancel_completed = 0.0
            self.deadline = self.started + args.timeout
            self.shutdown_deadline = 0.0
            self.failed: str | None = None
            self.passed: list[str] = []
            self.finished = False
            self.screenshot_saved = False
            self.urls = UrlCapture(self)
            QDesktopServices.setUrlHandler("file", self.urls, "receive")
            self.timer = QTimer(self)
            self.timer.setInterval(25)
            self.timer.timeout.connect(self.tick)
            self.timer.start()

        def require(self, condition: Any, message: str) -> None:
            if not condition:
                raise AssertionError(message)

        def record(self, name: str) -> None:
            self.passed.append(name)
            print("PASS " + name, flush=True)

        def child(self, widget_class: Any, name: str) -> Any:
            widget = self.window.findChild(widget_class, name)
            self.require(widget is not None, "Missing control: " + name)
            self.controls[name] = widget
            return widget

        def report(self) -> dict[str, Any]:
            # Parse the actual CLI stdout independently from the GUI's summary.
            value = json.loads(self.window._stdout_tail)
            self.require(isinstance(value, dict), "CLI did not return a JSON object")
            return value

        def idle(self) -> bool:
            return bool(self.controls["inspectButton"].isEnabled())

        def check_busy_controls(self) -> None:
            for name in ("projectRoot", "entrypoint", "projectKind", "targetPlatform", "outputFormat", "smokeTestCheck", "inspectButton", "doctorButton", "buildButton", "openResultsButton"):
                self.require(not self.controls[name].isEnabled(), "Control remained enabled during a task: " + name)
            self.require(self.controls["cancelButton"].isEnabled(), "Cancel button is unavailable during a task")
            indicator = self.controls["busyIndicator"]
            self.require(indicator.isVisible() and indicator.minimum() == 0 and indicator.maximum() == 0, "Busy indicator must be indeterminate")

        def check_idle_controls(self, *, has_results: bool = False) -> None:
            for name in ("projectRoot", "entrypoint", "projectKind", "targetPlatform", "outputFormat", "smokeTestCheck", "inspectButton", "doctorButton", "buildButton"):
                self.require(self.controls[name].isEnabled(), "Control was not restored after a task: " + name)
            self.require(not self.controls["cancelButton"].isEnabled(), "Cancel remained enabled after a task")
            self.require(not self.controls["busyIndicator"].isVisible(), "Busy indicator remained visible")
            self.require(self.controls["openResultsButton"].isEnabled() == has_results, "Unexpected result-folder button state")

        def capture(self) -> None:
            if args.screenshot is None:
                return
            destination = args.screenshot.expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.require(self.window.grab().save(str(destination), "PNG"), "Could not save the GUI screenshot")
            self.screenshot_saved = True

        def begin(self) -> None:
            self.window = next((widget for widget in QApplication.topLevelWidgets() if widget.objectName() == "maxkompilatorWindow"), None)
            if self.window is None:
                return
            for cls, name in (
                (QLineEdit, "projectRoot"), (QLineEdit, "entrypoint"),
                (QComboBox, "projectKind"), (QComboBox, "targetPlatform"), (QComboBox, "outputFormat"),
                (QCheckBox, "smokeTestCheck"), (QPushButton, "inspectButton"),
                (QPushButton, "doctorButton"), (QPushButton, "buildButton"),
                (QPushButton, "cancelButton"), (QPushButton, "openResultsButton"),
                (QPlainTextEdit, "logView"), (QPlainTextEdit, "summaryView"),
                (QLabel, "statusLabel"), (QProgressBar, "busyIndicator"),
            ):
                self.child(cls, name)
            self.require(not self.window.windowIcon().isNull(), "The application icon is missing")
            self.require(not self.controls["smokeTestCheck"].isChecked(), "Runtime testing must be off by default")
            self.require(self.controls["projectKind"].currentData() == "auto", "Automatic project detection is not the default")
            self.require(self.controls["outputFormat"].currentData() == "auto", "Automatic output format is not the default")
            self.check_idle_controls()
            self.record("initial_window_icon_and_controls")
            self.controls["projectRoot"].setText(str(self.fixture))
            self.controls["entrypoint"].setText("main.py")
            # Leave kind and format at auto to exercise the default CLI mapping.
            self.controls["inspectButton"].click()
            self.check_busy_controls()
            self.phase = "wait_inspect"

        def inspect_finished(self) -> None:
            if not self.idle():
                return
            report = self.report()
            self.require(report.get("project", {}).get("kind") == "python", "Project detection did not select Python")
            self.require(report.get("format") == "executable", "Automatic plan did not choose the native executable format")
            self.require("PLAN BUDOWANIA" in self.controls["summaryView"].toPlainText(), "The inspect-to-plan chain did not finish")
            self.require("Projekt rozpoznany" in self.controls["logView"].toPlainText(), "Inspection was not reflected in the live log")
            self.require(not self.marker.exists(), "Inspect or plan executed project code")
            self.check_idle_controls()
            self.record("inspect_and_plan_unicode_path_auto_defaults")
            combo = self.controls["outputFormat"]
            combo.setCurrentIndex(combo.findData("zipapp"))
            self.controls["smokeTestCheck"].setChecked(True)
            # A checked box must not pass --smoke-test to doctor.
            self.controls["doctorButton"].click()
            self.check_busy_controls()
            self.phase = "wait_doctor"

        def doctor_finished(self) -> None:
            if not self.idle():
                return
            report = self.report()
            self.require(report.get("ready") is True, "Environment doctor failed: " + str(report))
            self.require(isinstance(report.get("checks"), list) and all(check.get("available") for check in report["checks"]), "Required tools were not reported as available")
            summary = self.controls["summaryView"].toPlainText()
            self.require("ŚRODOWISKO" in summary and "Gotowe do budowania" in summary, "Doctor results were not presented")
            self.require(not self.marker.exists(), "Doctor executed project code")
            self.check_idle_controls()
            self.record("environment_doctor_and_smoke_flag_scoping")
            self.controls["buildButton"].click()
            self.check_busy_controls()
            self.phase = "wait_build"

        def build_finished(self) -> None:
            if not self.idle():
                return
            report = self.report()
            self.require(report.get("status") == "built", "Zipapp build failed: " + str(report))
            self.require(report.get("smoke_test", {}).get("status") == "passed", "Runtime smoke test did not pass")
            artifacts = report.get("artifacts") or []
            self.require(artifacts and all(Path(item["path"]).is_file() for item in artifacts), "Reported artifacts do not exist")
            self.require(any(Path(item["path"]).suffix == ".pyz" for item in artifacts), "Build did not produce a zipapp")
            persisted = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
            self.require(persisted["status"] == "built" and persisted["smoke_test"]["status"] == "passed", "Persisted report disagrees with the GUI result")
            self.require(self.marker.is_file() and self.marker.read_text(encoding="utf-8") == "Zażółć gęślą jaźń", "The built application did not load its packaged Unicode resource")
            self.require("GUI_SMOKE_OK" in self.controls["logView"].toPlainText(), "Runtime output did not reach the live GUI log")
            self.require("test uruchomienia zaliczony" in self.controls["statusLabel"].text(), "GUI status does not confirm the successful runtime test")
            self.check_idle_controls(has_results=True)
            self.record("zipapp_build_real_runtime_and_persisted_report")
            self.controls["openResultsButton"].click()
            self.require(self.urls.paths and self.urls.paths[-1] == Path(report["output_dir"]).resolve(), "Open results did not dispatch the correct directory through Qt")
            copy_button = next((button for button in self.window.findChildren(QPushButton) if button.text() == "Kopiuj log"), None)
            self.require(copy_button is not None, "Copy-log button is missing")
            copy_button.click()
            self.require("GUI_SMOKE_OK" in QApplication.clipboard().text(), "Copy log did not copy the live output")
            self.record("open_results_and_copy_log_buttons")
            self.capture()
            self.start_cancel_fixture()

        def start_cancel_fixture(self) -> None:
            code = (
                "import json, os, subprocess, sys, time\n"
                "from pathlib import Path\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                f"Path({str(self.cancel_pids)!r}).write_text(json.dumps({{'parent': os.getpid(), 'child': child.pid}}), encoding='utf-8')\n"
                "print('GUI_CANCEL_READY', flush=True)\n"
                "time.sleep(30)\n"
            )
            (self.fixture / "main.py").write_text(code, encoding="utf-8")
            self.controls["buildButton"].click()
            self.check_busy_controls()
            self.phase = "wait_cancel_ready"

        def cancel_when_running(self) -> None:
            if self.idle():
                raise AssertionError("Cancellation fixture finished before cancellation: " + str(self.report()))
            if "GUI_CANCEL_READY" not in self.controls["logView"].toPlainText():
                return
            self.require(self.cancel_pids.is_file(), "Cancellation fixture did not record worker PIDs")
            pids = json.loads(self.cancel_pids.read_text(encoding="utf-8"))
            self.require(all(_pid_running(pid) for pid in pids.values()), "Cancellation fixture processes were not running")
            self.cancel_started = time.monotonic()
            self.controls["cancelButton"].click()
            self.require(not self.controls["cancelButton"].isEnabled(), "Repeated cancellation remained enabled")
            self.phase = "wait_cancelled"

        def cancellation_finished(self) -> None:
            if not self.idle():
                return
            report = self.report()
            self.require(report.get("status") == "cancelled", "Cancellation did not return a cancelled report: " + str(report))
            self.require(report.get("smoke_test", {}).get("status") == "cancelled", "The cancelled runtime test was not identified")
            self.require("Anulowano" in self.controls["statusLabel"].text(), "Cancellation was not displayed in the GUI")
            self.check_idle_controls()
            self.cancel_completed = time.monotonic()
            self.require(self.cancel_completed - self.cancel_started < 15, "Cancellation took too long")
            self.record("cancel_button_stops_running_build")
            self.phase = "wait_descendants"

        def descendants_finished(self) -> None:
            pids = json.loads(self.cancel_pids.read_text(encoding="utf-8"))
            running = {name: pid for name, pid in pids.items() if _pid_running(pid)}
            if running and time.monotonic() - self.cancel_completed < 5:
                return
            self.require(not running, "Cancellation left running fixture processes: " + str(running))
            self.record("cancelled_worker_and_descendant_are_stopped")
            self.finished = True
            self.timer.stop()
            self.window.close()

        def fail(self, message: str) -> None:
            if self.failed is not None:
                return
            self.failed = f"{self.phase}: {message}"
            print("FAIL " + self.failed, file=sys.stderr, flush=True)
            self.shutdown_deadline = time.monotonic() + 20
            if self.window is None:
                self.timer.stop()
                self.app.exit(1)
                return
            if "logView" in self.controls:
                print(self.controls["logView"].toPlainText()[-6000:], file=sys.stderr, flush=True)
            if not self.screenshot_saved and args.screenshot is not None:
                try:
                    self.capture()
                except Exception:
                    pass
            # Use the window's normal cancellation/close path for cleanup.
            self.window.close()

        def tick(self) -> None:
            try:
                if self.failed is not None:
                    if self.window is None or not self.window.isVisible():
                        self.timer.stop()
                        self.app.exit(1)
                    elif time.monotonic() > self.shutdown_deadline:
                        self.window._force_stop()
                        self.shutdown_deadline = time.monotonic() + 10
                    return
                if time.monotonic() > self.deadline:
                    raise TimeoutError(f"Overall timeout ({args.timeout:g} seconds)")
                {
                    "find_window": self.begin,
                    "wait_inspect": self.inspect_finished,
                    "wait_doctor": self.doctor_finished,
                    "wait_build": self.build_finished,
                    "wait_cancel_ready": self.cancel_when_running,
                    "wait_cancelled": self.cancellation_finished,
                    "wait_descendants": self.descendants_finished,
                }[self.phase]()
            except Exception as exc:
                self.fail(str(exc))

    app = QApplication(["maxkompilator-gui-smoke"])
    with tempfile.TemporaryDirectory(prefix="maxkompilator-gui-") as temporary:
        temporary_root = Path(temporary)
        fixture = temporary_root / "projekt ze spacją Łódź"
        fixture.mkdir()
        package = fixture / "sample"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "text.txt").write_text("Zażółć gęślą jaźń", encoding="utf-8")
        marker = temporary_root / "runtime marker.txt"
        cancel_pids = temporary_root / "cancel pids.json"
        (fixture / "main.py").write_text(
            "from importlib.resources import files\n"
            "from pathlib import Path\n"
            "text = files('sample').joinpath('text.txt').read_text(encoding='utf-8')\n"
            f"Path({str(marker)!r}).write_text(text, encoding='utf-8')\n"
            "print('GUI_SMOKE_OK ' + text, flush=True)\n",
            encoding="utf-8",
        )
        harness = SmokeHarness(app, fixture, marker, cancel_pids)
        original_hook = sys.excepthook

        def exception_hook(kind: type[BaseException], value: BaseException, tb: Any) -> None:
            harness.fail("Unhandled Qt callback: " + "".join(traceback.format_exception(kind, value, tb)))

        sys.excepthook = exception_hook
        try:
            exit_code = launch_gui()
        finally:
            sys.excepthook = original_hook
            QDesktopServices.unsetUrlHandler("file")
        passed = harness.finished and harness.failed is None and exit_code == 0
        result = {
            "status": "passed" if passed else "failed",
            "checks": harness.passed,
            "duration_seconds": round(time.monotonic() - harness.started, 3),
            "cancellation_seconds": round(harness.cancel_completed - harness.cancel_started, 3) if harness.cancel_completed else None,
            "screenshot": str(args.screenshot.expanduser().resolve()) if harness.screenshot_saved else None,
            "error": harness.failed,
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
