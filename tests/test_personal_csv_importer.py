"""Tests for fake personal CSV import templates and local normalization."""

from pathlib import Path
import hashlib
import subprocess
import sys

import fitz
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.importers.personal_csv import (
    IDENTITY_COLUMNS,
    IMPORT_TEMPLATE_COLUMNS,
    normalize_fake_bank_export,
    normalize_personal_csv,
    normalize_personal_transactions,
    normalize_uploaded_files,
    normalize_uploaded_statement_file,
    normalize_uploaded_transactions,
    parse_coasthills_visa_pdf,
    validate_safe_output_path,
    write_uploaded_category_review,
    write_uploaded_transactions,
)
from modules.validation import REQUIRED_COLUMNS, validate_transactions_for_processing

TEMPLATE_PATH = PROJECT_ROOT / "data" / "sample" / "personal_transactions_template.csv"


FAKE_BANK_EXPORT_PATH = PROJECT_ROOT / "data" / "sample" / "fake_bank_export_profile.csv"


FAKE_PDF_ROWS = [
    ("01/31", "02/01", "00000000000000000001", "FAKE COASTHILLS GROCERY GOLETA CA", "12.34"),
    ("02/14", "02/15", "00000000000000000002", "FAKE COASTHILLS BOOKSTORE ISLA VISTA CA", "56.78"),
]
FAKE_PDF_ROWS_LATER = [
    ("03/01", "03/02", "00000000000000000003", "FAKE COASTHILLS COFFEE GOLETA CA", "9.99"),
]


def _fake_coasthills_pdf_bytes(rows):
    """Build a tiny text-based statement PDF fixture with no real financial data."""
    lines = []
    for transaction_date, posted_date, reference, vendor, amount in rows:
        lines.extend([transaction_date, posted_date, "PPLN", reference, vendor, "$", amount])
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "\n".join(lines), fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def test_fake_bank_export_profile_fixture_exists_and_is_fake_only():
    """The first bank-profile fixture should be fake data with realistic export columns."""
    export = pd.read_csv(FAKE_BANK_EXPORT_PATH)

    assert list(export.columns) == [
        "Transaction Date",
        "Description",
        "Debit",
        "Credit",
        "Category",
        "Account Name",
        "Transaction ID",
    ]
    assert len(export) >= 4
    assert export["Account Name"].str.contains("Fake", case=False).all()
    assert not export.to_string().lower().count("paul")


def test_normalize_fake_bank_export_profile_maps_debit_credit_to_amounts():
    """The fake bank profile should adapt split Debit/Credit columns into signed amounts."""
    export = pd.read_csv(FAKE_BANK_EXPORT_PATH)

    normalized = normalize_fake_bank_export(
        export,
        source_file="fake_bank_export_profile.csv",
        import_batch_id="import_fake_bank",
    )

    assert list(normalized.columns) == REQUIRED_COLUMNS + IDENTITY_COLUMNS
    assert normalized[["date", "vendor", "amount", "raw_category"]].to_dict("records")[:2] == [
        {
            "date": "2026-04-01",
            "vendor": "Fake Payroll Deposit",
            "amount": 2500.00,
            "raw_category": "income",
        },
        {
            "date": "2026-04-02",
            "vendor": "Fake Grocery Market",
            "amount": -73.42,
            "raw_category": "groceries",
        },
    ]
    assert normalized.loc[0, "source_file"] == "fake_bank_export_profile.csv"
    assert normalized.loc[0, "source_row_number"] == 2
    assert normalized.loc[0, "import_batch_id"] == "import_fake_bank"
    assert normalized.loc[0, "transaction_id"] == "fake_bank_txn_001"


