"""Frozen desktop entry point, also used for the GUI's CLI subprocess."""

import sys

if "--cli" in sys.argv[1:]:
    sys.argv.remove("--cli")
    from maxkompilator.cli import main

    raise SystemExit(main())

from maxkompilator.gui import launch_gui

raise SystemExit(launch_gui())
