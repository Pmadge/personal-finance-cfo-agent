"""Tests for turning reviewed fake personal rows into draft personal reports."""

from argparse import Namespace
from pathlib import Path
import subprocess
import sys

import fitz
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.config import APPROVED_CATEGORIES, SAMPLE_PERSONAL_PROFILE

SCRIPT = PROJECT_ROOT / "scripts" / "generate_personal_report.py"


def reviewed_rows():
    return pd.DataFrame(
        [
            {
                "date": "2026-04-01",
                "vendor": "Fake Payroll Deposit",
                "amount": 2500.00,
                "raw_category": "income",
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 2,
                "import_batch_id": "import_fake123",
                "transaction_id": "fake_txn_001",
                "suggested_category": "Income",
                "classification_method": "raw_category_map",
                "review_status": "auto_suggested",
                "final_category": "Income",
                "override_note": "",
            },
            {
                "date": "2026-04-02",
                "vendor": "Fake Grocery Market",
                "amount": -73.42,
                "raw_category": "groceries",
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 3,
                "import_batch_id": "import_fake123",
                "transaction_id": "fake_txn_002",
                "suggested_category": "Food & Dining",
                "classification_method": "raw_category_map",
                "review_status": "manual_override",
                "final_category": "Food & Dining",
                "override_note": "Fake correction",
            },
        ]
    )


def extract_pdf_text(pdf_path):
    document = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in document)
    page_count = document.page_count
    document.close()
    return text, page_count


def test_reviewed_rows_become_report_ready_transactions():
    """Reviewed final categories should become the deterministic assigned_category field."""
    from modules.personal_report_inputs import build_report_transactions_from_review

    report_df = build_report_transactions_from_review(reviewed_rows())

    assert list(report_df["assigned_category"]) == ["Income", "Food & Dining"]
    assert "final_category" not in report_df.columns
    assert "suggested_category" not in report_df.columns
    assert set(["date", "vendor", "amount", "raw_category", "assigned_category", "classification_method"]).issubset(report_df.columns)
    assert report_df["assigned_category"].isin(APPROVED_CATEGORIES).all()


def test_reviewed_rows_fail_closed_on_blank_final_category():
    """Reports should not be generated while any reviewed row still needs a category."""
    from modules.personal_report_inputs import build_report_transactions_from_review

    review_df = reviewed_rows()
    review_df.loc[1, "final_category"] = ""

    with pytest.raises(ValueError, match="blank final_category"):
        build_report_transactions_from_review(review_df)


def test_reviewed_rows_fail_closed_on_invalid_final_category():
    """Only approved final categories should become report data."""
    from modules.personal_report_inputs import build_report_transactions_from_review

    review_df = reviewed_rows()
    review_df.loc[1, "final_category"] = "AI Guess Category"

    with pytest.raises(ValueError, match="Invalid final_category"):
        build_report_transactions_from_review(review_df)


def test_personal_report_self_checks_allow_distinct_transactions_with_same_visible_fields():
    """Two same-date/same-vendor/same-amount card charges can be valid when transaction IDs differ."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[1, ["date", "vendor", "amount", "raw_category", "final_category"]] = [
        review_df.loc[0, "date"],
        review_df.loc[0, "vendor"],
        review_df.loc[0, "amount"],
        review_df.loc[0, "raw_category"],
        review_df.loc[0, "final_category"],
    ]
    review_df.loc[0, "transaction_id"] = "same_visible_001"
    review_df.loc[1, "transaction_id"] = "same_visible_002"

    report_df = build_report_transactions_from_review(review_df)

    checks = assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)
    assert checks["Status"].eq("PASS").all()


def test_progress_memory_appends_snapshot_and_delta(tmp_path):
    """Each personal report run should leave a local history record and comparison."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.progress_memory import build_progress_snapshot, append_progress_snapshot

    report_df = build_report_transactions_from_review(reviewed_rows())
    history_path = tmp_path / "progress_history.json"

    first = build_progress_snapshot(
        report_df,
        profile=SAMPLE_PERSONAL_PROFILE,
        report_path="outputs/personal/first.pdf",
        run_timestamp="2026-04-30T00:00:00+00:00",
    )
    second_df = report_df.copy()
    second_df.loc[0, "amount"] = 3000.0
    second = build_progress_snapshot(
        second_df,
        profile=SAMPLE_PERSONAL_PROFILE,
        report_path="outputs/personal/second.pdf",
        run_timestamp="2026-05-31T00:00:00+00:00",
    )

    append_progress_snapshot(history_path, first)
    manifest = append_progress_snapshot(history_path, second)

    assert [entry["report_file"] for entry in manifest["snapshots"]] == ["first.pdf", "second.pdf"]
    assert manifest["latest_comparison"]["net_cash_flow_change"] == 500.0
    assert manifest["latest_comparison"]["savings_rate_change"] > 0
    assert manifest["snapshots"][-1]["metrics"]["debt_total"] == 18000.0


