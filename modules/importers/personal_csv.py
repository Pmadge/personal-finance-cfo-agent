"""Import helpers for local, manual personal CSV workflows.

This module is intentionally simple and offline. It turns safe bank-style CSV
exports into the internal transaction schema used by the rest of the app.
Direct module calls and the Streamlit upload screen use these helpers; the
standalone import CLI remains the fake/sample-only user entry point.
"""

from pathlib import Path
import hashlib
import re

import fitz
import pandas as pd

from modules.categorization_review import build_category_review, write_category_review_file
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
STATEMENT_DATE_RE = re.compile(r"^\d{2}/\d{2}$")
STATEMENT_REFERENCE_RE = re.compile(r"^\d{20,}$")
STATEMENT_MONEY_RE = re.compile(r"^\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}-?$")


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


def _statement_pdf_lines(input_pdf):
    if isinstance(input_pdf, (bytes, bytearray)):
        document = fitz.open(stream=input_pdf, filetype="pdf")
    else:
        document = fitz.open(input_pdf)
    return [line.strip() for page in document for line in page.get_text("text").splitlines() if line.strip()]


def _money_to_float(value):
    return float(str(value).replace("$", "").replace(",", "").replace("-", ""))


def parse_coasthills_visa_pdf(input_pdf, source_file="statement.pdf"):
    """Extract purchase rows from CoastHills FCU Visa statement PDFs."""
    rows = []
    lines = _statement_pdf_lines(input_pdf)
    for index in range(len(lines) - 5):
        if not (
            STATEMENT_DATE_RE.match(lines[index])
            and STATEMENT_DATE_RE.match(lines[index + 1])
            and lines[index + 2].startswith("PPLN")
            and STATEMENT_REFERENCE_RE.match(lines[index + 3])
        ):
            continue
        amount_index = index + 5
        if amount_index < len(lines) and lines[amount_index] == "$":
            amount_index += 1
        if amount_index >= len(lines) or not STATEMENT_MONEY_RE.match(lines[amount_index]):
            continue
        posted_month, posted_day = lines[index + 1].split("/")
        rows.append(
            {
                "posted_date": f"2026-{posted_month}-{posted_day}",
                "description": lines[index + 4],
                "amount": -_money_to_float(lines[amount_index]),
                "source_category": "misc",
                "source_account": "CoastHills FCU Visa",
                "transaction_id": lines[index + 3],
            }
        )
    if not rows:
        raise ValueError("No CoastHills Visa statement transactions found in PDF")
    return pd.DataFrame(rows)


def normalize_uploaded_statement_file(file_obj, source_file="uploaded"):
    """Normalize an uploaded CSV or CoastHills Visa PDF statement."""
    source_name = Path(str(source_file)).name
    if source_name.lower().endswith(".pdf"):
        parsed = parse_coasthills_visa_pdf(file_obj, source_file=source_name)
        return "coasthills-visa-pdf", normalize_personal_transactions(
            parsed,
            source_file=source_name,
            import_batch_id="upload_preview",
        )
    return normalize_uploaded_transactions(pd.read_csv(file_obj), source_file=source_name)


def normalize_uploaded_files(file_items):
    """Normalize one upload or merge multiple CoastHills Visa PDF uploads."""
    file_items = list(file_items)
    if not file_items:
        raise ValueError("Upload at least one file")
    source_names = [Path(str(source_file)).name for _, source_file in file_items]
    if len(file_items) == 1:
        profile, normalized = normalize_uploaded_statement_file(file_items[0][0], source_file=source_names[0])
        return source_names[0], profile, normalized
    if any(not source_name.lower().endswith(".pdf") for source_name in source_names):
        raise ValueError("Multiple uploads currently supports PDF statements only")
    raw = pd.concat(
        [
            parse_coasthills_visa_pdf(file_obj, source_file=source_name)
            for (file_obj, _), source_name in zip(file_items, source_names)
        ],
        ignore_index=True,
    )
    source_label = " + ".join(source_names)
    return " + ".join(source_names), "coasthills-visa-pdf-batch", normalize_personal_transactions(
        raw,
        source_file=source_label,
        import_batch_id="upload_preview",
    )


def normalize_uploaded_transactions(df, source_file="uploaded.csv"):
    """Detect a supported uploaded CSV profile and normalize it for preview."""
    columns = set(df.columns)
    if set(REQUIRED_IMPORT_COLUMNS).issubset(columns):
        return "personal-template", normalize_personal_transactions(
            df,
            source_file=source_file,
            import_batch_id="upload_preview",
        )
    if set(FAKE_BANK_EXPORT_COLUMNS).issubset(columns):
        return "debit-credit", normalize_fake_bank_export(
            df,
            source_file=source_file,
            import_batch_id="upload_preview",
        )
    raise ValueError(
        "Unsupported upload columns. Use either "
        f"{', '.join(REQUIRED_IMPORT_COLUMNS)} or {', '.join(FAKE_BANK_EXPORT_COLUMNS)}."
    )


def write_uploaded_transactions(df, output_path, source_file="uploaded.csv"):
    """Normalize an uploaded CSV and write it to an approved local processed path."""
    output_path = Path(output_path)
    if not validate_safe_output_path(output_path):
        raise ValueError("Unsafe personal output path. Use data/processed/ or outputs/personal/.")
    output_path = resolve_local_path(output_path)
    profile, normalized = normalize_uploaded_transactions(df, source_file=source_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False)
    return profile, normalized


def write_uploaded_category_review(df, output_path, source_file="uploaded.csv"):
    """Normalize an uploaded CSV and persist a local category review file."""
    output_path = Path(output_path)
    if not validate_safe_output_path(output_path):
        raise ValueError("Unsafe personal output path. Use data/processed/ or outputs/personal/.")
    output_path = resolve_local_path(output_path)
    profile, normalized = normalize_uploaded_transactions(df, source_file=source_file)
    review = build_category_review(normalized)
    write_category_review_file(review, output_path)
    return profile, review


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
