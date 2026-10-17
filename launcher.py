"""Frozen desktop entry point, also used for the GUI's CLI subprocess."""

import sys

if "--cli" in sys.argv[1:]:
    sys.argv.remove("--cli")
    from maxkompilator.cli import main

    raise SystemExit(main())

if sys.argv[1:2] == ["--qualify-gui"]:
    # Explicit developer mode uses the real packaged window and console worker.
    # Keep this import static so PyInstaller collects the diagnostic harness.
    from maxkompilator.gui_qualification import main as qualify_gui

    raise SystemExit(qualify_gui(sys.argv[2:]))

from maxkompilator.gui import launch_gui

raise SystemExit(launch_gui())
