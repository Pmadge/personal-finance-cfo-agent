"""Tests for personal workflow audit artifacts."""

from pathlib import Path
import hashlib
import json
import subprocess
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.workflow_audit import (
    REQUIRED_AUDIT_FIELDS,
    build_personal_workflow_audit,
    validate_safe_audit_output_path,
    validate_safe_listed_output_path,
    validate_safe_workflow_path,
    write_personal_workflow_audit,
)


def reviewed_transactions():
    return pd.DataFrame(
        [
            {
                "date": "2026-04-01",
                "vendor": "Fake Payroll Deposit",
                "amount": 2500.00,
                "raw_category": "income",
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 2,
                "import_batch_id": "import_test123",
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
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_002",
                "suggested_category": "Food & Dining",
                "classification_method": "raw_category_map",
                "review_status": "manual_override",
                "final_category": "Food & Dining",
                "override_note": "Fake correction",
            },
            {
                "date": "2026-04-03",
                "vendor": "Mystery Vendor",
                "amount": -42.00,
                "raw_category": "uncategorized",
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 4,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_003",
                "suggested_category": "Misc",
                "classification_method": "unknown_below_review_threshold",
                "review_status": "needs_review",
                "final_category": "",
                "override_note": "",
            },
        ]
    )


def test_build_personal_workflow_audit_records_inputs_and_counts():
    """Audit records should summarize source files, row counts, overrides, and outputs."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=["outputs/personal/personal_cfo_report_draft.pdf"],
    )

    assert set(REQUIRED_AUDIT_FIELDS).issubset(audit)
    assert audit["mode"] == "sample"
    assert audit["row_count"] == 3
    assert audit["override_count"] == 1
    assert audit["needs_review_count"] == 1
    assert audit["self_check_status"] == "PASS"
    assert audit["privacy_status"] == "local_only_gitignored_outputs"
    assert audit["input_file"] == "data/sample/personal_transactions_template.csv"
    expected_hash = hashlib.sha256(
        (PROJECT_ROOT / "data" / "sample" / "personal_transactions_template.csv").read_bytes()
    ).hexdigest()
    assert audit["input_file_sha256"] == expected_hash
    assert audit["output_paths"] == ["outputs/personal/personal_cfo_report_draft.pdf"]


def test_write_personal_workflow_audit_creates_markdown_and_json(tmp_path):
    """Audit artifacts should be readable by humans and machines."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=["outputs/personal/personal_cfo_report_draft.pdf"],
        run_timestamp="2026-06-21T13:56:28",
    )
    markdown_path = tmp_path / "workflow_audit.md"
    json_path = tmp_path / "workflow_audit.json"

    written = write_personal_workflow_audit(
        audit,
        markdown_path,
        json_path,
        allow_unsafe_output=True,
    )

    assert written == {"markdown": markdown_path, "json": json_path}
    markdown = markdown_path.read_text()
    assert "# Personal Workflow Audit" in markdown
    assert "Mode: sample" in markdown
    assert "Rows processed: 3" in markdown
    assert "Manual overrides applied: 1" in markdown
    assert "Rows still needing review: 1" in markdown
    data = json.loads(json_path.read_text())
    assert data["run_timestamp"] == "2026-06-21T13:56:28"
    assert data["row_count"] == 3
    assert len(data["input_file_sha256"]) == 64
    assert f"Input SHA-256: `{data['input_file_sha256']}`" in markdown


def test_workflow_audit_counts_normalize_review_status_values():
    """Audit counts should match report self-check behavior for manual CSV drift."""
    reviewed_df = reviewed_transactions()
    reviewed_df.loc[1, "review_status"] = " Manual_Override "
    reviewed_df.loc[2, "review_status"] = " Needs_Review "

    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_df,
        self_check_status="NOT_RUN",
        output_paths=[],
    )

    assert audit["override_count"] == 1
    assert audit["needs_review_count"] == 1


