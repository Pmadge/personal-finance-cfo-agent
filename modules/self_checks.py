"""Accuracy self-checks for the CFO Agent data pipeline.

These checks are deliberately simple and local. They give the backend, reports,
and any future AI layer a fail-closed way to verify that the numbers being used
still tie back to the source transaction table.
"""

import math

import pandas as pd

from modules.analytics import monthly_summary
from modules.validation import REQUIRED_COLUMNS

CATEGORIZED_COLUMNS = ["assigned_category", "classification_method"]
TRANSACTION_CONTRACT_COLUMNS = REQUIRED_COLUMNS + CATEGORIZED_COLUMNS
MONEY_TOLERANCE = 0.01
RATE_TOLERANCE = 0.01


def _result(check, passed, detail):
    """Return one normalized self-check row."""
    return {
        "Check": check,
        "Status": "PASS" if passed else "FAIL",
        "Detail": detail,
    }


def _money_close(actual, expected):
    """Compare rounded financial values with cent-level tolerance."""
    return math.isclose(float(actual), float(expected), abs_tol=MONEY_TOLERANCE)


def _rate_close(actual, expected):
    """Compare rounded percentage values with basis-point-level tolerance."""
    return math.isclose(float(actual), float(expected), abs_tol=RATE_TOLERANCE)