def test_personal_report_script_writes_progress_history(tmp_path):
    """Successful personal report generation should save local progress memory."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_progress_memory_report.pdf"
    history_path = PROJECT_ROOT / "outputs" / "personal" / "test_progress_history.json"
    output_path.unlink(missing_ok=True)
    history_path.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--history",
                str(history_path),
                "--allow-unsafe-input-for-tests",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        assert "Wrote progress history" in result.stdout
        assert history_path.exists()
    finally:
        output_path.unlink(missing_ok=True)
        history_path.unlink(missing_ok=True)


def test_personal_report_script_writes_draft_pdf_to_private_output(tmp_path):
    """The draft personal report script should create an inspectable PDF from reviewed fake data."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_personal_report_draft.pdf"
    output_path.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--allow-unsafe-input-for-tests",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        text, page_count = extract_pdf_text(output_path)
        assert "Wrote draft personal report" in result.stdout
        assert page_count >= 1
        assert "Draft Personal CFO Report" in text
        assert "Fake Payroll Deposit" in text
        assert "Food & Dining" in text
        assert "sample or fictional data only" in text.lower()
    finally:
        output_path.unlink(missing_ok=True)


def test_documented_default_flow_generates_report_without_hidden_flags():
    """The exact README flow should work with sample data and no test-only flags."""
    output_path = PROJECT_ROOT / "outputs" / "personal" / "personal_cfo_report_draft.pdf"

    close_result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "monthly_close.py"), "--sample"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    report_result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    text, page_count = extract_pdf_text(output_path)
    assert "Monthly close sample workflow complete" in close_result.stdout
    assert "Wrote draft personal report" in report_result.stdout
    assert output_path.exists()
    assert page_count >= 1
    assert "Draft Personal CFO Report" in text


def test_spending_by_category_table_excludes_income(tmp_path):
    """Income is not spending, so the Spending by Category table must omit it.

    Regression guard: the chart already excluded income, but the table did not,
    which showed a misleading "Income $0.00" row in the draft report.
    """
    from modules.personal_report_inputs import build_report_transactions_from_review
    from scripts.generate_personal_report import build_draft_personal_report

    report_df = build_report_transactions_from_review(reviewed_rows())
    output_path = tmp_path / "spending_table_report.pdf"
    charts_dir = tmp_path / "spending_table_charts"
    build_draft_personal_report(report_df, output_path, charts_dir)

    text, _ = extract_pdf_text(output_path)
    section_start = text.index("Spending by Category")
    section_end = text.index("Reviewed Transactions", section_start)
    spending_section = text[section_start:section_end]

    # The one expense in reviewed_rows() is Food & Dining; income must not appear.
    assert "Food & Dining" in spending_section
    assert "Income" not in spending_section


def test_personal_report_includes_full_pillar_suite(tmp_path):
    """The personal report must carry the CFO pillars, not just the basic snapshot."""
    from scripts.generate_personal_report import build_draft_personal_report
    from modules.personal_report_inputs import build_report_transactions_from_review

    report_df = build_report_transactions_from_review(reviewed_rows())
    output_path = tmp_path / "pillar_personal_report.pdf"
    charts_dir = tmp_path / "pillar_personal_charts"
    build_draft_personal_report(report_df, output_path, charts_dir)

    text, _ = extract_pdf_text(output_path)
    for section in [
        "Executive Dashboard",
        "Cash Runway",
        "12-Month Cash Projection",
        "Goal Tracker",
        "What-If Scenarios",
        "Risk Register",
        "Home Purchase Readiness",
    ]:
        assert section in text, section
    # Emoji are converted for the PDF font, not left as raw glyphs.
    assert "🟢" not in text and "🔴" not in text


