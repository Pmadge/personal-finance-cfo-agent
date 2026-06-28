"""Privacy and input-validation guardrails for personal-use readiness."""

from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.categorizer import categorize_file


PRIVATE_PATHS = [
    "data/personal/",
    "data/processed/",
    "outputs/personal/",
]

PRIVATE_EXAMPLE_FILES = [
    "data/personal/example_bank_export.csv",
    "data/processed/example_categorized.csv",
    "outputs/personal/example_report.pdf",
    "config/personal_rules.json",
]


def assert_categorize_error(input_rows, expected_message, tmp_path):
    """Write bad rows, assert the user-facing error, and verify no output appears."""
    bad_csv = tmp_path / "bad_transactions.csv"
    output_csv = tmp_path / "categorized.csv"
    pd.DataFrame(input_rows).to_csv(bad_csv, index=False)

    with pytest.raises(ValueError, match=expected_message):
        categorize_file(bad_csv, output_csv)

    assert not output_csv.exists()


def test_private_financial_folders_are_gitignored():
    """Future personal financial data folders should be protected before use."""
    gitignore_text = (PROJECT_ROOT / ".gitignore").read_text()

    for private_path in PRIVATE_PATHS:
        assert private_path in gitignore_text
        assert f"!{private_path}.gitkeep" in gitignore_text
        assert (PROJECT_ROOT / private_path / ".gitkeep").exists()


def test_git_itself_ignores_representative_private_financial_files():
    """Verify privacy paths with Git, not only by string-matching .gitignore."""
    result = subprocess.run(
        ["git", "check-ignore", *PRIVATE_EXAMPLE_FILES],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    ignored = set(result.stdout.splitlines())
    assert ignored == set(PRIVATE_EXAMPLE_FILES)


def test_categorize_file_rejects_missing_required_columns_with_plain_english(tmp_path):
    """A bad personal CSV should fail with a helpful message, not a KeyError."""
    assert_categorize_error(
        [
            {
                "date": "2026-03-01",
                "vendor": "Payroll Deposit",
                "amount": 2400.00,
            }
        ],
        "Missing required column: raw_category",
        tmp_path,
    )


def test_categorize_file_rejects_multiple_missing_columns_with_plain_english(tmp_path):
    """Multiple missing columns should still produce one plain-English error."""
    assert_categorize_error(
        [{"date": "2026-03-01", "vendor": "Payroll Deposit"}],
        "Missing required columns: amount, raw_category",
        tmp_path,
    )


def test_categorize_file_rejects_non_numeric_amounts_with_plain_english(tmp_path):
    """Amounts must be numeric so reports do not silently produce bad math."""
    assert_categorize_error(
        [
            {
                "date": "2026-03-01",
                "vendor": "Payroll Deposit",
                "amount": "not-a-number",
                "raw_category": "income",
            }
        ],
        "Amount values must be numeric",
        tmp_path,
    )


def test_categorize_file_rejects_invalid_dates_with_plain_english(tmp_path):
    """Dates must parse before personal reporting starts."""
    assert_categorize_error(
        [
            {
                "date": "March-ish",
                "vendor": "Payroll Deposit",
                "amount": 2400.00,
                "raw_category": "income",
            }
        ],
        "Date values must use YYYY-MM-DD",
        tmp_path,
    )


def test_categorize_file_rejects_invalid_calendar_dates_with_plain_english(tmp_path):
    """YYYY-MM-DD shape is not enough; impossible dates should fail too."""
    assert_categorize_error(
        [
            {
                "date": "2026-02-30",
                "vendor": "Payroll Deposit",
                "amount": 2400.00,
                "raw_category": "income",
            }
        ],
        "Date values must use YYYY-MM-DD",
        tmp_path,
    )


def test_categorize_file_rejects_blank_vendors_with_plain_english(tmp_path):
    """Blank vendors make personal review harder and should fail early."""
    assert_categorize_error(
        [
            {
                "date": "2026-03-01",
                "vendor": " ",
                "amount": -42.00,
                "raw_category": "dining",
            }
        ],
        "Vendor values cannot be blank",
        tmp_path,
    )


def test_categorize_file_rejects_blank_raw_categories_with_plain_english(tmp_path):
    """Personal imports need a starting raw category or explicit import mapping."""
    assert_categorize_error(
        [
            {
                "date": "2026-03-01",
                "vendor": "Blue Bottle Coffee",
                "amount": -6.50,
                "raw_category": " ",
            }
        ],
        "Raw category values cannot be blank",
        tmp_path,
    )
