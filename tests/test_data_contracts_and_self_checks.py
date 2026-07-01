"""Backend data-contract and accuracy self-check tests."""

from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.analytics import monthly_summary
from modules.categorizer import calculate_accuracy
from modules.config import APPROVED_CATEGORIES
from modules.self_checks import (
    assert_pipeline_self_checks,
    build_pipeline_self_checks,
    check_approved_categories,
    check_duplicate_transactions,
    check_monthly_summary_reconciles,
    check_transaction_schema,
)
from modules.validation import build_audit_log

def load_categorized():
    return pd.read_csv(PROJECT_ROOT / "test_personas" / "starter_person" / "transactions_categorized.csv")


def test_transaction_schema_contract_passes_for_categorized_data():
    """The backend should have one clear transaction data contract."""
    df = load_categorized()

    result = check_transaction_schema(df)

    assert result["Status"] == "PASS"
    assert "date, vendor, amount, raw_category, assigned_category, classification_method" in result["Detail"]


def test_duplicate_transactions_warn_but_do_not_block():
    """Identical legitimate transactions should warn, not fail-close the report."""
    df = load_categorized()
    duplicated = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    # The schema contract no longer fails on duplicates...
    schema_result = check_transaction_schema(duplicated)
    assert schema_result["Status"] == "PASS"

    # ...a separate soft check surfaces them as a WARN instead.
    dup_result = check_duplicate_transactions(duplicated)
    assert dup_result["Status"] == "WARN"
    assert "1" in dup_result["Detail"]

    # And the pipeline gate does not raise on a WARN.
    checks = assert_pipeline_self_checks(duplicated, "2026-03", APPROVED_CATEGORIES)
    assert "WARN" in set(checks["Status"])


def test_approved_categories_self_check_catches_ai_category_drift():
    """Any AI/category fallback must stay inside the approved category contract."""
    df = load_categorized()
    df.loc[0, "assigned_category"] = "AI Guess Category"

    result = check_approved_categories(df, APPROVED_CATEGORIES)

    assert result["Status"] == "FAIL"
    assert "Unapproved assigned categories: AI Guess Category" in result["Detail"]


def test_monthly_summary_self_check_reconciles_against_source_transactions():
    """Reported income/expense/net numbers should tie back to source transactions."""
    df = load_categorized()
    summary = monthly_summary(df, "2026-03")

    result = check_monthly_summary_reconciles(df, "2026-03", summary)

    assert result["Status"] == "PASS"
    assert "Income, expenses, net cash flow, and savings rate reconcile" in result["Detail"]


def test_monthly_summary_self_check_fails_when_ai_or_code_uses_wrong_numbers():
    """If commentary/report code passes wrong numbers, the self-check should fail."""
    df = load_categorized()
    summary = monthly_summary(df, "2026-03")
    summary["Total Expenses"] = summary["Total Expenses"] + 1.00

    result = check_monthly_summary_reconciles(df, "2026-03", summary)

    assert result["Status"] == "FAIL"
    assert "Total Expenses expected" in result["Detail"]


def test_monthly_summary_self_check_fails_on_missing_reported_metrics():
    """An explicitly bad summary should fail instead of being recomputed silently."""
    df = load_categorized()

    result = check_monthly_summary_reconciles(df, "2026-03", {})

    assert result["Status"] == "FAIL"
    assert "Income expected" in result["Detail"]


def test_monthly_summary_self_check_fails_on_non_numeric_reported_metrics():
    """Bad AI/report values should return a FAIL row, not crash the audit."""
    df = load_categorized()
    summary = monthly_summary(df, "2026-03")
    summary["Income"] = "not-a-number"

    result = check_monthly_summary_reconciles(df, "2026-03", summary)

    assert result["Status"] == "FAIL"
    assert "Income expected" in result["Detail"]


def test_pipeline_self_checks_return_all_passes_for_current_demo_data():
    """One call should produce a compact audit table for backend/data confidence."""
    df = load_categorized()

    checks = build_pipeline_self_checks(df, report_month="2026-03", approved_categories=APPROVED_CATEGORIES)

    assert set(checks.columns) == {"Check", "Status", "Detail"}
    assert checks["Status"].eq("PASS").all()
    assert "Transaction schema contract" in set(checks["Check"])
    assert "Approved category contract" in set(checks["Check"])
    assert "Monthly summary reconciliation" in set(checks["Check"])


def test_assert_pipeline_self_checks_fails_closed_on_bad_data():
    """Reports should have an easy fail-closed gate before trusting bad data."""
    df = load_categorized()
    df.loc[0, "assigned_category"] = "AI Guess Category"

    with pytest.raises(ValueError, match="Pipeline self-checks failed"):
        assert_pipeline_self_checks(df, report_month="2026-03", approved_categories=APPROVED_CATEGORIES)


def test_audit_log_includes_backend_accuracy_self_checks():
    """The visible audit log should expose the self-checks, not hide them in tests."""
    df = load_categorized()
    audit = build_audit_log(
        df,
        calculate_accuracy(df),
        PROJECT_ROOT / "test_personas" / "starter_person" / "transactions.csv",
        PROJECT_ROOT,
    )

    assert "Transaction schema contract" in set(audit["Check"])
    assert "Approved category contract" in set(audit["Check"])
    assert "Monthly summary reconciliation" in set(audit["Check"])
    self_check_names = [
        "Transaction schema contract",
        "Approved category contract",
        "Monthly summary reconciliation",
    ]
    self_check_rows = audit[audit["Check"].isin(self_check_names)]
    assert self_check_rows["Status"].eq("PASS").all()