def test_personal_report_handles_empty_goal_profile(tmp_path):
    """A valid local profile with no goals should render a dashboard fallback."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from scripts.generate_personal_report import build_draft_personal_report

    report_df = build_report_transactions_from_review(reviewed_rows())
    profile = {key: value for key, value in SAMPLE_PERSONAL_PROFILE.items()}
    profile["goals"] = []
    output_path = tmp_path / "no_goals_personal_report.pdf"
    charts_dir = tmp_path / "no_goals_charts"

    build_draft_personal_report(report_df, output_path, charts_dir, profile=profile)

    text, _ = extract_pdf_text(output_path)
    assert "Executive Dashboard" in text
    assert "No goals configured" in text


def test_personal_report_pdf_excludes_source_identity_fields(tmp_path):
    """Traceability belongs in audit artifacts, not the human-facing report body."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_clean_personal_report_draft.pdf"
    output_path.unlink(missing_ok=True)

    try:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--allow-unsafe-input-for-tests",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        text, _ = extract_pdf_text(output_path)
        forbidden_terms = [
            "source_file",
            "source_row_number",
            "import_batch_id",
            "transaction_id",
            "personal_transactions_template.csv",
            "import_fake123",
            "fake_txn_001",
            "fake_txn_002",
        ]
        for term in forbidden_terms:
            assert term not in text
    finally:
        output_path.unlink(missing_ok=True)


def test_personal_report_includes_visual_snapshot_and_chart_artifacts(tmp_path):
    """The report should go beyond a bank-app table by adding charts and insight labels."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_visual_personal_report_draft.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "test_charts"
    expected_charts = [
        charts_dir / "personal_spending_by_category.png",
        charts_dir / "personal_cash_flow_waterfall.png",
    ]
    output_path.unlink(missing_ok=True)
    for chart in expected_charts:
        chart.unlink(missing_ok=True)

    try:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--charts-dir",
                str(charts_dir),
                "--allow-unsafe-input-for-tests",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        text, page_count = extract_pdf_text(output_path)
        assert page_count >= 2
        assert "Visual CFO Snapshot" in text
        assert "Largest Spending Category" in text
        assert "Cash Flow Waterfall" in text
        for chart in expected_charts:
            assert chart.exists(), chart
            assert chart.stat().st_size > 5_000, chart
    finally:
        output_path.unlink(missing_ok=True)
        for chart in expected_charts:
            chart.unlink(missing_ok=True)
        charts_dir.rmdir() if charts_dir.exists() and not any(charts_dir.iterdir()) else None


def test_personal_report_self_checks_pass_for_clean_reviewed_rows():
    """Clean fake reviewed rows should produce compact PASS self-check rows before rendering."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    report_df = build_report_transactions_from_review(review_df)

    checks = assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)

    assert set(checks["Status"]) == {"PASS"}
    assert set(checks["Check"]) == {
        "Reviewed rows ready for report",
        "No duplicate personal report transactions",
        "Transaction schema contract",
        "Approved category contract",
        "Personal report cash-flow arithmetic",
    }


def test_personal_report_self_checks_fail_on_duplicate_transaction_id():
    """Rows sharing a source transaction ID should not reach final statements."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[1, "transaction_id"] = "fake_txn_001"
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Duplicate source transaction IDs"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_fail_on_duplicate_source_row_identity():
    """The same imported source row should not be counted twice."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[1, "source_file"] = "personal_transactions_template.csv"
    review_df.loc[1, "source_row_number"] = 2
    review_df.loc[1, "import_batch_id"] = "import_fake123"
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Duplicate source row identities"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_normalize_duplicate_transaction_ids():
    """Whitespace/case variants of source transaction IDs should still fail closed."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[0, "transaction_id"] = " Fake_Txn_001 "
    review_df.loc[1, "transaction_id"] = "fake_txn_001"
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Duplicate source transaction IDs"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_normalize_source_row_numbers_from_csv_text():
    """CSV-read source row numbers represented as text should still dedupe."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows().astype({"source_row_number": str})
    review_df.loc[1, "source_file"] = "personal_transactions_template.csv"
    review_df.loc[1, "source_row_number"] = "2"
    review_df.loc[1, "import_batch_id"] = "import_fake123"
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Duplicate source row identities"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_fail_on_duplicate_final_statement_rows():
    """Exact final-statement duplicates should fail even when source IDs are blank."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = pd.concat([reviewed_rows(), reviewed_rows().iloc[[1]]], ignore_index=True)
    review_df.loc[:, "transaction_id"] = ""
    review_df.loc[:, "source_file"] = ["file_a.csv", "file_a.csv", "file_b.csv"]
    review_df.loc[:, "source_row_number"] = [2, 3, 8]
    review_df.loc[:, "import_batch_id"] = ["batch_a", "batch_a", "batch_b"]
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Duplicate final statement rows"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_fail_on_rows_still_needing_review():
    """Even valid final categories should not bypass rows explicitly marked needs_review."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[1, "review_status"] = "needs_review"
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Reviewed rows ready for report"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_self_checks_normalize_needs_review_status():
    """Whitespace/case variants of needs_review should still fail closed."""
    from modules.personal_report_inputs import build_report_transactions_from_review
    from modules.self_checks import assert_personal_report_self_checks

    review_df = reviewed_rows()
    review_df.loc[1, "review_status"] = " Needs_Review "
    report_df = build_report_transactions_from_review(review_df)

    with pytest.raises(ValueError, match="Rows still marked needs_review: 1"):
        assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)


