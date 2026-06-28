"""Convert reviewed personal workflow rows into report-ready inputs."""

import pandas as pd

from modules.config import APPROVED_CATEGORIES
from modules.validation import REQUIRED_COLUMNS, validate_transactions_for_processing

REVIEW_REQUIRED_COLUMNS = [
    *REQUIRED_COLUMNS,
    "classification_method",
    "final_category",
]
REPORT_COLUMNS = [
    *REQUIRED_COLUMNS,
    "assigned_category",
    "classification_method",
]


def build_report_transactions_from_review(review_df):
    """Convert reviewed category rows into report-ready categorized transactions.

    Deterministic code owns the categories. If any row is still blank or outside
    the approved category list, fail before a report can be generated.
    """
    missing = [column for column in REVIEW_REQUIRED_COLUMNS if column not in review_df.columns]
    if missing:
        raise ValueError(f"Missing reviewed report columns: {', '.join(missing)}")

    working = review_df.copy()
    final_categories = working["final_category"].fillna("").astype(str).str.strip()
    if (final_categories == "").any():
        raise ValueError("Cannot build report while any row has blank final_category")

    invalid = sorted(set(final_categories) - set(APPROVED_CATEGORIES))
    if invalid:
        raise ValueError(f"Invalid final_category: {invalid[0]}")

    report_df = working[[*REQUIRED_COLUMNS, "classification_method"]].copy()
    report_df["assigned_category"] = final_categories
    report_df = report_df[REPORT_COLUMNS]
    return validate_transactions_for_processing(report_df)
