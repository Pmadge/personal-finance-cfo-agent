"""Tests for local category review and override workflow."""

from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.categorization_review import (
    OVERRIDE_TEMPLATE_COLUMNS,
    REVIEW_COLUMNS,
    apply_category_overrides,
    apply_category_overrides_file,
    build_category_review,
    write_category_review_file,
    write_override_template,
)
from modules.config import APPROVED_CATEGORIES


def normalized_transactions():
    return pd.DataFrame(
        [
            {
                "date": "2026-04-02",
                "vendor": "Fake Grocery Market",
                "amount": -73.42,
                "raw_category": "groceries",
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 3,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_002",
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
            },
        ]
    )


def test_build_category_review_preserves_source_identity_and_suggested_categories():
    """Review files should keep traceability while showing the suggested category."""
    review = build_category_review(normalized_transactions())

    assert list(review.columns) == REVIEW_COLUMNS
    assert review.loc[0, "suggested_category"] == "Food & Dining"
    assert review.loc[0, "review_status"] == "auto_suggested"
    assert review.loc[0, "final_category"] == "Food & Dining"
    assert review.loc[0, "source_file"] == "personal_transactions_template.csv"
    assert review.loc[0, "source_row_number"] == 3
    assert review.loc[0, "import_batch_id"] == "import_test123"
    assert review.loc[0, "transaction_id"] == "fake_txn_002"


def test_build_category_review_marks_low_confidence_rows_for_review():
    """Unknown/low-confidence rows should be obvious before report generation."""
    review = build_category_review(normalized_transactions())

    mystery = review.loc[review["vendor"] == "Mystery Vendor"].iloc[0]
    assert mystery["suggested_category"] == "Misc"
    assert mystery["classification_method"].startswith("unknown_below_")
    assert mystery["review_status"] == "needs_review"
    assert mystery["final_category"] == ""


def test_apply_category_overrides_updates_final_category_by_source_identity():
    """Manual overrides should target source identity, not only vendor text."""
    review = build_category_review(normalized_transactions())
    overrides = pd.DataFrame(
        [
            {
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 4,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_003",
                "override_category": "Shopping",
                "override_note": "Fake fixture correction",
            }
        ]
    )

    updated = apply_category_overrides(review, overrides)
    mystery = updated.loc[updated["vendor"] == "Mystery Vendor"].iloc[0]

    assert mystery["final_category"] == "Shopping"
    assert mystery["review_status"] == "manual_override"
    assert mystery["override_note"] == "Fake fixture correction"


def test_apply_category_overrides_rejects_invalid_categories():
    """Override files should fail closed if a category is outside the approved list."""
    review = build_category_review(normalized_transactions())
    overrides = pd.DataFrame(
        [
            {
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 4,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_003",
                "override_category": "Random AI Guess",
            }
        ]
    )

    with pytest.raises(ValueError, match="Invalid override category: Random AI Guess"):
        apply_category_overrides(review, overrides)


def test_write_category_review_file_uses_gitignored_default_folder(tmp_path):
    """Review files should be written to a local processed path for personal workflows."""
    review = build_category_review(normalized_transactions())
    output_path = tmp_path / "category_review.csv"

    written = write_category_review_file(review, output_path)

    assert written == output_path
    assert output_path.exists()
    disk = pd.read_csv(output_path)
    assert disk["suggested_category"].isin(APPROVED_CATEGORIES).all()
    assert "source_row_number" in disk.columns


def test_write_override_template_creates_human_editable_local_csv(tmp_path):
    """The override template should have only the columns a human needs to edit."""
    review = build_category_review(normalized_transactions())
    output_path = tmp_path / "personal_rules.csv"

    written = write_override_template(review, output_path)

    assert written == output_path
    template = pd.read_csv(output_path, keep_default_na=False)
    assert list(template.columns) == OVERRIDE_TEMPLATE_COLUMNS
    assert template.loc[0, "source_file"] == "personal_transactions_template.csv"
    assert template.loc[0, "source_row_number"] == 4
    assert template.loc[0, "override_category"] == ""
    assert template.loc[0, "override_note"] == ""


def test_apply_category_overrides_file_writes_reviewed_output(tmp_path):
    """The end-to-end helper should read review + overrides and write a reviewed CSV."""
    review_path = tmp_path / "category_review.csv"
    overrides_path = tmp_path / "personal_rules.csv"
    output_path = tmp_path / "category_review_applied.csv"
    review = build_category_review(normalized_transactions())
    review.to_csv(review_path, index=False)
    pd.DataFrame(
        [
            {
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 4,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_003",
                "override_category": "Shopping",
                "override_note": "Fake fixture correction",
            }
        ]
    ).to_csv(overrides_path, index=False)

    written = apply_category_overrides_file(review_path, overrides_path, output_path)

    assert written == output_path
    disk = pd.read_csv(output_path)
    mystery = disk.loc[disk["vendor"] == "Mystery Vendor"].iloc[0]
    assert mystery["final_category"] == "Shopping"
    assert mystery["review_status"] == "manual_override"
    assert mystery["override_note"] == "Fake fixture correction"


def test_apply_category_overrides_ignores_blank_template_rows():
    """Blank override rows from the template should not modify the review output."""
    review = build_category_review(normalized_transactions())
    overrides = pd.DataFrame(
        [
            {
                "source_file": "personal_transactions_template.csv",
                "source_row_number": 4,
                "import_batch_id": "import_test123",
                "transaction_id": "fake_txn_003",
                "override_category": "",
                "override_note": "",
            }
        ]
    )

    updated = apply_category_overrides(review, overrides)

    mystery = updated.loc[updated["vendor"] == "Mystery Vendor"].iloc[0]
    assert mystery["final_category"] == ""
    assert mystery["review_status"] == "needs_review"