def test_fake_bank_export_profile_rejects_rows_with_both_debit_and_credit():
    """Ambiguous bank rows should fail before entering the internal schema."""
    export = pd.DataFrame(
        [
            {
                "Transaction Date": "2026-04-01",
                "Description": "Fake Ambiguous Row",
                "Debit": "10.00",
                "Credit": "5.00",
                "Category": "dining",
                "Account Name": "Fake Checking",
                "Transaction ID": "fake_bad_001",
            }
        ]
    )

    with pytest.raises(ValueError, match="exactly one of Debit or Credit"):
        normalize_fake_bank_export(export)


def test_fake_bank_export_profile_escapes_formula_like_text():
    """Fake-bank profile normalization should reuse spreadsheet formula escaping."""
    export = pd.DataFrame(
        [
            {
                "Transaction Date": "2026-04-01",
                "Description": "=HYPERLINK(\"https://bad.example\")",
                "Debit": "10.00",
                "Credit": "",
                "Category": "@risky_category",
                "Account Name": "Fake Checking",
                "Transaction ID": "+fake_bad_001",
            }
        ]
    )

    normalized = normalize_fake_bank_export(export)

    assert normalized.loc[0, "vendor"].startswith("'=")
    assert normalized.loc[0, "raw_category"].startswith("'@")
    assert normalized.loc[0, "transaction_id"].startswith("'+")


def test_fake_personal_csv_template_exists_and_uses_safe_columns():
    """The personal import template should be safe fake data, not Paul's real data."""
    template = pd.read_csv(TEMPLATE_PATH)

    assert list(template.columns) == IMPORT_TEMPLATE_COLUMNS
    assert len(template) >= 4
    assert template["source_account"].str.contains("Fake", case=False).all()
    assert not template.to_string().lower().count("paul")


def test_normalize_personal_transactions_maps_template_to_internal_schema():
    """The importer should convert bank-style columns into the app's source schema."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Fake Payroll Deposit",
                "amount": 2500.00,
                "source_category": "income",
                "source_account": "Fake Checking",
                "notes": "fake fixture only",
            },
            {
                "posted_date": "2026-04-02",
                "description": "Fake Grocery Market",
                "amount": -73.42,
                "source_category": "groceries",
                "source_account": "Fake Credit Card",
                "notes": "fake fixture only",
            },
        ]
    )

    normalized = normalize_personal_transactions(
        raw,
        source_file="fake_personal_export.csv",
        import_batch_id="batch_test",
    )

    assert list(normalized.columns) == REQUIRED_COLUMNS + IDENTITY_COLUMNS
    assert normalized[REQUIRED_COLUMNS].to_dict("records") == [
        {
            "date": "2026-04-01",
            "vendor": "Fake Payroll Deposit",
            "amount": 2500.00,
            "raw_category": "income",
        },
        {
            "date": "2026-04-02",
            "vendor": "Fake Grocery Market",
            "amount": -73.42,
            "raw_category": "groceries",
        },
    ]
    assert normalized[IDENTITY_COLUMNS].to_dict("records") == [
        {
            "source_file": "fake_personal_export.csv",
            "source_row_number": 2,
            "import_batch_id": "batch_test",
            "transaction_id": "",
        },
        {
            "source_file": "fake_personal_export.csv",
            "source_row_number": 3,
            "import_batch_id": "batch_test",
            "transaction_id": "",
        },
    ]
    validate_transactions_for_processing(normalized)


def test_normalize_uploaded_transactions_detects_supported_template_profile():
    """UI uploads should reuse importer profiles instead of inventing UI parsing."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Real Uploaded Payroll",
                "amount": 2500.00,
                "source_category": "income",
            }
        ]
    )

    profile, normalized = normalize_uploaded_transactions(raw, source_file="checking.csv")

    assert profile == "personal-template"
    assert normalized.loc[0, "vendor"] == "Real Uploaded Payroll"
    assert normalized.loc[0, "source_file"] == "checking.csv"


