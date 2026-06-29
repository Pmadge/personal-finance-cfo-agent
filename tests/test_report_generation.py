"""Tests that reports can be regenerated from source into isolated output paths."""

from pathlib import Path
import sys

import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def extract_pdf_text(pdf_path):
    """Return all text from a generated PDF."""
    document = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in document)
    page_count = document.page_count
    document.close()
    return text, page_count


def test_monthly_report_can_regenerate_to_temp_output_folder(tmp_path):
    """Monthly report generation should not depend on a stale PDF in outputs/."""
    from modules.reports.pdf_report import build_pdf

    pdf_path = tmp_path / "monthly_report.pdf"

    generated_path = build_pdf(output_path=pdf_path, output_dir=tmp_path)
    text, page_count = extract_pdf_text(generated_path)

    assert generated_path == pdf_path
    assert generated_path.exists()
    assert page_count >= 10
    assert "Executive Summary" in text
    assert "Model Version Log" in text


def test_portfolio_demo_report_uses_richer_fictional_household(tmp_path):
    """Portfolio screenshots should be reproducible from a more complex fake household."""
    from modules.reports.pdf_report import build_pdf, portfolio_demo_report_config

    pdf_path = tmp_path / "portfolio_demo_report.pdf"
    generated_path = build_pdf(
        output_path=pdf_path,
        output_dir=tmp_path / "charts",
        report_config=portfolio_demo_report_config(),
    )
    text, page_count = extract_pdf_text(generated_path)

    assert generated_path == pdf_path
    assert generated_path.exists()
    assert page_count >= 10
    assert "Morgan Patel Household" in text
    assert "fictional Morgan Patel household data only" in text
    assert "dual income, mortgage-level housing, childcare" in text
    assert "First Home Down Payment" in text
    assert "Readiness to buy a $875,000.00 home" in text


def test_trend_report_can_regenerate_to_temp_output_folder(tmp_path):
    """Trend report generation should not depend on a stale PDF in outputs/."""
    from modules.reports.trend_report import build_pdf

    pdf_path = tmp_path / "trend_report.pdf"

    generated_path = build_pdf(output_path=pdf_path)
    text, page_count = extract_pdf_text(generated_path)

    assert generated_path == pdf_path
    assert generated_path.exists()
    assert page_count == 1
    assert "3-Month Trend Summary Report" in text
    assert "CFO Summary" in text