def test_audit_artifact_marks_sample_vs_personal_mode():
    """Audit mode should explicitly distinguish fake sample runs from personal runs."""
    sample_audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )
    personal_audit = build_personal_workflow_audit(
        mode="personal",
        input_file="data/personal/manual_export.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )

    assert sample_audit["mode"] == "sample"
    assert sample_audit["personal_data_warning"] == "sample_or_fictional_data_only"
    assert personal_audit["mode"] == "personal"
    assert personal_audit["personal_data_warning"] == "private_local_data_do_not_commit"


def test_audit_artifact_rejects_missing_required_fields(tmp_path):
    """Incomplete audit dictionaries should fail before writing misleading artifacts."""
    incomplete = {
        "mode": "sample",
        "row_count": 3,
    }

    with pytest.raises(ValueError, match="Missing audit fields"):
        write_personal_workflow_audit(
            incomplete,
            tmp_path / "workflow_audit.md",
            tmp_path / "workflow_audit.json",
            allow_unsafe_output=True,
        )


def test_audit_artifact_rejects_malformed_input_file_hashes(tmp_path):
    """Audit writers should reject malformed source hash values before writing artifacts."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )

    for bad_hash in ["ABCDEF" * 10 + "ABCD", "abc123", "g" * 64]:
        audit["input_file_sha256"] = bad_hash
        with pytest.raises(ValueError, match="input_file_sha256"):
            write_personal_workflow_audit(
                audit,
                tmp_path / "workflow_audit.md",
                tmp_path / "workflow_audit.json",
                allow_unsafe_output=True,
            )


def test_missing_input_file_hash_is_blank_and_markdown_says_not_available(tmp_path):
    """Missing source files should be explicit instead of inventing a hash."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/missing_source_file.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )

    assert audit["input_file_sha256"] == ""
    write_personal_workflow_audit(
        audit,
        tmp_path / "workflow_audit.md",
        tmp_path / "workflow_audit.json",
        allow_unsafe_output=True,
    )

    data = json.loads((tmp_path / "workflow_audit.json").read_text())
    markdown = (tmp_path / "workflow_audit.md").read_text()
    assert data["input_file_sha256"] == ""
    assert "Input SHA-256: `not_available`" in markdown


def test_audit_artifact_rejects_invalid_field_values(tmp_path):
    """Audit writers should fail closed on misleading values, not only missing keys."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )
    audit["row_count"] = -1

    with pytest.raises(ValueError, match="Invalid audit count"):
        write_personal_workflow_audit(
            audit,
            tmp_path / "workflow_audit.md",
            tmp_path / "workflow_audit.json",
            allow_unsafe_output=True,
        )


def test_audit_output_path_must_stay_under_gitignored_roots(tmp_path):
    """Audit artifacts should not be written into arbitrary/tracked paths by default."""
    safe_path = PROJECT_ROOT / "data" / "processed" / "workflow_audit.md"
    unsafe_path = PROJECT_ROOT / "docs" / "workflow_audit.md"

    assert validate_safe_audit_output_path(safe_path)
    assert not validate_safe_audit_output_path(unsafe_path)

    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )

    with pytest.raises(ValueError, match="Unsafe workflow audit output path"):
        write_personal_workflow_audit(
            audit,
            unsafe_path,
            tmp_path / "workflow_audit.json",
            allow_unsafe_output=False,
        )


def test_relative_workflow_paths_are_project_relative_not_cwd_relative(tmp_path, monkeypatch):
    """Audit safety checks should be stable even when called from another working directory."""
    monkeypatch.chdir(tmp_path)

    assert validate_safe_audit_output_path("data/processed/workflow_audit.md")
    assert validate_safe_workflow_path("normalized_file", "data/processed/normalized.csv")
    assert validate_safe_workflow_path("override_file", "config/personal_rules.csv")
    assert validate_safe_listed_output_path("outputs/personal/report.pdf")
    assert not validate_safe_audit_output_path("docs/workflow_audit.md")
    assert not validate_safe_listed_output_path("docs/report.pdf")


def test_relative_audit_write_paths_are_written_under_project_root(tmp_path, monkeypatch):
    """Relative audit paths should be written where validation says they are safe."""
    markdown_path = PROJECT_ROOT / "data" / "processed" / "test_relative_workflow_audit.md"
    json_path = PROJECT_ROOT / "data" / "processed" / "test_relative_workflow_audit.json"
    wrong_markdown_path = tmp_path / "data" / "processed" / "test_relative_workflow_audit.md"
    wrong_json_path = tmp_path / "data" / "processed" / "test_relative_workflow_audit.json"
    markdown_path.unlink(missing_ok=True)
    json_path.unlink(missing_ok=True)

    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="PASS",
        output_paths=[],
    )
    monkeypatch.chdir(tmp_path)
    try:
        written = write_personal_workflow_audit(
            audit,
            "data/processed/test_relative_workflow_audit.md",
            "data/processed/test_relative_workflow_audit.json",
        )

        assert written == {"markdown": markdown_path, "json": json_path}
        assert markdown_path.exists()
        assert json_path.exists()
        assert not wrong_markdown_path.exists()
        assert not wrong_json_path.exists()
    finally:
        markdown_path.unlink(missing_ok=True)
        json_path.unlink(missing_ok=True)


def test_personal_mode_redacts_external_input_paths():
    """Personal audit records should avoid storing full local paths to private source files."""
    audit = build_personal_workflow_audit(
        mode="personal",
        input_file="/tmp/private/manual_export.csv",
        normalized_file=PROJECT_ROOT / "data" / "processed" / "normalized_personal_transactions.csv",
        category_review_file=PROJECT_ROOT / "data" / "processed" / "category_review.csv",
        override_file=PROJECT_ROOT / "config" / "personal_rules.csv",
        applied_review_file=PROJECT_ROOT / "data" / "processed" / "category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="NOT_RUN",
        output_paths=[PROJECT_ROOT / "outputs" / "personal" / "draft.pdf"],
    )

    assert audit["input_file"] == "manual_export.csv"
    assert audit["normalized_file"] == "data/processed/normalized_personal_transactions.csv"
    assert audit["output_paths"] == ["outputs/personal/draft.pdf"]


def test_audit_rejects_unsafe_listed_output_paths():
    """Audit privacy status should not claim local-only safety for tracked output destinations."""
    with pytest.raises(ValueError, match="Unsafe workflow output path"):
        build_personal_workflow_audit(
            mode="sample",
            input_file="data/sample/personal_transactions_template.csv",
            normalized_file="data/processed/normalized_personal_transactions.csv",
            category_review_file="data/processed/category_review.csv",
            override_file="config/personal_rules.csv",
            applied_review_file="data/processed/category_review_applied.csv",
            reviewed_df=reviewed_transactions(),
            self_check_status="NOT_RUN",
            output_paths=["docs/private_report.pdf"],
        )


def test_audit_rejects_unsafe_workflow_paths():
    """Workflow receipt paths should also stay in expected private/local locations."""
    with pytest.raises(ValueError, match="Unsafe workflow path"):
        build_personal_workflow_audit(
            mode="sample",
            input_file="data/sample/personal_transactions_template.csv",
            normalized_file="data/processed/normalized_personal_transactions.csv",
            category_review_file="docs/category_review.csv",
            override_file="config/personal_rules.csv",
            applied_review_file="data/processed/category_review_applied.csv",
            reviewed_df=reviewed_transactions(),
            self_check_status="NOT_RUN",
            output_paths=[],
        )


def test_write_audit_revalidates_hand_built_paths(tmp_path):
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/personal_transactions_template.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="NOT_RUN",
        output_paths=[],
    )
    audit["output_paths"] = ["docs/private_report.pdf"]

    markdown_path = PROJECT_ROOT / "data" / "processed" / "test_workflow_audit.md"
    json_path = PROJECT_ROOT / "data" / "processed" / "test_workflow_audit.json"
    try:
        with pytest.raises(ValueError, match="Unsafe workflow output path"):
            write_personal_workflow_audit(audit, markdown_path, json_path)
    finally:
        markdown_path.unlink(missing_ok=True)
        json_path.unlink(missing_ok=True)


def test_markdown_output_escapes_backticks_and_newlines(tmp_path):
    """Path-like values should not be able to distort the Markdown receipt."""
    audit = build_personal_workflow_audit(
        mode="sample",
        input_file="data/sample/bad`name\nsecond-line.csv",
        normalized_file="data/processed/normalized_personal_transactions.csv",
        category_review_file="data/processed/category_review.csv",
        override_file="config/personal_rules.csv",
        applied_review_file="data/processed/category_review_applied.csv",
        reviewed_df=reviewed_transactions(),
        self_check_status="NOT_RUN",
        output_paths=["outputs/personal/report`draft.pdf"],
    )
    markdown_path = tmp_path / "workflow_audit.md"
    json_path = tmp_path / "workflow_audit.json"

    write_personal_workflow_audit(
        audit,
        markdown_path,
        json_path,
        allow_unsafe_output=True,
    )

    markdown = markdown_path.read_text()
    assert "bad\\`name second-line.csv" in markdown
    assert "report\\`draft.pdf" in markdown


def test_generate_workflow_audit_script_defaults_self_check_to_not_run(tmp_path):
    """The CLI should not claim PASS unless a caller explicitly supplies that status."""
    applied_review_path = tmp_path / "category_review_applied.csv"
    markdown_path = tmp_path / "workflow_audit.md"
    json_path = tmp_path / "workflow_audit.json"
    reviewed_transactions().to_csv(applied_review_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_workflow_audit.py",
            "--applied-review-file",
            str(applied_review_path),
            "--markdown-output",
            str(markdown_path),
            "--json-output",
            str(json_path),
            "--allow-unsafe-output-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    data = json.loads(json_path.read_text())
    assert data["self_check_status"] == "NOT_RUN"


def test_generate_workflow_audit_script_writes_artifacts(tmp_path):
    """The beginner script should write both audit artifact formats."""
    applied_review_path = tmp_path / "category_review_applied.csv"
    markdown_path = tmp_path / "workflow_audit.md"
    json_path = tmp_path / "workflow_audit.json"
    reviewed_transactions().to_csv(applied_review_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_workflow_audit.py",
            "--input-file",
            "data/sample/personal_transactions_template.csv",
            "--normalized-file",
            "data/processed/normalized_personal_transactions.csv",
            "--category-review-file",
            "data/processed/category_review.csv",
            "--override-file",
            "config/personal_rules.csv",
            "--applied-review-file",
            str(applied_review_path),
            "--markdown-output",
            str(markdown_path),
            "--json-output",
            str(json_path),
            "--self-check-status",
            "PASS",
            "--allow-unsafe-output-for-tests",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Wrote workflow audit:" in result.stdout
    assert "Wrote workflow audit JSON:" in result.stdout
    assert markdown_path.exists()
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["row_count"] == 3
    assert data["override_count"] == 1
