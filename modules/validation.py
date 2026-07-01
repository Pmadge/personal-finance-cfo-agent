"""Validation and audit checks for the fictional CFO Agent input data."""

from pathlib import Path

import pandas as pd

from modules.config import (
    APPROVED_CATEGORIES,
    FICTIONAL_DATA_NOTICE,
    REPORT_MONTH,
    TREND_MONTHS,
)


REQUIRED_COLUMNS = ["date", "vendor", "amount", "raw_category"]


def validate_transactions_for_processing(df):
    """Raise plain-English errors before categorization or reporting."""
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        if len(missing_columns) == 1:
            raise ValueError(f"Missing required column: {missing_columns[0]}")
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    if df.empty:
        raise ValueError("Transaction CSV must include at least one row")

    blank_vendors = df["vendor"].isna() | (df["vendor"].astype(str).str.strip() == "")
    if blank_vendors.any():
        raise ValueError("Vendor values cannot be blank")

    numeric_amounts = pd.to_numeric(df["amount"], errors="coerce")
    if numeric_amounts.isna().any():
        raise ValueError("Amount values must be numeric")

    date_text = df["date"].astype(str).str.strip()
    yyyy_mm_dd = date_text.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    parsed_dates = pd.to_datetime(date_text, format="%Y-%m-%d", errors="coerce")
    if (~yyyy_mm_dd | parsed_dates.isna()).any():
        raise ValueError("Date values must use YYYY-MM-DD")

    blank_raw_categories = df["raw_category"].isna() | (
        df["raw_category"].astype(str).str.strip() == ""
    )
    if blank_raw_categories.any():
        raise ValueError("Raw category values cannot be blank")

    cleaned_df = df.copy()
    cleaned_df["amount"] = numeric_amounts
    cleaned_df["date"] = date_text
    return cleaned_df


def validate_transactions(df, expected_months=None):
    """Return PASS/FAIL checks for the transaction data frame."""
    expected_months = expected_months or TREND_MONTHS
    rows = []

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    rows.append(
        {
            "Check": "Required columns",
            "Status": "PASS" if not missing_columns else "FAIL",
            "Detail": "All required columns present"
            if not missing_columns
            else f"Missing columns: {', '.join(missing_columns)}",
        }
    )

    if missing_columns:
        return pd.DataFrame(rows)

    parsed_dates = pd.to_datetime(df["date"], errors="coerce")
    numeric_amounts = pd.to_numeric(df["amount"], errors="coerce")
    months = sorted(parsed_dates.dropna().dt.to_period("M").astype(str).unique())
    blank_vendors = df["vendor"].isna() | (df["vendor"].astype(str).str.strip() == "")

    checks = [
        ("Valid dates", parsed_dates.notna().all(), "Every date uses a valid YYYY-MM-DD value"),
        ("Numeric amounts", numeric_amounts.notna().all(), "Every amount is numeric"),
        ("No blank vendors", not blank_vendors.any(), "Every row has a vendor or income source"),
        (
            "Expected month coverage",
            months == expected_months,
            f"Months found: {', '.join(months)}",
        ),
    ]

    for check, passed, detail in checks:
        rows.append({"Check": check, "Status": "PASS" if passed else "FAIL", "Detail": detail})

    return pd.DataFrame(rows)


def validate_fictional_data_notice(project_root):
    """Confirm project docs explicitly label the data as fictional Alex Rivera data."""
    project_root = Path(project_root)
    docs = [
        project_root / "README.md",
        project_root / "test_personas" / "README.md",
        project_root / "data" / "README.md",
        project_root / "outputs" / "README.md",
    ]
    combined_text = "\n".join(path.read_text() for path in docs if path.exists())
    passed = FICTIONAL_DATA_NOTICE.lower() in combined_text.lower()
    return {
        "Check": "Fictional data notice",
        "Status": "PASS" if passed else "FAIL",
        "Detail": FICTIONAL_DATA_NOTICE if passed else "Fictional data notice not found",
    }


def _display_input_path(input_path, project_root):
    """Show a project-relative path so reports never leak a full local/home path."""
    input_path = Path(input_path)
    try:
        return str(input_path.resolve().relative_to(Path(project_root).resolve()))
    except ValueError:
        return input_path.name


def build_audit_log(df, accuracy_rate, input_path, project_root):
    """Build a compact audit trail for CLI and PDF reporting."""
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    months = sorted(working_df["date"].dt.to_period("M").astype(str).unique())
    validation_df = validate_transactions(working_df)
    fictional_notice = validate_fictional_data_notice(project_root)

    rows = [
        {"Check": "Input file", "Status": "INFO", "Detail": _display_input_path(input_path, project_root)},
        {"Check": "Row count", "Status": "INFO", "Detail": str(len(working_df))},
        {"Check": "Months covered", "Status": "INFO", "Detail": ", ".join(months)},
        {
            "Check": "Categorization accuracy",
            "Status": "PASS" if accuracy_rate >= 85 else "FAIL",
            "Detail": f"{accuracy_rate:.2f}%",
        },
    ]
    rows.extend(validation_df.to_dict("records"))
    from modules.self_checks import build_pipeline_self_checks

    self_checks_df = build_pipeline_self_checks(
        working_df,
        report_month=REPORT_MONTH,
        approved_categories=APPROVED_CATEGORIES,
    )
    rows.extend(self_checks_df.to_dict("records"))
    rows.append(fictional_notice)
    return pd.DataFrame(rows, columns=["Check", "Status", "Detail"])