def test_normalize_uploaded_transactions_detects_supported_debit_credit_profile():
    """Uploaded bank-style Debit/Credit exports should normalize with existing logic."""
    raw = pd.DataFrame(
        [
            {
                "Transaction Date": "2026-04-01",
                "Description": "Real Uploaded Grocery",
                "Debit": "73.42",
                "Credit": "",
                "Category": "groceries",
                "Account Name": "Checking",
                "Transaction ID": "bank_001",
            }
        ]
    )

    profile, normalized = normalize_uploaded_transactions(raw, source_file="bank.csv")

    assert profile == "debit-credit"
    assert normalized.loc[0, "amount"] == -73.42
    assert normalized.loc[0, "transaction_id"] == "bank_001"


def test_normalize_uploaded_transactions_rejects_unknown_columns():
    """Unsupported uploads should fail with the accepted column sets."""
    raw = pd.DataFrame([{"date": "2026-04-01", "memo": "Store", "value": -1}])

    with pytest.raises(ValueError, match="Unsupported upload columns"):
        normalize_uploaded_transactions(raw, source_file="unknown.csv")


def test_parse_coasthills_visa_pdf_extracts_statement_purchases():
    parsed = parse_coasthills_visa_pdf(_fake_coasthills_pdf_bytes(FAKE_PDF_ROWS))

    assert len(parsed) == 2
    assert round(parsed["amount"].sum(), 2) == -69.12
    assert parsed.loc[0, "description"] == "FAKE COASTHILLS GROCERY GOLETA CA"
    assert parsed.loc[0, "transaction_id"] == "00000000000000000001"
    assert set(["posted_date", "description", "amount", "source_category", "transaction_id"]).issubset(parsed.columns)


def test_normalize_uploaded_statement_file_accepts_pdf_upload_bytes():
    profile, normalized = normalize_uploaded_statement_file(
        _fake_coasthills_pdf_bytes(FAKE_PDF_ROWS),
        source_file="Fake CoastHills Statement.pdf",
    )

    assert profile == "coasthills-visa-pdf"
    assert len(normalized) == 2
    assert round(normalized["amount"].sum(), 2) == -69.12
    assert normalized.loc[0, "source_file"] == "Fake CoastHills Statement.pdf"
    assert normalized.loc[0, "vendor"] == "FAKE COASTHILLS GROCERY GOLETA CA"


def test_normalize_uploaded_files_merges_multiple_pdf_statements():
    uploads = [
        (_fake_coasthills_pdf_bytes(FAKE_PDF_ROWS), "Fake February Statement.pdf"),
        (_fake_coasthills_pdf_bytes(FAKE_PDF_ROWS_LATER), "Fake March Statement.pdf"),
    ]

    source_label, profile, normalized = normalize_uploaded_files(uploads)

    assert profile == "coasthills-visa-pdf-batch"
    assert source_label == "Fake February Statement.pdf + Fake March Statement.pdf"
    assert len(normalized) == 3
    assert round(normalized["amount"].sum(), 2) == -79.11
    assert normalized.loc[0, "vendor"] == "FAKE COASTHILLS GROCERY GOLETA CA"
    assert normalized.loc[len(normalized) - 1, "vendor"] == "FAKE COASTHILLS COFFEE GOLETA CA"


def test_normalize_uploaded_files_rejects_multiple_csv_uploads():
    csv_upload = b"posted_date,description,amount,source_category\n2026-04-01,Store,-1,misc\n"

    with pytest.raises(ValueError, match="Multiple uploads currently supports PDF statements only"):
        normalize_uploaded_files([(csv_upload, "one.csv"), (csv_upload, "two.csv")])


def test_write_uploaded_transactions_writes_only_safe_processed_output():
    output_path = PROJECT_ROOT / "data" / "processed" / "test_uploaded_normalized.csv"
    output_path.unlink(missing_ok=True)
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Uploaded Payroll",
                "amount": 2500.0,
                "source_category": "income",
            }
        ]
    )
    try:
        profile, normalized = write_uploaded_transactions(
            raw,
            output_path,
            source_file="checking.csv",
        )

        assert profile == "personal-template"
        assert output_path.exists()
        written = pd.read_csv(output_path, keep_default_na=False)
        assert written.to_dict("records") == normalized.to_dict("records")
    finally:
        output_path.unlink(missing_ok=True)