def test_personal_report_script_runs_self_checks_before_render(monkeypatch, tmp_path):
    """A future refactor should not move PDF/chart rendering ahead of the gate."""
    import scripts.generate_personal_report as report_script

    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_order_guard.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "test_order_guard_charts"
    output_path.unlink(missing_ok=True)
    calls = []
    original_assert = report_script.assert_personal_report_self_checks

    def recording_assert(*args, **kwargs):
        calls.append("self_check")
        return original_assert(*args, **kwargs)

    def fake_render(report_df, output, charts, **_kwargs):
        calls.append("render")
        return Path(output)

    monkeypatch.setattr(
        report_script,
        "parse_args",
        lambda: Namespace(
            reviewed_input=review_path,
            output=output_path,
            charts_dir=charts_dir,
            history=PROJECT_ROOT / "outputs" / "personal" / "test_order_guard_history.json",
            allow_unsafe_input_for_tests=True,
        ),
    )
    monkeypatch.setattr(report_script, "assert_personal_report_self_checks", recording_assert)
    monkeypatch.setattr(report_script, "build_draft_personal_report", fake_render)

    try:
        report_script.main()

        assert calls == ["self_check", "render"]
        assert not output_path.exists()
    finally:
        output_path.unlink(missing_ok=True)
        if charts_dir.exists():
            for child in charts_dir.iterdir():
                child.unlink()
            charts_dir.rmdir()


def test_personal_report_script_duplicate_failure_writes_no_artifacts(tmp_path):
    """Duplicate rows should fail before final statement artifacts are written."""
    review_df = reviewed_rows()
    review_df.loc[1, "transaction_id"] = "fake_txn_001"
    review_path = tmp_path / "category_review_applied.csv"
    review_df.to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_duplicate.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_duplicate_charts"
    output_path.unlink(missing_ok=True)
    if charts_dir.exists():
        for child in charts_dir.iterdir():
            child.unlink()
        charts_dir.rmdir()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reviewed-input",
            str(review_path),
            "--output",
            str(output_path),
            "--charts-dir",
            str(charts_dir),
            "--allow-unsafe-input-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Duplicate source transaction IDs" in result.stderr
    assert not output_path.exists()
    assert not charts_dir.exists()


def test_personal_report_script_self_check_failure_writes_no_artifacts(tmp_path):
    """The CLI should fail before writing PDF/charts if reviewed rows are not report-ready."""
    review_df = reviewed_rows()
    review_df.loc[1, "review_status"] = "needs_review"
    review_path = tmp_path / "category_review_applied.csv"
    review_df.to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_self_check.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_self_check_charts"
    output_path.unlink(missing_ok=True)
    if charts_dir.exists():
        for child in charts_dir.iterdir():
            child.unlink()
        charts_dir.rmdir()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reviewed-input",
            str(review_path),
            "--output",
            str(output_path),
            "--charts-dir",
            str(charts_dir),
            "--allow-unsafe-input-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Personal report self-checks failed" in result.stderr
    assert not output_path.exists()
    assert not charts_dir.exists()


