"""Optional Polish desktop interface for the shared Maxkompilator CLI.

Importing this module never imports Qt.  ``launch_gui()`` is the only entry point
that requires the ``gui`` extra.  The subprocess protocol deliberately matches
the public CLI; the window does not implement a second build engine.
"""

from __future__ import annotations

import codecs
import json
import os
from pathlib import Path
import re
import signal
import sys
from typing import Any


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_OUTPUT_TAIL_LIMIT = 2 * 1024 * 1024


def _last_json_object(output: str) -> dict[str, Any] | None:
    """Read both standalone JSON and a final JSON object after ordinary logs."""
    text = output.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except (ValueError, TypeError):
        pass
    for match in reversed(list(re.finditer(r"(?m)^[ \t]*\{", text))):
        try:
            value = json.loads(text[match.start() :])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _readable_size(value: Any) -> str:
    try:
        size = float(value)
    except (ValueError, TypeError):
        return "nieznany rozmiar"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "nieznany rozmiar"


def _report_text(report: dict[str, Any], action: str) -> str:
    """Keep build, artifact checks and runtime tests distinct in the UI."""
    lines: list[str] = []
    project = report.get("project")
    if isinstance(project, dict):
        kinds = {"python": "Python", "dotnet": "C# / .NET", "android": "Android"}
        lines.extend(
            [
                "PROJEKT",
                str(project.get("name") or "Bez nazwy"),
                "Typ: " + kinds.get(str(project.get("kind")), str(project.get("kind", "—"))),
                "Folder: " + str(project.get("root", "—")),
            ]
        )
        if project.get("entrypoint"):
            lines.append("Plik startowy: " + str(project["entrypoint"]))
        if project.get("project_file"):
            lines.append("Plik projektu: " + str(project["project_file"]))

    if action == "plan":
        lines.extend(
            [
                "",
                "PLAN BUDOWANIA",
                "Cel: " + str(report.get("target", "—")),
                "Format: " + str(report.get("format", "—")),
                "Wyniki: " + str(report.get("output_dir", "—")),
            ]
        )
        steps = report.get("steps") or []
        if isinstance(steps, list):
            for index, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    lines.append(f"{index}. {step.get('name', 'Etap budowania')}")
        if report.get("internal_builder"):
            lines.append("Budowanie wewnętrzne: " + str(report["internal_builder"]))
        requirements = report.get("requirements") or []
        if requirements:
            lines.extend(["", "WYMAGANE NARZĘDZIA"])
            for requirement in requirements:
                if isinstance(requirement, dict):
                    lines.append("• " + str(requirement.get("name", "Narzędzie")))
                    if requirement.get("hint"):
                        lines.append("  " + str(requirement["hint"]))
        notes = report.get("notes") or []
        if notes:
            lines.extend(["", "UWAGI"])
            lines.extend("• " + str(note) for note in notes)

    if action == "doctor":
        lines.extend(["ŚRODOWISKO", "Gotowe do budowania" if report.get("ready") else "Wymaga uzupełnienia"])
        checks = report.get("checks") or []
        for check in checks:
            if not isinstance(check, dict):
                continue
            available = bool(check.get("available"))
            lines.extend(["", str(check.get("name", "Narzędzie")) + " — " + ("dostępne" if available else "niedostępne")])
            if check.get("version"):
                lines.append("Wersja / lokalizacja: " + str(check["version"]))
            if check.get("error"):
                lines.append("Problem: " + str(check["error"]))
            if not available and check.get("hint"):
                lines.append("Co zrobić: " + str(check["hint"]))
        if not checks and report.get("ready"):
            lines.append("Plan nie wymaga dodatkowych narzędzi.")

    if action == "build":
        statuses = {"built": "Zbudowano", "failed": "Budowanie nieudane", "cancelled": "Anulowano"}
        lines.extend(["", "WYNIK", statuses.get(str(report.get("status")), str(report.get("status", "Brak statusu")))])
        if report.get("output_dir"):
            lines.append("Folder wyników: " + str(report["output_dir"]))
        artifacts = report.get("artifacts") or []
        if isinstance(artifacts, list):
            lines.append(f"Pliki wynikowe: {len(artifacts)}")
            for artifact in artifacts:
                if isinstance(artifact, dict):
                    path = str(artifact.get("path", "—"))
                    size = _readable_size(artifact.get("size_bytes"))
                    lines.append(f"• {path}\n  Rozmiar: {size}")
                    if artifact.get("format"):
                        lines.append("  Format: " + str(artifact["format"]))
                    if "verified" in artifact:
                        if not artifact["verified"] and artifact.get("format") == "data":
                            lines.append("  Sprawdzenie artefaktu: plik danych — zapisano sumę")
                        else:
                            lines.append("  Sprawdzenie artefaktu: " + ("zaliczone" if artifact["verified"] else "niezaliczone"))
                elif artifact:
                    lines.append("• " + str(artifact))
        smoke = report.get("smoke_test") or {}
        if isinstance(smoke, dict):
            smoke_status = str(smoke.get("status", "not_run"))
            smoke_labels = {"passed": "Zaliczony", "failed": "Niezaliczony", "not_run": "Nie wykonano"}
            lines.extend(["", "TEST URUCHOMIENIA", smoke_labels.get(smoke_status, smoke_status)])
            if smoke.get("reason"):
                lines.append(str(smoke["reason"]))
        if report.get("log_path"):
            lines.extend(["", "Plik logu: " + str(report["log_path"])])

    if report.get("error"):
        lines.extend(["", "BŁĄD", str(report["error"])])
    return "\n".join(lines).strip() or json.dumps(report, ensure_ascii=False, indent=2)