def test_write_uploaded_transactions_rejects_unsafe_output(tmp_path):
    raw = pd.DataFrame(
        [{"posted_date": "2026-04-01", "description": "Uploaded", "amount": 1, "source_category": "income"}]
    )

    with pytest.raises(ValueError, match="Unsafe personal output path"):
        write_uploaded_transactions(raw, tmp_path / "normalized.csv", source_file="checking.csv")


def test_write_uploaded_category_review_writes_review_file_to_safe_output():
    output_path = PROJECT_ROOT / "data" / "processed" / "test_uploaded_category_review.csv"
    output_path.unlink(missing_ok=True)
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Uploaded Payroll",
                "amount": 2500.0,
                "source_category": "income",
            }
        ]
    )
    try:
        profile, review = write_uploaded_category_review(raw, output_path, source_file="checking.csv")

        assert profile == "personal-template"
        assert output_path.exists()
        written = pd.read_csv(output_path, keep_default_na=False)
        assert written.to_dict("records") == review.to_dict("records")
        assert written.loc[0, "suggested_category"] == "Income"
    finally:
        output_path.unlink(missing_ok=True)


def test_write_uploaded_category_review_rejects_unsafe_output(tmp_path):
    raw = pd.DataFrame(
        [{"posted_date": "2026-04-01", "description": "Uploaded", "amount": 1, "source_category": "income"}]
    )

    with pytest.raises(ValueError, match="Unsafe personal output path"):
        write_uploaded_category_review(raw, tmp_path / "review.csv", source_file="checking.csv")


def test_normalize_personal_csv_writes_processed_output(tmp_path):
    """The file-level importer should write normalized data to the requested path."""
    input_path = tmp_path / "fake_personal_export.csv"
    output_path = tmp_path / "normalized_transactions.csv"
    pd.DataFrame(
        [
            {
                "transaction_id": "txn_001",
                "posted_date": "2026-04-03",
                "description": "Fake Coffee Shop",
                "amount": -6.25,
                "source_category": "dining",
                "source_account": "Fake Credit Card",
                "notes": "fake fixture only",
            }
        ]
    ).to_csv(input_path, index=False)

    normalized = normalize_personal_csv(input_path, output_path, allow_unsafe_output=True)

    assert output_path.exists()
    written = pd.read_csv(output_path)
    assert written.to_dict("records") == normalized.to_dict("records")
    assert written.loc[0, "vendor"] == "Fake Coffee Shop"
    assert written.loc[0, "source_file"] == "fake_personal_export.csv"
    assert written.loc[0, "source_row_number"] == 2
    expected_batch_id = f"import_{hashlib.sha256(input_path.read_bytes()).hexdigest()[:12]}"
    assert written.loc[0, "import_batch_id"] == expected_batch_id
    assert written.loc[0, "transaction_id"] == "txn_001"


def test_normalize_personal_csv_relative_output_is_project_relative(tmp_path, monkeypatch):
    """Module callers should not depend on cwd for approved relative processed outputs."""
    output_path = PROJECT_ROOT / "data" / "processed" / "test_relative_normalized.csv"
    wrong_output = tmp_path / "data" / "processed" / "test_relative_normalized.csv"
    output_path.unlink(missing_ok=True)
    monkeypatch.chdir(tmp_path)
    try:
        normalized = normalize_personal_csv(
            TEMPLATE_PATH,
            "data/processed/test_relative_normalized.csv",
        )

        assert len(normalized) == 4
        assert output_path.exists()
        assert not wrong_output.exists()
    finally:
        output_path.unlink(missing_ok=True)