def test_personal_report_script_prints_self_check_success(tmp_path):
    """Successful report generation should make the pre-render gate visible to users."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_self_check_success.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "test_self_check_success_charts"
    output_path.unlink(missing_ok=True)
    if charts_dir.exists():
        for child in charts_dir.iterdir():
            child.unlink()
        charts_dir.rmdir()

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--charts-dir",
                str(charts_dir),
                "--allow-unsafe-input-for-tests",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        assert "Personal report self-checks passed" in result.stdout
        assert output_path.exists()
        assert charts_dir.exists()
    finally:
        output_path.unlink(missing_ok=True)
        if charts_dir.exists():
            for child in charts_dir.iterdir():
                child.unlink()
            charts_dir.rmdir()


def test_personal_report_script_rejects_unsafe_charts_dir(tmp_path):
    """Chart artifacts are private report outputs and should stay under outputs/personal/."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reviewed-input",
            str(review_path),
            "--output",
            str(PROJECT_ROOT / "outputs" / "personal" / "test_unsafe_chart_dir.pdf"),
            "--charts-dir",
            "docs/not_safe_charts",
            "--allow-unsafe-input-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Unsafe personal report charts path" in result.stderr


def test_personal_report_script_rejects_non_default_reviewed_input_without_test_escape(tmp_path):
    """Report generation should not accept arbitrary processed inputs by default."""
    custom_processed = PROJECT_ROOT / "data" / "processed" / "not_default_review.csv"
    reviewed_rows().to_csv(custom_processed, index=False)
    output_path = PROJECT_ROOT / "outputs" / "personal" / "should_not_write.pdf"
    output_path.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(custom_processed),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        custom_processed.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "only accepts approved reviewed workflow files" in result.stderr


def test_uploaded_reviewed_report_blocks_blank_final_category_without_writing_artifacts():
    """Uploaded reports should fail closed until every row has an approved final category."""
    review_path = PROJECT_ROOT / "data" / "processed" / "uploaded_category_review.csv"
    output_path = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_uploaded.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "should_not_write_uploaded_charts"
    review_df = reviewed_rows()
    review_df.loc[1, "final_category"] = ""
    review_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
    if charts_dir.exists():
        for child in charts_dir.iterdir():
            child.unlink()
        charts_dir.rmdir()
    try:
        review_df.to_csv(review_path, index=False)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--charts-dir",
                str(charts_dir),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode != 0
        assert "blank final_category" in result.stderr
        assert not output_path.exists()
        assert not charts_dir.exists()
    finally:
        review_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_uploaded_reviewed_report_generates_pdf_without_test_escape():
    """The real-upload local loop should generate a report once categories are approved."""
    review_path = PROJECT_ROOT / "data" / "processed" / "uploaded_category_review.csv"
    output_path = PROJECT_ROOT / "outputs" / "personal" / "test_uploaded_personal_report.pdf"
    charts_dir = PROJECT_ROOT / "outputs" / "personal" / "test_uploaded_personal_charts"
    review_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
    if charts_dir.exists():
        for child in charts_dir.iterdir():
            child.unlink()
        charts_dir.rmdir()
    try:
        from modules.importers.personal_csv import write_uploaded_category_review

        raw_upload = pd.DataFrame(
            [
                {
                    "posted_date": "2026-04-01",
                    "description": "Uploaded Payroll",
                    "amount": 2500.0,
                    "source_category": "income",
                },
                {
                    "posted_date": "2026-04-02",
                    "description": "Uploaded Grocery",
                    "amount": -73.42,
                    "source_category": "groceries",
                },
            ]
        )
        write_uploaded_category_review(raw_upload, review_path, source_file="checking.csv")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reviewed-input",
                str(review_path),
                "--output",
                str(output_path),
                "--charts-dir",
                str(charts_dir),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        text, page_count = extract_pdf_text(output_path)
        assert "Personal report self-checks passed" in result.stdout
        assert page_count >= 1
        assert "Draft Personal CFO Report" in text
        assert "Uploaded Payroll" in text
        assert "Food & Dining" in text
        assert "Local reviewed personal data" in text
        assert "sample or fictional data only" not in text.lower()
    finally:
        review_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        if charts_dir.exists():
            for child in charts_dir.iterdir():
                child.unlink()
            charts_dir.rmdir()


def test_personal_report_script_rejects_unsafe_output(tmp_path):
    """Draft personal report PDFs should stay under outputs/personal/."""
    review_path = tmp_path / "category_review_applied.csv"
    reviewed_rows().to_csv(review_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reviewed-input",
            str(review_path),
            "--output",
            "docs/not_safe_personal_report.pdf",
            "--allow-unsafe-input-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Unsafe personal report output path" in result.stderr