def launch_gui() -> int:
    """Launch the optional Qt GUI, returning an exit code for the CLI."""
    try:
        from PySide6.QtCore import QPoint, QProcess, QProcessEnvironment, QSize, Qt, QTimer, QUrl, Signal
        from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QPainter, QPolygon
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QSplitter,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        print(
            "Interfejs graficzny wymaga PySide6. "
            'Zainstaluj dodatek: python -m pip install "maxkompilator[gui]"\n'
            f"Szczegóły: {exc}",
            file=sys.stderr,
        )
        return 2

    class SelectionBox(QComboBox):
        """Keep the selection arrow visible with the dark native Qt theme."""

        def paintEvent(self, event: Any) -> None:
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#b4c9e5" if self.isEnabled() else "#64768f"))
            x, y = self.width() - 15, self.height() // 2
            painter.drawPolygon(QPolygon([QPoint(x - 4, y - 2), QPoint(x + 4, y - 2), QPoint(x, y + 3)]))

    class MaxkompilatorWindow(QMainWindow):
        # Expose the real process lifecycle to diagnostics before start() can
        # emit started() synchronously on Windows. No commands are substituted.
        task_process_created = Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("maxkompilatorWindow")
            self.setWindowTitle("Maxkompilator — by Swir")
            self.resize(1220, 860)
            self.setMinimumSize(930, 700)
            self._process: QProcess | None = None
            self._cleanup_process: QProcess | None = None
            self._busy = False
            self._cancel_requested = False
            self._close_after_finish = False
            self._continue_with_plan = False
            self._action = ""
            self._job_config: dict[str, Any] = {}
            self._stdout_tail = ""
            self._stream_report: dict[str, Any] | None = None
            self._line_buffers = {"stdout": "", "stderr": ""}
            self._decoders: dict[str, Any] = {}
            self._output_dir: Path | None = None
            self._own_process_session = False
            self._cancel_timer = QTimer(self)
            self._cancel_timer.setSingleShot(True)
            self._cancel_timer.timeout.connect(self._force_stop)
            self._cleanup_timer = QTimer(self)
            self._cleanup_timer.setSingleShot(True)
            self._cleanup_timer.timeout.connect(self._cleanup_timeout)

            icon_candidates = (
                Path(__file__).resolve().parent / "assets" / "maxkompilator.png",
                Path(__file__).resolve().parents[1] / "assets" / "maxkompilator.png",
            )
            icon_path = next((path for path in icon_candidates if path.is_file()), None)
            self._icon = QIcon(str(icon_path)) if icon_path else QIcon()
            self.setWindowIcon(self._icon)
            self._build_ui()

        def _build_ui(self) -> None:
            central = QWidget(self)
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(26, 22, 26, 18)
            layout.setSpacing(18)

            header = QHBoxLayout()
            logo = QLabel()
            logo.setPixmap(self._icon.pixmap(QSize(76, 76)))
            logo.setFixedSize(80, 80)
            header.addWidget(logo)
            headings = QVBoxLayout()
            headings.setSpacing(2)
            title = QLabel("Maxkompilator")
            title.setObjectName("appTitle")
            headings.addWidget(title)
            subtitle = QLabel("Jedno miejsce do budowania Twoich projektów.")
            subtitle.setObjectName("muted")
            headings.addWidget(subtitle)
            header.addLayout(headings)
            header.addStretch()
            signature = QLabel('by <a href="https://github.com/Swir" style="color:#69f1e7; text-decoration:none;">Swir ↗</a>')
            signature.setObjectName("signature")
            signature.setOpenExternalLinks(True)
            signature.setToolTip("Otwórz profil Swir na GitHubie")
            header.addWidget(signature)
            layout.addLayout(header)
            spectrum = QFrame()
            spectrum.setObjectName("spectrumLine")
            spectrum.setFixedHeight(3)
            layout.addWidget(spectrum)

            main_splitter = QSplitter(Qt.Orientation.Vertical)
            main_splitter.setChildrenCollapsible(False)
            upper = QWidget()
            upper_layout = QHBoxLayout(upper)
            upper_layout.setContentsMargins(0, 0, 0, 0)
            upper_layout.setSpacing(18)

            form = QFrame()
            form.setObjectName("card")
            form_layout = QVBoxLayout(form)
            form_layout.setContentsMargins(20, 18, 20, 18)
            form_layout.setSpacing(13)
            form_heading = QLabel("Konfiguracja projektu")
            form_heading.setObjectName("sectionTitle")
            form_layout.addWidget(form_heading)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(8)
            grid.addWidget(QLabel("Folder projektu"), 0, 0, 1, 2)
            self.project_edit = QLineEdit()
            self.project_edit.setObjectName("projectRoot")
            self.project_edit.setPlaceholderText("Wybierz folder z kodem źródłowym")
            self.project_edit.setClearButtonEnabled(True)
            self.project_edit.setToolTip("Folder zawierający pliki źródłowe i konfigurację projektu")
            self.folder_button = QPushButton("Wybierz…")
            self.folder_button.setObjectName("chooseFolderButton")
            self.folder_button.clicked.connect(self._choose_folder)
            grid.addWidget(self.project_edit, 1, 0)
            grid.addWidget(self.folder_button, 1, 1)

            grid.addWidget(QLabel("Plik startowy · opcjonalnie"), 2, 0, 1, 2)
            self.entry_edit = QLineEdit()
            self.entry_edit.setObjectName("entrypoint")
            self.entry_edit.setPlaceholderText("np. main.py — względem folderu projektu")
            self.entry_edit.setClearButtonEnabled(True)
            self.entry_button = QPushButton("Plik…")
            self.entry_button.setObjectName("chooseEntryButton")
            self.entry_button.clicked.connect(self._choose_entry)
            grid.addWidget(self.entry_edit, 3, 0)
            grid.addWidget(self.entry_button, 3, 1)
            grid.setColumnStretch(0, 1)
            form_layout.addLayout(grid)

            choices = QGridLayout()
            choices.setHorizontalSpacing(12)
            choices.setVerticalSpacing(8)
            choices.addWidget(QLabel("Rodzaj projektu"), 0, 0)
            choices.addWidget(QLabel("System docelowy"), 0, 1)
            self.kind_combo = SelectionBox()
            self.kind_combo.setObjectName("projectKind")
            for label, value in (
                ("Rozpoznaj automatycznie", "auto"),
                ("Python", "python"),
                ("C# / .NET", "dotnet"),
                ("Android (Gradle)", "android"),
            ):
                self.kind_combo.addItem(label, value)
            self.target_combo = SelectionBox()
            self.target_combo.setObjectName("targetPlatform")
            for label, value in (
                ("Bieżący system", "native"),
                ("Windows x64", "windows-x64"),
                ("Linux x64", "linux-x64"),
                ("macOS Apple Silicon", "macos-arm64"),
                ("Android", "android"),
            ):
                self.target_combo.addItem(label, value)
            self.target_combo.setToolTip("Dostępność celu zależy od projektu i zainstalowanego środowiska.")
            choices.addWidget(self.kind_combo, 1, 0)
            choices.addWidget(self.target_combo, 1, 1)
            choices.addWidget(QLabel("Format wyniku"), 2, 0, 1, 2)
            self.format_combo = SelectionBox()
            self.format_combo.setObjectName("outputFormat")
            for label, value in (
                ("Dobierz automatycznie", "auto"),
                ("Program wykonywalny", "executable"),
                ("Python ZIPAPP (.pyz)", "zipapp"),
                ("Android APK (.apk)", "apk"),
                ("Android App Bundle (.aab)", "aab"),
            ):
                self.format_combo.addItem(label, value)
            choices.addWidget(self.format_combo, 3, 0, 1, 2)
            choices.setColumnStretch(0, 1)
            choices.setColumnStretch(1, 1)
            form_layout.addLayout(choices)
            self.smoke_checkbox = QCheckBox("Test uruchomienia")
            self.smoke_checkbox.setObjectName("smokeTestCheck")
            self.smoke_checkbox.setChecked(False)
            self.smoke_checkbox.setToolTip("Po zbudowaniu uruchom wynikową aplikację Python lub .NET i sprawdź zakończenie programu. Wykonuje kod projektu.")
            form_layout.addWidget(self.smoke_checkbox)
            form_layout.addStretch()
            hint = QLabel("Sprawdź projekt, aby zobaczyć rozpoznany typ, plan budowania i wymagane narzędzia.")
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            form_layout.addWidget(hint)
            upper_layout.addWidget(form, 6)

            summary_card = QFrame()
            summary_card.setObjectName("summaryCard")
            summary_layout = QVBoxLayout(summary_card)
            summary_layout.setContentsMargins(20, 18, 20, 16)
            summary_heading = QLabel("Projekt i wynik")
            summary_heading.setObjectName("sectionTitle")
            summary_layout.addWidget(summary_heading)
            self.summary_view = QPlainTextEdit()
            self.summary_view.setObjectName("summaryView")
            self.summary_view.setReadOnly(True)
            self.summary_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.summary_view.setPlaceholderText(
                "Wybierz projekt i kliknij „Sprawdź projekt”.\n\n"
                "Tutaj pojawią się plan, wymagane narzędzia oraz wynik budowania.\n\n"
                "Raport osobno pokazuje sprawdzenie pliku i test uruchomienia aplikacji."
            )
            summary_layout.addWidget(self.summary_view)
            upper_layout.addWidget(summary_card, 5)
            main_splitter.addWidget(upper)

            log_card = QFrame()
            log_card.setObjectName("logCard")
            log_layout = QVBoxLayout(log_card)
            log_layout.setContentsMargins(18, 14, 18, 16)
            log_layout.setSpacing(10)
            log_header = QHBoxLayout()
            log_title = QLabel("Przebieg zadania")
            log_title.setObjectName("sectionTitle")
            log_header.addWidget(log_title)
            log_header.addStretch()
            self.autoscroll = QCheckBox("Przewijaj automatycznie")
            self.autoscroll.setChecked(True)
            log_header.addWidget(self.autoscroll)
            copy_log = QPushButton("Kopiuj log")
            copy_log.setObjectName("smallButton")
            copy_log.clicked.connect(self._copy_log)
            log_header.addWidget(copy_log)
            clear_log = QPushButton("Wyczyść")
            clear_log.setObjectName("smallButton")
            clear_log.clicked.connect(lambda: self.log_view.clear())
            log_header.addWidget(clear_log)
            log_layout.addLayout(log_header)
            self.log_view = QPlainTextEdit()
            self.log_view.setObjectName("logView")
            self.log_view.setReadOnly(True)
            self.log_view.setMaximumBlockCount(8000)
            self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            log_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            log_font.setPointSize(10)
            self.log_view.setFont(log_font)
            self.log_view.setPlaceholderText("Logi będą pojawiać się na żywo podczas sprawdzania i budowania.")
            log_layout.addWidget(self.log_view)
            main_splitter.addWidget(log_card)
            main_splitter.setStretchFactor(0, 3)
            main_splitter.setStretchFactor(1, 2)
            main_splitter.setSizes([390, 250])
            layout.addWidget(main_splitter, 1)

            actions = QHBoxLayout()
            actions.setSpacing(10)
            self.inspect_button = QPushButton("Sprawdź projekt")
            self.inspect_button.setObjectName("inspectButton")
            self.inspect_button.clicked.connect(self._inspect)
            self.doctor_button = QPushButton("Sprawdź środowisko")
            self.doctor_button.setObjectName("doctorButton")
            self.doctor_button.clicked.connect(self._doctor)
            self.build_button = QPushButton("Zbuduj")
            self.build_button.setObjectName("buildButton")
            self.build_button.setMinimumWidth(145)
            self.build_button.clicked.connect(self._build)
            self.cancel_button = QPushButton("Anuluj")
            self.cancel_button.setObjectName("cancelButton")
            self.cancel_button.setEnabled(False)
            self.cancel_button.clicked.connect(self._request_cancel)
            self.open_button = QPushButton("Otwórz wyniki")
            self.open_button.setObjectName("openResultsButton")
            self.open_button.setEnabled(False)
            self.open_button.clicked.connect(self._open_results)
            actions.addWidget(self.inspect_button)
            actions.addWidget(self.doctor_button)
            actions.addWidget(self.build_button)
            actions.addWidget(self.cancel_button)
            actions.addStretch()
            actions.addWidget(self.open_button)
            layout.addLayout(actions)

            status_row = QHBoxLayout()
            self.status_label = QLabel("Gotowy do wyboru projektu")
            self.status_label.setObjectName("statusLabel")
            self.status_label.setWordWrap(True)
            status_row.addWidget(self.status_label, 1)
            self.busy_indicator = QProgressBar()
            self.busy_indicator.setObjectName("busyIndicator")
            self.busy_indicator.setRange(0, 0)
            self.busy_indicator.setTextVisible(False)
            self.busy_indicator.setFixedSize(150, 6)
            self.busy_indicator.hide()
            status_row.addWidget(self.busy_indicator)
            layout.addLayout(status_row)

            self._configuration_widgets = (
                self.project_edit, self.entry_edit, self.folder_button,
                self.entry_button, self.kind_combo, self.target_combo, self.format_combo,
                self.smoke_checkbox,
            )
            self.project_edit.textChanged.connect(self._configuration_changed)
            self.entry_edit.textChanged.connect(self._configuration_changed)
            self.kind_combo.currentIndexChanged.connect(self._configuration_changed)
            self.target_combo.currentIndexChanged.connect(self._configuration_changed)
            self.format_combo.currentIndexChanged.connect(self._configuration_changed)
            self.smoke_checkbox.stateChanged.connect(self._configuration_changed)
            self.project_edit.returnPressed.connect(self._inspect)

            self.setStyleSheet("""
                QMainWindow, QWidget { background: #090d19; color: #edf0fc;
                    font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 13px; }
                QFrame#card, QFrame#summaryCard, QFrame#logCard {
                    background: #11182a; border: 1px solid #343250; border-radius: 13px; }
                QFrame#card { border-top: 2px solid #b779ff; }
                QFrame#summaryCard { border-top: 2px solid #52ded9; }
                QFrame#logCard { border-top: 2px solid #ff9873; }
                QFrame#card QLabel, QFrame#card QCheckBox,
                QFrame#summaryCard QLabel, QFrame#logCard QLabel,
                QFrame#logCard QCheckBox { background: transparent; }
                QFrame#spectrumLine { border: none; border-radius: 1px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4be8e0, stop:0.3 #8472ff, stop:0.6 #eb53d3,
                        stop:0.82 #ff956b, stop:1 #dcf586); }
                QLabel#appTitle { font-size: 31px; font-weight: 700; color: #f8f6ff; }
                QLabel#sectionTitle { font-size: 16px; font-weight: 600; color: #eae3ff; }
                QLabel#muted { color: #a3afc8; font-size: 12px; }
                QLabel#signature { color: #ada7c8; font-size: 14px; }
                QLabel#statusLabel { color: #aebbd8; font-size: 12px; }
                QLineEdit, QComboBox { min-height: 24px; padding: 7px 10px;
                    background: #0b1121; border: 1px solid #3c4564; border-radius: 7px;
                    selection-background-color: #6641a8; }
                QLineEdit:focus, QComboBox:focus { border: 1px solid #62dfdb; }
                QLineEdit:disabled, QComboBox:disabled { color: #858ca7; border-color: #303650; }
                QComboBox::drop-down { border: 0; width: 22px; }
                QComboBox QAbstractItemView { background: #182039; color: #edf0fc;
                    selection-background-color: #573a86; border: 1px solid #706396; outline: 0; }
                QPushButton { background: #202940; border: 1px solid #4b5576;
                    border-radius: 8px; padding: 10px 17px; font-weight: 600; }
                QPushButton:hover { background: #303653; border-color: #9b82df; }
                QPushButton:pressed { background: #171d35; }
                QPushButton:disabled { background: #171e30; border-color: #30374f; color: #7a839e; }
                QPushButton#inspectButton:hover, QPushButton#openResultsButton:hover { border-color: #53dcd5; }
                QPushButton#buildButton { color: white; border-color: #df90f0;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #7134cf, stop:0.55 #a629ad, stop:1 #b8276a); }
                QPushButton#buildButton:hover { border-color: #83fff0;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #8142dd, stop:0.55 #b638be, stop:1 #ce357e); }
                QPushButton#buildButton:pressed { background: #632982; }
                QPushButton#buildButton:disabled { background: #302345; border-color: #564061; color: #b1a0bb; }
                QPushButton#cancelButton:enabled { border-color: #f19b7d; color: #ffd1be; }
                QPushButton#smallButton { padding: 5px 10px; border-radius: 6px; font-size: 11px; }
                QPlainTextEdit { background: #090f1e; border: 1px solid #303a55;
                    border-radius: 8px; padding: 8px; color: #ced9f0;
                    selection-background-color: #64439b; }
                QPlainTextEdit#summaryView { background: #11182a; border: none; padding: 2px; }
                QScrollBar:vertical { background: #0d1425; width: 11px; margin: 0; }
                QScrollBar::handle:vertical { background: #65547e; min-height: 28px; border-radius: 5px; }
                QScrollBar:horizontal { background: #0d1425; height: 11px; margin: 0; }
                QScrollBar::handle:horizontal { background: #65547e; min-width: 28px; border-radius: 5px; }
                QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
                QScrollBar::add-page, QScrollBar::sub-page { background: none; }
                QSplitter::handle { background: #090d19; height: 10px; }
                QCheckBox { color: #abb8d3; font-size: 11px; spacing: 6px; }
                QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #81709e;
                    border-radius: 3px; background: #0d1426; }
                QCheckBox::indicator:checked { background: #9d52cb; border-color: #eea7ff; }
                QProgressBar { background: #272039; border: none; border-radius: 3px; }
                QProgressBar::chunk { border-radius: 3px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #52e4da, stop:0.5 #bf79f9, stop:1 #fb8aab); }
                QToolTip { color: #f3edff; background: #29273e; border: 1px solid #9380b6; padding: 5px; }
            """)

        def _configuration_changed(self, *_args: Any) -> None:
            if not self._busy:
                self._output_dir = None
                self.open_button.setEnabled(False)
                self.summary_view.clear()
                self.status_label.setText("Konfiguracja zmieniona — sprawdź projekt lub rozpocznij budowanie")

        def _choose_folder(self) -> None:
            directory = QFileDialog.getExistingDirectory(self, "Wybierz folder projektu", self.project_edit.text() or str(Path.home()))
            if directory:
                self.project_edit.setText(directory)

        def _choose_entry(self) -> None:
            selected, _ = QFileDialog.getOpenFileName(
                self, "Wybierz plik startowy", self.project_edit.text() or str(Path.home()),
                "Pliki Python (*.py *.pyw);;Wszystkie pliki (*)",
            )
            if selected:
                root = Path(self.project_edit.text()).expanduser()
                try:
                    selected = str(Path(selected).resolve().relative_to(root.resolve()))
                except (OSError, RuntimeError, ValueError):
                    pass
                self.entry_edit.setText(selected)

        def _prepare_job(self) -> bool:
            if self._busy or self._cleanup_process is not None:
                return False
            raw_root = self.project_edit.text().strip()
            if not raw_root:
                QMessageBox.information(self, "Wybierz projekt", "Najpierw wskaż folder projektu.")
                self.project_edit.setFocus()
                return False
            try:
                root = Path(raw_root).expanduser().resolve()
                root_exists = root.is_dir()
            except (OSError, RuntimeError, ValueError):
                root_exists = False
            if not root_exists:
                QMessageBox.warning(self, "Folder nie istnieje", "Wskazany folder projektu nie istnieje lub jest niedostępny.")
                return False
            self._job_config = {
                "root": str(root), "entry": self.entry_edit.text().strip(),
                "kind": str(self.kind_combo.currentData()),
                "target": str(self.target_combo.currentData()),
                "format": str(self.format_combo.currentData()),
                "smoke_test": self.smoke_checkbox.isChecked(),
            }
            self._cancel_requested = False
            self._output_dir = None
            self.open_button.setEnabled(False)
            self.summary_view.clear()
            self.log_view.clear()
            return True

        def _inspect(self) -> None:
            if self._prepare_job():
                self._continue_with_plan = True
                self._start_action("inspect")

        def _build(self) -> None:
            if self._prepare_job():
                self._continue_with_plan = False
                self._start_action("build")

        def _doctor(self) -> None:
            if self._prepare_job():
                self._continue_with_plan = False
                self._start_action("doctor")

        def _set_busy(self, busy: bool) -> None:
            self._busy = busy
            for widget in self._configuration_widgets:
                widget.setEnabled(not busy)
            self.inspect_button.setEnabled(not busy)
            self.doctor_button.setEnabled(not busy)
            self.build_button.setEnabled(not busy)
            self.cancel_button.setEnabled(busy and not self._cancel_requested)
            self.busy_indicator.setVisible(busy)
            self.open_button.setEnabled(not busy and self._output_dir is not None)

        def _start_action(self, action: str) -> None:
            if self._cancel_requested:
                self._finish_job("Anulowano zadanie")
                return
            self._action = action
            self._stdout_tail = ""
            self._stream_report = None
            self._line_buffers = {"stdout": "", "stderr": ""}
            self._decoders = {channel: codecs.getincrementaldecoder("utf-8")("replace") for channel in self._line_buffers}
            labels = {"inspect": "Rozpoznawanie projektu…", "plan": "Przygotowywanie planu budowania…", "doctor": "Sprawdzanie środowiska…", "build": "Budowanie projektu…"}
            self.status_label.setText(labels[action])
            self._append_log(labels[action])
            self._set_busy(True)
            config = self._job_config
            frozen = bool(getattr(sys, "frozen", False))
            program = sys.executable
            if frozen and sys.platform == "win32":
                # The desktop EXE is windowed. Its console sibling preserves
                # stdin/stdout/stderr for the QProcess control and JSON protocol.
                worker = Path(sys.executable).with_name("MaxkompilatorCLI.exe")
                if worker.is_file():
                    program = str(worker)
                else:
                    # Preserve older single-EXE console distributions. A
                    # windowed fallback without a report remains unconfirmed.
                    self._append_log(
                        "Nie znaleziono MaxkompilatorCLI.exe obok aplikacji. "
                        "Uruchamiam silnik w bieżącym EXE w trybie zgodności."
                    )
            args = ["--cli"] if frozen else ["-m", "maxkompilator"]
            args.extend([action, config["root"]])
            if config["kind"] != "auto":
                args.extend(["--kind", config["kind"]])
            if config["entry"]:
                args.extend(["--entry", config["entry"]])
            if action != "inspect":
                args.extend(["--target", config["target"]])
                if config["format"] != "auto":
                    args.extend(["--format", config["format"]])
            if action == "build" and config["smoke_test"]:
                args.append("--smoke-test")
            args.append("--json")
            process = QProcess(self)
            self._process = process
            process.setProgram(program)
            process.setArguments(args)
            # From a source checkout, -m must resolve our package regardless of
            # the chosen project's directory. Each build step sets its own cwd.
            process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
            environment = QProcessEnvironment.systemEnvironment()
            environment.insert("PYTHONUNBUFFERED", "1")
            environment.insert("PYTHONIOENCODING", "utf-8")
            process.setProcessEnvironment(environment)
            self._own_process_session = False
            if os.name == "posix" and hasattr(process, "setUnixProcessParameters"):
                flags = getattr(QProcess, "UnixProcessFlag", None)
                new_session = getattr(flags, "CreateNewSession", None)
                if new_session is not None:
                    process.setUnixProcessParameters(new_session)
                    self._own_process_session = True
            process.readyReadStandardOutput.connect(lambda: self._read_stream(process, "stdout"))
            process.readyReadStandardError.connect(lambda: self._read_stream(process, "stderr"))
            process.finished.connect(lambda code, status: self._process_finished(process, code, status))
            process.errorOccurred.connect(lambda error: self._process_error(process, error))
            process.started.connect(lambda: self._process_started(process))
            self.task_process_created.emit(process)
            process.start()

        def _process_started(self, process: QProcess) -> None:
            if process is self._process and self._cancel_requested:
                process.write(b"cancel\n")

        def _read_stream(self, process: QProcess, channel: str, final: bool = False) -> None:
            if process is not self._process:
                return
            data = bytes(process.readAllStandardOutput() if channel == "stdout" else process.readAllStandardError())
            decoded = self._decoders[channel].decode(data, final=final)
            if channel == "stdout":
                self._stdout_tail = (self._stdout_tail + decoded)[-_OUTPUT_TAIL_LIMIT:]
            self._line_buffers[channel] += decoded.replace("\r\n", "\n").replace("\r", "\n")
            lines = self._line_buffers[channel].split("\n")
            self._line_buffers[channel] = "" if final else lines.pop()
            if not final and len(self._line_buffers[channel]) > 256 * 1024:
                lines.append(self._line_buffers[channel])
                self._line_buffers[channel] = ""
            visible = []
            for line in lines:
                if channel == "stdout" and line.lstrip().startswith("{"):
                    report = _last_json_object(line)
                    if report is not None:
                        self._stream_report = report
                        continue
                if line:
                    visible.append(line)
            if visible:
                self._append_log("\n".join(visible))

        def _append_log(self, text: str) -> None:
            scrollbar = self.log_view.verticalScrollBar()
            old_position = scrollbar.value()
            self.log_view.appendPlainText(_ANSI_ESCAPE.sub("", text))
            scrollbar.setValue(scrollbar.maximum() if self.autoscroll.isChecked() else old_position)

        def _process_error(self, process: QProcess, error: Any) -> None:
            if process is not self._process:
                return
            if error == QProcess.ProcessError.FailedToStart:
                message = "Nie udało się uruchomić silnika: " + process.errorString()
                self._append_log(message)
                self.summary_view.setPlainText(message)
                self._process = None
                process.deleteLater()
                self._finish_job("Nie udało się uruchomić zadania")
            elif error == QProcess.ProcessError.Crashed and not self._cancel_requested:
                self._append_log("Proces silnika zakończył się nieoczekiwanie: " + process.errorString())

        def _process_finished(self, process: QProcess, exit_code: int, _exit_status: Any) -> None:
            if process is not self._process:
                return
            for channel in ("stdout", "stderr"):
                self._read_stream(process, channel, final=True)
            report = _last_json_object(self._stdout_tail) or self._stream_report
            action = self._action
            self._process = None
            process.deleteLater()
            self._cancel_timer.stop()
            if report is not None:
                self.summary_view.setPlainText(_report_text(report, action))
            if self._cancel_requested or (report and report.get("status") == "cancelled"):
                self._append_log("Zadanie anulowane.")
                self._finish_job("Anulowano zadanie")
                return
            if action == "doctor" and report is not None and "ready" in report:
                if report["ready"] and exit_code == 0:
                    message = "Środowisko gotowe — wymagane narzędzia są dostępne"
                else:
                    message = "Środowisko niegotowe — sprawdź brakujące narzędzia w raporcie"
                self._append_log(message + ".")
                self._finish_job(message)
                return
            if exit_code != 0 or (report and report.get("status") == "failed"):
                message = str(report.get("error") or "Szczegóły błędu znajdują się w logu.") if report else "Szczegóły błędu znajdują się w logu."
                self._append_log(f"Zadanie nie powiodło się (kod {exit_code}). {message}")
                self._finish_job("Zadanie nieudane — sprawdź raport i log")
                return
            if report is None:
                self._append_log("Silnik zakończył pracę bez poprawnego raportu JSON. Wynik nie został potwierdzony.")
                self._finish_job("Brak raportu — wynik niepotwierdzony")
                return
            if action == "inspect" and self._continue_with_plan:
                self._continue_with_plan = False
                self._append_log("Projekt rozpoznany. Przygotowuję plan i listę wymaganych narzędzi.")
                QTimer.singleShot(0, lambda: self._start_action("plan"))
                return
            if action == "build":
                output = report.get("output_dir")
                if output:
                    candidate = Path(str(output)).expanduser()
                    if not candidate.is_absolute():
                        candidate = Path(self._job_config["root"]) / candidate
                    if candidate.is_dir():
                        self._output_dir = candidate.resolve()
                if report.get("status") != "built":
                    self._append_log("Raport nie potwierdził ukończenia budowania.")
                    self._finish_job("Wynik budowania wymaga sprawdzenia")
                    return
                smoke = report.get("smoke_test") or {}
                smoke_status = smoke.get("status", "not_run") if isinstance(smoke, dict) else "not_run"
                if smoke_status == "passed":
                    message = "Zbudowano — test uruchomienia zaliczony"
                elif smoke_status == "failed":
                    message = "Zbudowano — test uruchomienia niezaliczony"
                else:
                    message = "Zbudowano — testu uruchomienia nie wykonano"
                self._append_log(message + ".")
                self._finish_job(message)
            else:
                self._append_log("Plan przygotowany. Wymagane narzędzia są wymienione w podsumowaniu.")
                self._finish_job("Plan gotowy — możesz rozpocząć budowanie")

        def _finish_job(self, message: str) -> None:
            self._cancel_timer.stop()
            self._continue_with_plan = False
            self._set_busy(self._cleanup_process is not None)
            self.status_label.setText(message)
            if self._close_after_finish and self._cleanup_process is None:
                QTimer.singleShot(0, self.close)

        def _request_cancel(self) -> None:
            if not self._busy or self._cancel_requested:
                return
            self._cancel_requested = True
            self._continue_with_plan = False
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Trwa bezpieczne zatrzymywanie zadania…")
            self._append_log("Wysłano prośbę o anulowanie. Czekam na zakończenie procesów budowania…")
            if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
                # The core owns compiler subprocesses and cleans them up before
                # returning its cancellation report. Keep stdin open for this.
                self._process.write(b"cancel\n")
                self._cancel_timer.start(12000)
            else:
                self._finish_job("Anulowano zadanie")

        def _force_stop(self) -> None:
            process = self._process
            if process is None or process.state() == QProcess.ProcessState.NotRunning:
                return
            pid = int(process.processId())
            if pid <= 0:
                process.kill()
                return
            self._append_log("Silnik nie zakończył anulowania w wyznaczonym czasie. Zatrzymuję pozostałe procesy zadania.")
            self.status_label.setText("Zatrzymywanie pozostałych procesów…")
            cleanup = QProcess(self)
            self._cleanup_process = cleanup
            cleanup.errorOccurred.connect(lambda error: self._cleanup_error(cleanup, error))
            if os.name == "nt":
                cleanup.finished.connect(lambda _code, _status: self._windows_cleanup_finished(cleanup))
                cleanup.start("taskkill", ["/PID", str(pid), "/T", "/F"])
            else:
                # Child tools may create their own process groups. Inspect the
                # descendant tree before killing the launcher so they remain
                # discoverable even when they do not inherit its session.
                cleanup.finished.connect(lambda _code, _status: self._posix_cleanup_finished(cleanup, pid))
                cleanup.start("ps", ["-A", "-o", "pid=", "-o", "ppid="])
            self._cleanup_timer.start(5000)

        def _cleanup_error(self, cleanup: QProcess, error: Any) -> None:
            if cleanup is self._cleanup_process and error == QProcess.ProcessError.FailedToStart:
                self._append_log("Narzędzie zatrzymywania procesów jest niedostępne: " + cleanup.errorString())
                self._kill_launcher_group()
                self._finish_cleanup(cleanup)

        def _windows_cleanup_finished(self, cleanup: QProcess) -> None:
            if cleanup is not self._cleanup_process:
                return
            diagnostic = bytes(cleanup.readAllStandardOutput()) + bytes(cleanup.readAllStandardError())
            if diagnostic:
                self._append_log(diagnostic.decode("utf-8", "replace").strip())
            self._kill_launcher_group()
            self._finish_cleanup(cleanup)

        def _posix_cleanup_finished(self, cleanup: QProcess, root_pid: int) -> None:
            if cleanup is not self._cleanup_process:
                return
            relations: dict[int, list[int]] = {}
            for line in bytes(cleanup.readAllStandardOutput()).decode("ascii", "replace").splitlines():
                fields = line.split()
                if len(fields) == 2 and all(field.isdigit() for field in fields):
                    child, parent = map(int, fields)
                    relations.setdefault(parent, []).append(child)
            descendants: list[int] = []
            pending = list(relations.get(root_pid, []))
            seen = {root_pid, os.getpid()}
            while pending:
                child = pending.pop()
                if child in seen:
                    continue
                seen.add(child)
                descendants.append(child)
                pending.extend(relations.get(child, []))
            for child in reversed(descendants):
                try:
                    os.kill(child, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            self._kill_launcher_group()
            self._finish_cleanup(cleanup)

        def _kill_launcher_group(self) -> None:
            process = self._process
            if process is None or process.state() == QProcess.ProcessState.NotRunning:
                return
            pid = int(process.processId())
            if os.name == "posix" and pid > 0 and self._own_process_session:
                try:
                    if os.getpgid(pid) == pid:
                        os.killpg(pid, signal.SIGKILL)
                        return
                except (ProcessLookupError, PermissionError):
                    pass
            process.kill()

        def _cleanup_timeout(self) -> None:
            cleanup = self._cleanup_process
            if cleanup is None:
                return
            self._append_log("Przekroczono czas narzędzia zatrzymywania procesów.")
            cleanup.kill()
            self._kill_launcher_group()

        def _finish_cleanup(self, cleanup: QProcess) -> None:
            if cleanup is not self._cleanup_process:
                return
            self._cleanup_timer.stop()
            self._cleanup_process = None
            cleanup.deleteLater()
            if self._process is None:
                self._set_busy(False)
            if self._close_after_finish and not self._busy:
                QTimer.singleShot(0, self.close)

        def _copy_log(self) -> None:
            QApplication.clipboard().setText(self.log_view.toPlainText())

        def _open_results(self) -> None:
            if self._output_dir is not None and self._output_dir.is_dir():
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._output_dir))):
                    QMessageBox.information(self, "Folder wyników", "Otwórz folder wyników:\n" + str(self._output_dir))
            else:
                self.open_button.setEnabled(False)
                QMessageBox.information(self, "Brak folderu wyników", "Folder wyników nie istnieje lub jest niedostępny.")

        def closeEvent(self, event: Any) -> None:
            if self._busy or self._cleanup_process is not None:
                event.ignore()
                self._close_after_finish = True
                self._request_cancel()
                self.status_label.setText("Kończenie zadania przed zamknięciem okna…")
                return
            event.accept()

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("Maxkompilator")
    app.setOrganizationName("Swir")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = MaxkompilatorWindow()
    app.setWindowIcon(window.windowIcon())
    window.show()
    return app.exec()
