"""Local category review helpers for personal CSV workflows.

These functions create a human-reviewable CSV before any personal report is
trusted. Automatic suggestions are allowed, but low-confidence rows stay blank
until reviewed.
"""

from pathlib import Path

import pandas as pd

from modules.categorizer import RAW_CATEGORY_TRUTH_MAP, categorize_transaction
from modules.config import APPROVED_CATEGORIES

IDENTITY_COLUMNS = [
    "source_file",
    "source_row_number",
    "import_batch_id",
    "transaction_id",
]
REVIEW_COLUMNS = [
    "date",
    "vendor",
    "amount",
    "raw_category",
    *IDENTITY_COLUMNS,
    "suggested_category",
    "classification_method",
    "review_status",
    "final_category",
    "override_note",
]
OVERRIDE_KEY_COLUMNS = [
    "source_file",
    "source_row_number",
    "import_batch_id",
    "transaction_id",
]
OVERRIDE_TEMPLATE_COLUMNS = [
    *OVERRIDE_KEY_COLUMNS,
    "vendor",
    "suggested_category",
    "override_category",
    "override_note",
]


def _is_needs_review(classification_method):
    """Return True when an automatic categorization should be manually checked."""
    method = str(classification_method)
    return method.startswith("unknown_below_")


def _suggest_category(row):
    """Suggest a category from raw category mapping first, then vendor rules."""
    raw_category = str(row.get("raw_category", "")).strip().lower()
    if raw_category in RAW_CATEGORY_TRUTH_MAP:
        return pd.Series(
            {
                "assigned_category": RAW_CATEGORY_TRUTH_MAP[raw_category],
                "classification_method": "raw_category_map",
            }
        )
    return categorize_transaction(row)


def build_category_review(normalized_df):
    """Build a human-review CSV with suggested categories and source identity."""
    classification = normalized_df.apply(_suggest_category, axis=1)
    review = pd.concat([normalized_df.copy(), classification], axis=1)
    review = review.rename(columns={"assigned_category": "suggested_category"})
    review["review_status"] = review["classification_method"].map(
        lambda method: "needs_review" if _is_needs_review(method) else "auto_suggested"
    )
    review["final_category"] = review.apply(
        lambda row: "" if row["review_status"] == "needs_review" else row["suggested_category"],
        axis=1,
    )
    review["override_note"] = ""

    for column in IDENTITY_COLUMNS:
        if column not in review.columns:
            review[column] = ""

    return review[REVIEW_COLUMNS]


def _validate_override_categories(overrides_df):
    """Fail closed if any manual category is outside the approved category list."""
    categories = overrides_df["override_category"].fillna("").astype(str).str.strip()
    filled_categories = categories[categories != ""]
    invalid = sorted(set(filled_categories) - set(APPROVED_CATEGORIES))
    if invalid:
        raise ValueError(f"Invalid override category: {invalid[0]}")


def apply_category_overrides(review_df, overrides_df):
    """Apply manual category overrides by source identity columns."""
    if overrides_df.empty:
        return review_df.copy()

    required_columns = [*OVERRIDE_KEY_COLUMNS, "override_category"]
    missing = [column for column in required_columns if column not in overrides_df.columns]
    if missing:
        raise ValueError(f"Missing override columns: {', '.join(missing)}")

    _validate_override_categories(overrides_df)

    updated = review_df.copy()
    if "override_note" not in overrides_df.columns:
        overrides_df = overrides_df.copy()
        overrides_df["override_note"] = ""

    for _, override in overrides_df.iterrows():
        override_category = str(override["override_category"]).strip()
        if not override_category:
            continue

        mask = pd.Series(True, index=updated.index)
        for column in OVERRIDE_KEY_COLUMNS:
            mask &= updated[column].astype(str) == str(override[column])

        updated.loc[mask, "final_category"] = override_category
        updated.loc[mask, "review_status"] = "manual_override"
        updated.loc[mask, "override_note"] = override.get("override_note", "")

    return updated[REVIEW_COLUMNS]


def write_override_template(review_df, output_path):
    """Write a small local CSV that a person can edit with category corrections."""
    needs_review = review_df[review_df["review_status"] == "needs_review"].copy()
    if needs_review.empty:
        needs_review = review_df.copy()

    template = needs_review[[*OVERRIDE_KEY_COLUMNS, "vendor", "suggested_category"]].copy()
    template["override_category"] = ""
    template["override_note"] = ""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template[OVERRIDE_TEMPLATE_COLUMNS].to_csv(output_path, index=False)
    return output_path


def apply_category_overrides_file(review_path, overrides_path, output_path):
    """Read review and override CSVs, apply corrections, and write reviewed output."""
    review_df = pd.read_csv(review_path, keep_default_na=False)
    overrides_df = pd.read_csv(overrides_path, keep_default_na=False)
    updated = apply_category_overrides(review_df, overrides_df)
    return write_category_review_file(updated, output_path)


def write_category_review_file(review_df, output_path):
    """Write the category review CSV and return the output path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(output_path, index=False)
    return output_path
