#!/usr/bin/env python3
"""Run the shared GUI qualification harness against the source checkout.

Usage: python scripts/gui_smoke.py [--screenshot qualification/gui.png]
The packaged Windows gate uses scripts/qualify_windows_gui.py instead.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from maxkompilator.gui_qualification import main


if __name__ == "__main__":
    raise SystemExit(main())