def test_personal_csv_output_rejects_git_tracked_project_paths_by_default(tmp_path):
    """Personal normalized outputs should not accidentally land in tracked folders."""
    input_path = tmp_path / "fake_personal_export.csv"
    unsafe_output = PROJECT_ROOT / "data" / "sample" / "unsafe_personal_output.csv"
    pd.DataFrame(
        [
            {
                "posted_date": "2026-04-03",
                "description": "Fake Coffee Shop",
                "amount": -6.25,
                "source_category": "dining",
            }
        ]
    ).to_csv(input_path, index=False)

    with pytest.raises(ValueError, match="Unsafe personal output path"):
        normalize_personal_csv(input_path, unsafe_output)

    assert not unsafe_output.exists()


def test_safe_output_path_allows_processed_and_personal_report_folders():
    """Approved personal output roots should remain explicit and narrow."""
    assert validate_safe_output_path(PROJECT_ROOT / "data" / "processed" / "x.csv")
    assert validate_safe_output_path(PROJECT_ROOT / "outputs" / "personal" / "x.csv")


def test_safe_output_path_rejects_traversal_and_prefix_lookalikes():
    """Path safety should reject common bypass shapes."""
    assert not validate_safe_output_path(PROJECT_ROOT / "data" / "processed" / ".." / "sample" / "x.csv")
    assert not validate_safe_output_path(PROJECT_ROOT / "data" / "processed_evil" / "x.csv")


def test_import_personal_csv_script_rejects_non_sample_input_by_default(tmp_path):
    """The standalone importer should not bypass the fake-only posture."""
    private_input = PROJECT_ROOT / "data" / "personal" / "fake_real_export.csv"
    private_input.parent.mkdir(parents=True, exist_ok=True)
    private_input.write_text(
        "posted_date,description,amount,source_category\n"
        "2026-04-01,Private Store,-12.00,dining\n"
    )
    output_path = PROJECT_ROOT / "data" / "processed" / "should_not_write.csv"
    output_path.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/import_personal_csv.py",
                "--input",
                str(private_input),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        private_input.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "Sample import mode only accepts files under data/sample/" in result.stderr


def test_import_personal_csv_script_rejects_sample_path_traversal_input():
    """Sample-mode import should reject traversal that resolves outside data/sample/."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_personal_csv.py",
            "--input",
            "data/sample/../personal/fake_real_export.csv",
            "--output",
            "data/processed/should_not_write.csv",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Sample import mode only accepts files under data/sample/" in result.stderr


def test_import_personal_csv_script_rejects_symlink_out_of_sample_tree(tmp_path):
    """Sample-mode import should reject symlinks whose real target is outside data/sample/."""
    private_input = tmp_path / "external_fake.csv"
    private_input.write_text(
        "posted_date,description,amount,source_category\n"
        "2026-04-01,External Store,-12.00,dining\n"
    )
    sample_link = PROJECT_ROOT / "data" / "sample" / "linked_external.csv"
    output_path = PROJECT_ROOT / "data" / "processed" / "should_not_write_symlink.csv"
    sample_link.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
    try:
        sample_link.symlink_to(private_input)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/import_personal_csv.py",
                "--input",
                str(sample_link),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        sample_link.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "Sample import mode only accepts files under data/sample/" in result.stderr


def test_import_personal_csv_script_runs_fake_bank_profile_from_project_root():
    """The standalone importer should expose the fake bank profile without real-data mode."""
    output_path = PROJECT_ROOT / "data" / "processed" / "test_fake_bank_profile_normalized.csv"
    output_path.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/import_personal_csv.py",
                "--profile",
                "fake-bank",
                "--input",
                str(FAKE_BANK_EXPORT_PATH),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        written = pd.read_csv(output_path)
        assert "Normalized 4 rows" in result.stdout
        assert "Profile: fake-bank" in result.stdout
        assert written.loc[0, "amount"] == 2500.00
        assert written.loc[1, "amount"] == -73.42
        expected_batch_id = f"import_{hashlib.sha256(FAKE_BANK_EXPORT_PATH.read_bytes()).hexdigest()[:12]}"
        assert written.loc[0, "import_batch_id"] == expected_batch_id
        assert written.loc[0, "transaction_id"] == "fake_bank_txn_001"
    finally:
        output_path.unlink(missing_ok=True)


def test_import_personal_csv_script_runs_fake_bank_profile_with_default_input():
    """Selecting fake-bank profile should switch to the committed fake-bank fixture by default."""
    output_path = PROJECT_ROOT / "data" / "processed" / "test_fake_bank_profile_default_input.csv"
    output_path.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/import_personal_csv.py",
                "--profile",
                "fake-bank",
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        written = pd.read_csv(output_path)
        expected_batch_id = f"import_{hashlib.sha256(FAKE_BANK_EXPORT_PATH.read_bytes()).hexdigest()[:12]}"
        assert "Normalized 4 rows" in result.stdout
        assert f"Input: {FAKE_BANK_EXPORT_PATH}" in result.stdout
        assert written.loc[0, "import_batch_id"] == expected_batch_id
        assert written.loc[0, "transaction_id"] == "fake_bank_txn_001"
    finally:
        output_path.unlink(missing_ok=True)


def test_import_personal_csv_script_rejects_personal_mode_until_approved():
    """Personal mode should not be enabled from the standalone importer yet."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_personal_csv.py",
            "--mode",
            "personal",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Personal import mode is intentionally disabled" in result.stderr


