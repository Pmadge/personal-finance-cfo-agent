#!/usr/bin/env python3
"""Generate README screenshots from the complex-household test persona.

The README screenshots should demonstrate the CFO engine on a realistic household,
not only the simple starter-person fixture. This script uses the fully fictional
complex-household dataset and copies selected rendered PDF pages into
docs/screenshots/ for GitHub display.
"""

from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import fitz

from modules.reports.pdf_report import (
    build_pdf,
    complex_household_report_config,
    render_pdf_for_review,
)

SCREENSHOT_TARGETS = {
    "Executive Dashboard": "report_executive_dashboard.png",
    "Cash Runway": "report_cash_runway.png",
    "Goal Tracker": "report_goal_tracker.png",
    "Risk Register": "report_risk_register.png",
    "Capital Event: Home Purchase Readiness": "report_capital_event.png",
}


def _section_pages(pdf_path):
    """Return a mapping from section titles to zero-based PDF page indexes."""
    document = fitz.open(pdf_path)
    pages = {}
    for page_index in range(document.page_count):
        text = str(document.load_page(page_index).get_text())
        lines = [line.strip() for line in text.splitlines()]
        for title in SCREENSHOT_TARGETS:
            title_positions = [index for index, line in enumerate(lines) if line == title]
            if title_positions and min(title_positions) <= 8 and title not in pages:
                pages[title] = page_index
    document.close()
    missing = sorted(set(SCREENSHOT_TARGETS) - set(pages))
    if missing:
        raise RuntimeError(f"Could not find expected report sections: {', '.join(missing)}")
    return pages


def main():
    """Regenerate GitHub-safe screenshot assets from the complex-household report."""
    output_dir = PROJECT_ROOT / "outputs" / "complex_household"
    review_dir = PROJECT_ROOT / "outputs" / "complex_household_review"
    screenshots_dir = PROJECT_ROOT / "docs" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    report_config = complex_household_report_config()
    pdf_path = build_pdf(output_dir=output_dir, report_config=report_config)
    rendered_pages = render_pdf_for_review(pdf_path, review_dir=review_dir)
    page_lookup = _section_pages(pdf_path)

    copied = []
    for section_title, screenshot_name in SCREENSHOT_TARGETS.items():
        source = rendered_pages[page_lookup[section_title]]
        destination = screenshots_dir / screenshot_name
        shutil.copyfile(source, destination)
        copied.append(destination)

    print(f"Complex-household PDF: {pdf_path}")
    print(f"Rendered review pages: {review_dir}")
    print("Updated screenshots:")
    for path in copied:
        print(f"- {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
