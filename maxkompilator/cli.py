"""Command-line interface shared by terminal users and the desktop process."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import signal
import sys
import threading
from pathlib import Path

from . import __version__
from .adapters import create_plan
from .config import load_config
from .detection import detect_project
from .engine import execute_build
from .environment import check_environment
from .models import MaxkompilatorError, serializable


def _positive(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Podaj liczbę sekund.") from exc
    if not 0 < number <= 86400:
        raise argparse.ArgumentTypeError("Limit musi być większy od 0 i nie większy niż 86400 sekund.")
    return number


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maxkompilator", description="Maxkompilator by Swir — wykrywaj, buduj i sprawdzaj projekty.")
    parser.add_argument("--version", action="version", version=f"Maxkompilator {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (("inspect", "Rozpoznaj projekt bez wykonywania jego kodu."),
                               ("plan", "Pokaż plan bez uruchamiania narzędzi."),
                               ("doctor", "Sprawdź wymagane narzędzia."),
                               ("build", "Wykonaj budowanie i zapisz raport.")):
        item = commands.add_parser(command, help=help_text)
        item.add_argument("project", type=Path, help="Folder projektu albo pojedynczy skrypt Python.")
        item.add_argument("--kind", choices=("python", "dotnet", "android"), help="Jawny wybór adaptera.")
        item.add_argument("--entry", help="Plik startowy względem folderu projektu.")
        item.add_argument("--json", action="store_true", help="Wynik JSON na stdout; logi budowy na stderr.")
        if command != "inspect":
            item.add_argument("--target", help="np. native, windows-x64, linux-x64, macos-arm64, android.")
            item.add_argument("--format", help="np. zipapp, executable, directory, apk, aab.")
            item.add_argument("--output", type=Path, help="Katalog wynikowy; względnie do folderu projektu.")
            item.add_argument("--python", dest="python_executable", help="Interpreter używany przez adapter Python.")
        if command == "build":
            item.add_argument("--smoke-test", action="store_true", help="Uruchom utworzony program Python (wykonuje kod projektu).")
            item.add_argument("--timeout", type=_positive, default=1800.0, help="Limit pojedynczego etapu w sekundach.")
            item.add_argument("--smoke-timeout", type=_positive, default=30.0, help="Limit testu uruchomienia w sekundach.")
    commands.add_parser("gui", help="Otwórz interfejs PySide6.")
    return parser


def _python(requested: str | None) -> str:
    if requested:
        return requested
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found and Path(found).resolve() != Path(sys.executable).resolve():
            return found
    # Keep planning usable; doctor will provide a concrete missing-tool error.
    return "python"


def _emit(value: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(serializable(value), ensure_ascii=False), flush=True)
    else:
        print(json.dumps(serializable(value), indent=2, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    # stdout is a UTF-8 JSON protocol for the desktop worker even when Windows
    # pipes or a frozen launcher ignore PYTHONUTF8. Leave host-owned streams alone.
    for stream in (sys.stdout, sys.stderr):
        if type(stream) is io.TextIOWrapper and not stream.closed:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = create_parser().parse_args(argv)
    if args.command == "gui":
        try:
            from .gui import launch_gui

            return launch_gui()
        except ImportError as exc:
            print(f"GUI wymaga PySide6. Zainstaluj: python -m pip install '.[gui]'\n{exc}", file=sys.stderr)
            return 2
    try:
        config = load_config(args.project)
        project_settings = config.get("project", {})
        project = detect_project(args.project, kind=args.kind or project_settings.get("kind"),
                                 entrypoint=args.entry or project_settings.get("entry"))
        if args.command == "inspect":
            _emit({"project": project, "config": config}, as_json=args.json)
            return 0
        settings = config.get("build", {})
        python_executable = _python(args.python_executable)
        plan = create_plan(project, target=args.target or settings.get("target", "native"),
                           format=args.format or settings.get("format"),
                           output_dir=args.output if args.output is not None else settings.get("output"),
                           python_executable=python_executable)
        if args.command == "plan":
            _emit(serializable(plan), as_json=args.json)
            return 0
        if args.command == "doctor":
            result = check_environment(plan)
            _emit(result, as_json=args.json)
            return 0 if result["ready"] else 3
        event = threading.Event()
        previous_handlers = {}

        def cancel(_signum=None, _frame=None):
            event.set()

        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, cancel)

        def read_control():
            try:
                for line in sys.stdin:
                    if line.strip().lower() == "cancel":
                        event.set()
                        return
            except (OSError, ValueError):
                pass

        if sys.stdin is not None and not sys.stdin.isatty():
            threading.Thread(target=read_control, name="maxkompilator-control", daemon=True).start()
        try:
            result = execute_build(plan, cancel_event=event,
                                   on_log=lambda text: print(text, file=sys.stderr if args.json else sys.stdout, flush=True),
                                   smoke_test=args.smoke_test, timeout=args.timeout,
                                   smoke_timeout=args.smoke_timeout, python_executable=python_executable)
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
        _emit(result, as_json=args.json)
        return {"built": 0, "failed": 1, "cancelled": 130}[result["status"]]
    except (MaxkompilatorError, OSError) as exc:
        if args.json:
            _emit({"status": "error", "error": str(exc)}, as_json=True)
        else:
            print(f"Błąd: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
