#!/usr/bin/env python3
"""Generate the fictional starter-person 3-month trend report."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.reports.trend_report import main


if __name__ == "__main__":
    main()
