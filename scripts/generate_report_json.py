#!/usr/bin/env python3
"""Generate the stable report JSON contract for the UI layer.

The future local app (Streamlit first, possibly React/Tauri later) binds to this
JSON instead of recomputing anything. The deterministic Python engine owns the
numbers; this script just serializes the verified results.

Outputs (Git-ignored, regenerate on demand):
- outputs/report_json/report_<month>.json            (default Alex Rivera report)
- outputs/report_json/portfolio_demo_<month>.json    (richer Morgan household)
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.config import REPORT_MONTH
from modules.reports.pdf_report import portfolio_demo_report_config
from modules.reports.report_json import write_report_json


def main():
    """Write both the default and portfolio-demo report JSON contracts."""
    out_dir = PROJECT_ROOT / "outputs" / "report_json"
    charts_dir = PROJECT_ROOT / "outputs" / "report_json_charts"

    default_path = write_report_json(
        out_dir / f"report_{REPORT_MONTH}.json",
        output_dir=charts_dir / "default",
    )
    demo_path = write_report_json(
        out_dir / f"portfolio_demo_{REPORT_MONTH}.json",
        output_dir=charts_dir / "portfolio_demo",
        report_config=portfolio_demo_report_config(),
    )

    print("Report JSON contracts written:")
    for path in (default_path, demo_path):
        print(f"- {path.relative_to(PROJECT_ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
