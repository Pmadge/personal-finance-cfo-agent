"""Tests for the one-command monthly close workflow."""

from pathlib import Path
import json
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "monthly_close.py"


def run_monthly_close(*args, check=True):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def test_monthly_close_sample_runs_import_review_overrides_and_audit():
    """The beginner command should run the safe fake workflow in order."""
    result = run_monthly_close("--sample")

    assert "Step 1/5: normalized personal CSV" in result.stdout
    assert "Step 2/5: generated category review" in result.stdout
    assert "Step 3/5: ensured local override template" in result.stdout
    assert "Step 4/5: applied category overrides" in result.stdout
    assert "Step 5/5: wrote workflow audit" in result.stdout
    assert "Next: review data/processed/workflow_audit.md" in result.stdout

    expected_files = [
        "data/processed/normalized_personal_transactions.csv",
        "data/processed/category_review.csv",
        "config/personal_rules.csv",
        "data/processed/category_review_applied.csv",
        "data/processed/workflow_audit.md",
        "data/processed/workflow_audit.json",
    ]
    for relative_path in expected_files:
        assert (PROJECT_ROOT / relative_path).exists(), relative_path

    audit = json.loads((PROJECT_ROOT / "data/processed/workflow_audit.json").read_text())
    assert audit["mode"] == "sample"
    assert audit["row_count"] == 4
    assert audit["self_check_status"] == "NOT_RUN"
    assert audit["input_file"] == "data/sample/personal_transactions_template.csv"


def test_monthly_close_rejects_personal_mode_until_explicitly_enabled():
    """The one-command workflow should stay sample-only until real-data safety is approved."""
    result = run_monthly_close("--mode", "personal", check=False)

    assert result.returncode != 0
    assert "Personal mode is intentionally disabled" in result.stderr


def test_monthly_close_stops_with_clear_error_when_input_missing(tmp_path):
    """Missing input files should fail before creating misleading outputs."""
    missing_input = tmp_path / "missing.csv"
    result = run_monthly_close(
        "--sample",
        "--input",
        str(missing_input),
        check=False,
    )

    assert result.returncode != 0
    assert "Missing monthly close input" in result.stderr
    assert str(missing_input) in result.stderr


def test_monthly_close_rejects_unsafe_output_paths():
    """Generated personal workflow outputs should stay in approved Git-ignored folders."""
    unsafe_args = [
        ("--normalized-output", "docs/not_safe_normalized.csv"),
        ("--review-output", "docs/not_safe_review.csv"),
        ("--applied-review-output", "docs/not_safe_applied.csv"),
        ("--audit-markdown", "docs/not_safe_audit.md"),
        ("--audit-json", "docs/not_safe_audit.json"),
        ("--report-output", "docs/private_report.pdf"),
    ]
    for flag, unsafe_path in unsafe_args:
        result = run_monthly_close(
            "--sample",
            flag,
            unsafe_path,
            check=False,
        )

        assert result.returncode != 0, flag
        assert (
            "Unsafe personal output path" in result.stderr
            or "Processed workflow CSVs must stay under data/processed/" in result.stderr
        ), flag


def test_monthly_close_rejects_outputs_personal_for_intermediate_workflow_files():
    """Intermediate CSVs should be rejected before any write if they are routed to report folders."""
    attempted_path = PROJECT_ROOT / "outputs" / "personal" / "not_allowed_review.csv"
    attempted_path.unlink(missing_ok=True)

    result = run_monthly_close(
        "--sample",
        "--review-output",
        str(attempted_path),
        check=False,
    )

    assert result.returncode != 0
    assert "Processed workflow CSVs must stay under data/processed/" in result.stderr
    assert not attempted_path.exists()


def test_monthly_close_rejects_unsafe_override_path():
    """Local rules should only use the approved Git-ignored config/personal_rules.csv path."""
    result = run_monthly_close(
        "--sample",
        "--overrides",
        "docs/not_safe_rules.csv",
        check=False,
    )

    assert result.returncode != 0
    assert "Unsafe override rules path" in result.stderr


def test_monthly_close_sample_rejects_non_sample_input(tmp_path):
    """Sample mode must not process arbitrary or personal CSVs while personal mode is disabled."""
    private_input = PROJECT_ROOT / "data" / "personal" / "fake_real_export.csv"
    private_input.parent.mkdir(parents=True, exist_ok=True)
    private_input.write_text(
        "posted_date,description,amount,source_category,source_account,notes,transaction_id\n"
        "2026-04-01,Private Store,-12.00,dining,Checking,,p1\n"
    )
    try:
        result = run_monthly_close(
            "--sample",
            "--input",
            str(private_input),
            check=False,
        )
    finally:
        private_input.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "Sample mode only accepts files under data/sample/" in result.stderr


def test_monthly_close_rejects_external_sample_input(tmp_path):
    """Even existing external CSVs should not be mislabeled as sample workflow input."""
    external_input = tmp_path / "external.csv"
    external_input.write_text(
        "posted_date,description,amount,source_category,source_account,notes,transaction_id\n"
        "2026-04-01,External Store,-12.00,dining,Checking,,e1\n"
    )

    result = run_monthly_close(
        "--sample",
        "--input",
        str(external_input),
        check=False,
    )

    assert result.returncode != 0
    assert "Sample mode only accepts files under data/sample/" in result.stderr
