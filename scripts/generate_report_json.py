#!/usr/bin/env python3
"""Generate stable report JSON contracts for the UI layer.

The local app binds to these JSON files instead of recomputing anything. The
deterministic Python engine owns the numbers; this script serializes verified
results into each committed test persona folder.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.reports.pdf_report import portfolio_demo_report_config
from modules.reports.report_json import write_report_json


def main():
    """Write report JSON contracts next to each test persona's run outputs."""
    personas_root = PROJECT_ROOT / "test_personas"

    default_path = write_report_json(
        personas_root / "starter_person" / "outputs" / "report.json",
        output_dir=personas_root / "starter_person" / "outputs" / "charts",
    )
    demo_path = write_report_json(
        personas_root / "complex_household" / "outputs" / "report.json",
        output_dir=personas_root / "complex_household" / "outputs" / "charts",
        report_config=portfolio_demo_report_config(),
    )

    print("Report JSON contracts written:")
    for path in (default_path, demo_path):
        print(f"- {path.relative_to(PROJECT_ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
