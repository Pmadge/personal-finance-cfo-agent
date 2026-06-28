"""Import helpers for local, manual personal CSV workflows.

This module is intentionally simple and offline. It turns safe bank-style CSV
exports into the internal transaction schema used by the rest of the app.
Direct module calls are lower-level helpers; while personal mode is disabled,
the standalone CLI remains the fake/sample-only user entry point.
"""

from pathlib import Path
import hashlib

import pandas as pd

from modules.validation import REQUIRED_COLUMNS, validate_transactions_for_processing

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_IMPORT_COLUMNS = [
    "posted_date",
    "description",
    "amount",
    "source_category",
]
OPTIONAL_IMPORT_COLUMNS = ["source_account", "notes", "transaction_id"]
IMPORT_TEMPLATE_COLUMNS = REQUIRED_IMPORT_COLUMNS + OPTIONAL_IMPORT_COLUMNS
IDENTITY_COLUMNS = [
    "source_file",
    "source_row_number",
    "import_batch_id",
    "transaction_id",
]
SAFE_OUTPUT_ROOTS = [
    PROJECT_ROOT / "data" / "processed",
    PROJECT_ROOT / "outputs" / "personal",
]
SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")

COLUMN_MAP = {
    "posted_date": "date",
    "description": "vendor",
    "amount": "amount",
    "source_category": "raw_category",
}


def _missing_import_columns(df):
    """Return required import columns absent from the raw export."""
    return [column for column in REQUIRED_IMPORT_COLUMNS if column not in df.columns]


def _escape_spreadsheet_formula_text(value):
    """Prefix formula-like text so spreadsheet apps treat it as text."""
    text = "" if pd.isna(value) else str(value).strip()
    if text.startswith("'"):
        return text
    if text.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def import_batch_id_for_file(input_path):
    """Return a short deterministic import batch id for one source file."""
    input_path = Path(input_path)
    digest = hashlib.sha256(input_path.read_bytes()).hexdigest()[:12]
    return f"import_{digest}"


def resolve_local_path(path):
    """Resolve relative project paths against PROJECT_ROOT, not the caller's cwd."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def validate_safe_output_path(output_path):
    """Return True when output is under an approved personal-data output root."""
    resolved_output = resolve_local_path(output_path)
    for root in SAFE_OUTPUT_ROOTS:
        resolved_root = root.resolve()
        if resolved_output == resolved_root or resolved_root in resolved_output.parents:
            return True
    return False


FAKE_BANK_EXPORT_COLUMNS = [
    "Transaction Date",
    "Description",
    "Debit",
    "Credit",
    "Category",
    "Account Name",
    "Transaction ID",
]


def _missing_fake_bank_columns(df):
    """Return required columns absent from the fake bank export profile."""
    return [column for column in FAKE_BANK_EXPORT_COLUMNS if column not in df.columns]


def normalize_fake_bank_export(
    df,
    source_file="fake_bank_export_profile.csv",
    import_batch_id="manual_fake_bank",
    source_row_start=2,
):
    """Normalize the committed fake bank-export profile into the app schema."""
    missing_columns = _missing_fake_bank_columns(df)
    if missing_columns:
        raise ValueError(f"Missing fake bank export columns: {', '.join(missing_columns)}")

    debit = pd.Series(pd.to_numeric(df["Debit"].replace("", pd.NA), errors="coerce"), index=df.index)
    credit = pd.Series(pd.to_numeric(df["Credit"].replace("", pd.NA), errors="coerce"), index=df.index)
    has_debit = debit.notna()
    has_credit = credit.notna()
    if ((has_debit & has_credit) | (~has_debit & ~has_credit)).any():
        raise ValueError("Each fake bank export row must have exactly one of Debit or Credit")

    template_df = pd.DataFrame(
        {
            "posted_date": df["Transaction Date"],
            "description": df["Description"],
            "amount": credit.fillna(0) - debit.fillna(0),
            "source_category": df["Category"],
            "source_account": df["Account Name"],
            "transaction_id": df["Transaction ID"],
        }
    )
    return normalize_personal_transactions(
        template_df,
        source_file=source_file,
        import_batch_id=import_batch_id,
        source_row_start=source_row_start,
    )


def normalize_personal_transactions(
    df,
    source_file="in_memory",
    import_batch_id="manual",
    source_row_start=2,
):
    """Normalize a personal-style CSV data frame into the app transaction schema."""
    missing_columns = _missing_import_columns(df)
    if missing_columns:
        raise ValueError(f"Missing import columns: {', '.join(missing_columns)}")

    normalized = df[list(COLUMN_MAP.keys())].rename(columns=COLUMN_MAP)
    normalized = normalized[REQUIRED_COLUMNS].copy()
    normalized["vendor"] = normalized["vendor"].map(_escape_spreadsheet_formula_text)
    normalized["raw_category"] = (
        normalized["raw_category"].map(_escape_spreadsheet_formula_text).str.lower()
    )
    normalized["source_file"] = _escape_spreadsheet_formula_text(Path(str(source_file)).name)
    normalized["source_row_number"] = range(
        source_row_start,
        source_row_start + len(normalized),
    )
    normalized["import_batch_id"] = _escape_spreadsheet_formula_text(import_batch_id)
    if "transaction_id" in df.columns:
        normalized["transaction_id"] = df["transaction_id"].map(
            _escape_spreadsheet_formula_text
        )
    else:
        normalized["transaction_id"] = ""

    normalized = normalized[REQUIRED_COLUMNS + IDENTITY_COLUMNS]
    return validate_transactions_for_processing(normalized)


def normalize_personal_csv(input_path, output_path, allow_unsafe_output=False):
    """Read a local CSV export, normalize it, and write the processed CSV.

    Set allow_unsafe_output=True only for tests or non-personal scratch files.
    Normalized personal workflow CSVs should stay under data/processed/.
    Report-style outputs belong under outputs/personal/.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not allow_unsafe_output and not validate_safe_output_path(output_path):
        raise ValueError(
            "Unsafe personal output path. Use data/processed/ or outputs/personal/, "
            "or pass allow_unsafe_output=True for tests/non-personal scratch files."
        )
    if not allow_unsafe_output:
        output_path = resolve_local_path(output_path)

    raw_df = pd.read_csv(input_path)
    normalized_df = normalize_personal_transactions(
        raw_df,
        source_file=input_path.name,
        import_batch_id=import_batch_id_for_file(input_path),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_df.to_csv(output_path, index=False)
    return normalized_df