def test_import_personal_csv_script_runs_from_project_root():
    """The beginner-friendly wrapper script should work without PYTHONPATH tricks."""
    output_path = PROJECT_ROOT / "data" / "processed" / "test_script_normalized.csv"
    if output_path.exists():
        output_path.unlink()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_personal_csv.py",
            "--input",
            str(TEMPLATE_PATH),
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Normalized 4 rows" in result.stdout
    assert output_path.exists()
    output_path.unlink()


def test_normalize_personal_transactions_allows_optional_metadata_columns():
    """Only columns needed for the internal schema should be required."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Fake Payroll Deposit",
                "amount": 2500.00,
                "source_category": "income",
            }
        ]
    )

    normalized = normalize_personal_transactions(raw)

    assert normalized[REQUIRED_COLUMNS].to_dict("records") == [
        {
            "date": "2026-04-01",
            "vendor": "Fake Payroll Deposit",
            "amount": 2500.00,
            "raw_category": "income",
        }
    ]
    assert normalized.loc[0, "source_file"] == "in_memory"
    assert normalized.loc[0, "source_row_number"] == 2
    assert normalized.loc[0, "import_batch_id"] == "manual"
    assert normalized.loc[0, "transaction_id"] == ""


def test_normalize_personal_transactions_escapes_spreadsheet_formula_text():
    """Generated CSV text should be safer to open in spreadsheet tools."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "=HYPERLINK(\"https://bad.example\")",
                "amount": -10.00,
                "source_category": "@risky_category",
            }
        ]
    )

    normalized = normalize_personal_transactions(raw)

    assert normalized.loc[0, "vendor"].startswith("'=")
    assert normalized.loc[0, "raw_category"].startswith("'@")


def test_normalize_personal_transactions_fails_on_missing_import_columns():
    """Bad exports should fail before they enter the app schema."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "2026-04-01",
                "description": "Fake Payroll Deposit",
                "amount": 2500.00,
            }
        ]
    )

    with pytest.raises(ValueError, match="Missing import columns: source_category"):
        normalize_personal_transactions(raw)


def test_normalize_personal_transactions_fails_on_invalid_normalized_values():
    """Importer output should reuse the same validation gate as the main pipeline."""
    raw = pd.DataFrame(
        [
            {
                "posted_date": "04/01/2026",
                "description": "Fake Payroll Deposit",
                "amount": 2500.00,
                "source_category": "income",
                "source_account": "Fake Checking",
                "notes": "fake fixture only",
            }
        ]
    )

    with pytest.raises(ValueError, match="Date values must use YYYY-MM-DD"):
        normalize_personal_transactions(raw)