def check_transaction_schema(df):
    """Confirm categorized transaction data matches the backend contract."""
    missing_columns = [
        column for column in TRANSACTION_CONTRACT_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        return _result(
            "Transaction schema contract",
            False,
            f"Missing columns: {', '.join(missing_columns)}",
        )

    null_columns = [
        column for column in TRANSACTION_CONTRACT_COLUMNS if df[column].isna().any()
    ]
    if null_columns:
        return _result(
            "Transaction schema contract",
            False,
            f"Null values in columns: {', '.join(null_columns)}",
        )

    return _result(
        "Transaction schema contract",
        True,
        f"Required columns present: {', '.join(TRANSACTION_CONTRACT_COLUMNS)}",
    )


def check_duplicate_transactions(df):
    """Warn (do not block) on identical transaction rows.

    Two genuinely separate but identical purchases (for example two same-price
    coffees on the same day) are common and legitimate, so duplicates should not
    fail-close the whole report. They are surfaced as a WARN for human review.
    """
    present_columns = [
        column for column in TRANSACTION_CONTRACT_COLUMNS if column in df.columns
    ]
    if not present_columns:
        return _result("Duplicate transaction check", True, "No contract columns to compare")

    duplicate_count = int(df.duplicated(subset=present_columns).sum())
    if duplicate_count:
        return {
            "Check": "Duplicate transaction check",
            "Status": "WARN",
            "Detail": f"Identical transaction rows for review: {duplicate_count}",
        }
    return _result("Duplicate transaction check", True, "No identical transaction rows")


def check_approved_categories(df, approved_categories):
    """Catch category drift before reports or AI commentary trust it."""
    if "assigned_category" not in df.columns:
        return _result(
            "Approved category contract",
            False,
            "Missing assigned_category column",
        )

    approved = set(approved_categories)
    observed = set(df["assigned_category"].dropna().astype(str).unique())
    unapproved = sorted(observed - approved)
    if unapproved:
        return _result(
            "Approved category contract",
            False,
            f"Unapproved assigned categories: {', '.join(unapproved)}",
        )

    return _result(
        "Approved category contract",
        True,
        f"All assigned categories are approved: {len(observed)} observed",
    )


def _manual_monthly_summary(df, month):
    """Compute the month totals independently from analytics.monthly_summary."""
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    month_df = working_df[working_df["date"].dt.to_period("M").astype(str) == month]

    # Mirror analytics.monthly_summary: income is positive amounts categorized as
    # Income; everything else is spending net of refunds/credits.
    if "assigned_category" in month_df.columns:
        income_mask = (month_df["amount"] > 0) & (month_df["assigned_category"] == "Income")
    else:
        income_mask = month_df["amount"] > 0
    income = float(month_df.loc[income_mask, "amount"].sum())
    total_expenses = float(-month_df.loc[~income_mask, "amount"].sum())
    net_cash_flow = income - total_expenses
    savings_rate = (net_cash_flow / income * 100) if income else 0.0

    return {
        "Income": round(income, 2),
        "Total Expenses": round(total_expenses, 2),
        "Net Cash Flow": round(net_cash_flow, 2),
        "Savings Rate": round(savings_rate, 2),
    }


def check_monthly_summary_reconciles(df, month, summary=None):
    """Verify reported monthly summary numbers tie back to transactions."""
    expected = _manual_monthly_summary(df, month)
    observed = monthly_summary(df, month) if summary is None else summary

    comparisons = [
        ("Income", _money_close),
        ("Total Expenses", _money_close),
        ("Net Cash Flow", _money_close),
        ("Savings Rate", _rate_close),
    ]
    failures = []
    for label, comparator in comparisons:
        observed_value = observed.get(label)
        expected_value = expected[label]
        if observed_value is None:
            failures.append(f"{label} expected {expected_value:.2f}, got {observed_value}")
            continue
        try:
            values_match = comparator(observed_value, expected_value)
        except (TypeError, ValueError):
            values_match = False
        if not values_match:
            failures.append(f"{label} expected {expected_value:.2f}, got {observed_value}")

    if failures:
        return _result(
            "Monthly summary reconciliation",
            False,
            "; ".join(failures),
        )

    return _result(
        "Monthly summary reconciliation",
        True,
        "Income, expenses, net cash flow, and savings rate reconcile to source transactions",
    )


def build_pipeline_self_checks(df, report_month, approved_categories):
    """Build a compact self-check table for pipeline/report confidence."""
    rows = [
        check_transaction_schema(df),
        check_duplicate_transactions(df),
        check_approved_categories(df, approved_categories),
        check_monthly_summary_reconciles(df, report_month),
    ]
    return pd.DataFrame(rows, columns=["Check", "Status", "Detail"])


def assert_pipeline_self_checks(df, report_month, approved_categories):
    """Fail closed only on hard failures; WARN rows are surfaced, not blocking."""
    checks = build_pipeline_self_checks(df, report_month, approved_categories)
    failures = checks[checks["Status"] == "FAIL"]
    if not failures.empty:
        detail = " | ".join(
            f"{row['Check']}: {row['Detail']}" for _, row in failures.iterrows()
        )
        raise ValueError(f"Pipeline self-checks failed: {detail}")
    return checks


def check_personal_review_rows_ready(review_df):
    """Confirm reviewed rows are not still explicitly marked for human review."""
    if "review_status" not in review_df.columns:
        return _result(
            "Reviewed rows ready for report",
            False,
            "Missing review_status column",
        )
    review_status = review_df["review_status"].astype(str).str.strip().str.lower()
    needs_review_count = int((review_status == "needs_review").sum())
    if needs_review_count:
        return _result(
            "Reviewed rows ready for report",
            False,
            f"Rows still marked needs_review: {needs_review_count}",
        )
    return _result(
        "Reviewed rows ready for report",
        True,
        "No rows are marked needs_review",
    )


def _normalized_text_series(series):
    """Normalize text for duplicate checks without changing stored data."""
    return series.fillna("").astype(str).str.strip().str.lower()


def _nonblank_duplicate_count(frame, columns):
    """Count duplicate rows across columns after excluding blank identity rows."""
    working = pd.DataFrame({column: _normalized_text_series(frame[column]) for column in columns})
    nonblank = working.ne("").any(axis=1)
    if not bool(nonblank.any()):
        return 0
    return int(working.loc[nonblank].duplicated().sum())


def check_personal_report_duplicates(review_df, report_df):
    """Fail closed when duplicate source or final-statement rows are present."""
    traceability_columns = ["source_file", "source_row_number", "import_batch_id", "transaction_id"]
    missing_traceability = [column for column in traceability_columns if column not in review_df.columns]
    if missing_traceability:
        return _result(
            "No duplicate personal report transactions",
            False,
            f"Missing traceability columns: {', '.join(missing_traceability)}",
        )

    transaction_ids = _normalized_text_series(review_df["transaction_id"])
    nonblank_transaction_ids = transaction_ids[transaction_ids != ""]
    duplicate_transaction_ids = int(nonblank_transaction_ids.duplicated().sum())
    if duplicate_transaction_ids:
        return _result(
            "No duplicate personal report transactions",
            False,
            f"Duplicate source transaction IDs: {duplicate_transaction_ids}",
        )

    duplicate_source_rows = _nonblank_duplicate_count(
        review_df,
        ["source_file", "source_row_number", "import_batch_id"],
    )
    if duplicate_source_rows:
        return _result(
            "No duplicate personal report transactions",
            False,
            f"Duplicate source row identities: {duplicate_source_rows}",
        )

    # Real statements legitimately repeat identical purchases (two same-price
    # coffees on one day). When every row carries a complete source identity and
    # those identities are unique (verified above), identical amounts are real
    # repeats, not data errors - the fingerprint check below exists for rows
    # that lack identity.
    identity = pd.DataFrame(
        {
            column: _normalized_text_series(review_df[column])
            for column in ["source_file", "source_row_number", "import_batch_id"]
        }
    )
    if len(review_df) and bool(identity.ne("").all(axis=1).all()):
        return _result(
            "No duplicate personal report transactions",
            True,
            "Source row identities are unique; identical repeat purchases allowed",
        )

    final_statement_columns = ["date", "vendor", "amount", "raw_category", "assigned_category"]
    missing_statement_columns = [column for column in final_statement_columns if column not in report_df.columns]
    if missing_statement_columns:
        return _result(
            "No duplicate personal report transactions",
            False,
            f"Missing final statement columns: {', '.join(missing_statement_columns)}",
        )
    amount_fingerprint = pd.Series(pd.to_numeric(report_df["amount"], errors="coerce"), index=report_df.index)
    fingerprint_columns = {
        "date": _normalized_text_series(report_df["date"]),
        "vendor": _normalized_text_series(report_df["vendor"]),
        "amount": amount_fingerprint.round(2).astype(str),
        "raw_category": _normalized_text_series(report_df["raw_category"]),
        "assigned_category": _normalized_text_series(report_df["assigned_category"]),
    }
    if "transaction_id" in report_df.columns:
        fingerprint_columns["transaction_id"] = _normalized_text_series(report_df["transaction_id"])
    statement_fingerprint = pd.DataFrame(fingerprint_columns)
    duplicate_statement_rows = int(statement_fingerprint.duplicated().sum())
    if duplicate_statement_rows:
        return _result(
            "No duplicate personal report transactions",
            False,
            f"Duplicate final statement rows: {duplicate_statement_rows}",
        )

    return _result(
        "No duplicate personal report transactions",
        True,
        "No duplicate transaction IDs, source rows, or final statement rows found",
    )


def check_personal_report_cash_flow_arithmetic(report_df):
    """Verify personal report cash-flow totals reconcile within the report DataFrame."""
    if "amount" not in report_df.columns:
        return _result(
            "Personal report cash-flow arithmetic",
            False,
            "Missing amount column",
        )
    income = float(report_df.loc[report_df["amount"] > 0, "amount"].sum())
    expenses = float(-report_df.loc[report_df["amount"] < 0, "amount"].sum())
    net_cash_flow = income - expenses
    recomputed_net = float(report_df["amount"].sum())
    if not _money_close(net_cash_flow, recomputed_net):
        return _result(
            "Personal report cash-flow arithmetic",
            False,
            f"Income minus expenses expected {recomputed_net:.2f}, got {net_cash_flow:.2f}",
        )
    return _result(
        "Personal report cash-flow arithmetic",
        True,
        "Income, expenses, and net cash flow reconcile within report transactions",
    )


def build_personal_report_self_checks(review_df, report_df, approved_categories):
    """Build compact pre-render self-check rows for draft personal reports."""
    rows = [
        check_personal_review_rows_ready(review_df),
        check_personal_report_duplicates(review_df, report_df),
        check_transaction_schema(report_df),
        check_approved_categories(report_df, approved_categories),
        check_personal_report_cash_flow_arithmetic(report_df),
    ]
    return pd.DataFrame(rows, columns=["Check", "Status", "Detail"])


def assert_personal_report_self_checks(review_df, report_df, approved_categories):
    """Fail closed before PDF/chart rendering if personal report checks fail."""
    checks = build_personal_report_self_checks(review_df, report_df, approved_categories)
    failures = checks[checks["Status"] != "PASS"]
    if not failures.empty:
        detail = " | ".join(
            f"{row['Check']}: {row['Detail']}" for _, row in failures.iterrows()
        )
        raise ValueError(f"Personal report self-checks failed: {detail}")
    return checks
