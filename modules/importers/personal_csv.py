"""Import helpers for local, manual personal CSV/Excel/PDF workflows.

This module is intentionally simple and offline. It turns safe bank-style CSV
or Excel exports into the internal transaction schema used by the rest of the app.
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
EXCEL_UPLOAD_EXTENSIONS = (".xlsx", ".xlsm")
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
BROKERAGE_DATE_COLUMNS = ["Date", "Activity Date", "Trade Date", "Settlement Date"]
BROKERAGE_ACTION_COLUMNS = ["Action", "Type", "Activity", "Transaction Type"]
BROKERAGE_DESCRIPTION_COLUMNS = ["Description", "Security Description", "Name"]
BROKERAGE_SYMBOL_COLUMNS = ["Symbol", "Ticker"]
BROKERAGE_AMOUNT_COLUMNS = ["Amount", "Net Amount", "Net Cash", "Cash Amount"]
BROKERAGE_QUANTITY_COLUMNS = ["Quantity", "Qty", "Shares"]
BROKERAGE_PRICE_COLUMNS = ["Price", "Share Price"]
BROKERAGE_FEE_COLUMNS = ["Fees", "Fee", "Commission"]
BROKERAGE_ACCOUNT_COLUMNS = ["Account", "Account Name"]
STATEMENT_DATE_RE = re.compile(r"^\d{2}/\d{2}$")
STATEMENT_FULL_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
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


def _first_existing_column(df, candidates):
    columns_by_lower = {str(column).strip().lower(): column for column in df.columns}
    for candidate in candidates:
        column = columns_by_lower.get(candidate.lower())
        if column is not None:
            return column
    return None


def _signed_money_to_float(value):
    text = "" if pd.isna(value) else str(value).strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")") or text.endswith("-") or text.startswith("-")
    cleaned = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace("-", "")
    number = float(cleaned or 0)
    return -number if negative else number


def normalize_brokerage_activity_export(
    df,
    source_file="brokerage_activity.csv",
    import_batch_id="manual_brokerage",
    source_row_start=2,
):
    """Normalize a brokerage activity CSV/Excel export into reviewable cash-flow rows."""
    date_col = _first_existing_column(df, BROKERAGE_DATE_COLUMNS)
    amount_col = _first_existing_column(df, BROKERAGE_AMOUNT_COLUMNS)
    action_col = _first_existing_column(df, BROKERAGE_ACTION_COLUMNS)
    description_col = _first_existing_column(df, BROKERAGE_DESCRIPTION_COLUMNS)
    symbol_col = _first_existing_column(df, BROKERAGE_SYMBOL_COLUMNS)
    if not date_col or not amount_col or not (action_col or description_col or symbol_col):
        raise ValueError("Missing brokerage activity columns: date, amount, and action/description/symbol")

    quantity_col = _first_existing_column(df, BROKERAGE_QUANTITY_COLUMNS)
    price_col = _first_existing_column(df, BROKERAGE_PRICE_COLUMNS)
    fee_col = _first_existing_column(df, BROKERAGE_FEE_COLUMNS)
    account_col = _first_existing_column(df, BROKERAGE_ACCOUNT_COLUMNS)

    rows = []
    negative_actions = {"buy", "reinvest", "fee", "withdrawal", "transfer out"}
    positive_actions = {"sell", "dividend", "interest", "deposit", "transfer in"}
    for _, row in df.iterrows():
        action = "" if action_col is None or pd.isna(row.get(action_col)) else str(row.get(action_col)).strip()
        symbol = "" if symbol_col is None or pd.isna(row.get(symbol_col)) else str(row.get(symbol_col)).strip()
        description = "" if description_col is None or pd.isna(row.get(description_col)) else str(row.get(description_col)).strip()
        amount = _signed_money_to_float(row.get(amount_col))
        action_key = action.lower()
        if amount >= 0 and action_key in negative_actions:
            amount = -abs(amount)
        elif amount <= 0 and action_key in positive_actions:
            amount = abs(amount)
        details = [part for part in [action, symbol, description] if part]
        for label, column in (("Qty", quantity_col), ("Price", price_col), ("Fees", fee_col)):
            if column is not None and not pd.isna(row.get(column)) and str(row.get(column)).strip():
                details.append(f"{label} {row.get(column)}")
        rows.append(
            {
                "posted_date": row.get(date_col),
                "description": " | ".join(details) or "Brokerage activity",
                "amount": amount,
                "source_category": f"investment_{action_key}" if action_key else "investment_activity",
                "source_account": row.get(account_col) if account_col is not None else "Brokerage",
            }
        )

    return normalize_personal_transactions(
        pd.DataFrame(rows),
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


def _statement_closing_date(lines):
    """Latest full MM/DD/YYYY date printed on the statement (closing/due date).

    Transaction rows print only MM/DD, so the statement's own full dates are the
    only trustworthy year source. Fail closed rather than guess a year.
    """
    dates = [
        (int(match.group(3)), int(match.group(1)), int(match.group(2)))
        for line in lines
        for match in STATEMENT_FULL_DATE_RE.finditer(line)
    ]
    if not dates:
        raise ValueError(
            "Could not find a full MM/DD/YYYY date in the PDF to determine the statement year"
        )
    return max(dates)


def parse_credit_union_visa_pdf(input_pdf, source_file="statement.pdf"):
    """Extract purchase rows from Credit Union Visa statement PDFs."""
    rows = []
    lines = _statement_pdf_lines(input_pdf)
    statement_year, statement_month, _ = _statement_closing_date(lines)
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
        # A January statement lists December purchases: months after the closing
        # month belong to the prior year.
        posted_year = statement_year - 1 if int(posted_month) > statement_month else statement_year
        raw_amount = lines[amount_index]
        magnitude = _money_to_float(raw_amount)
        rows.append(
            {
                "posted_date": f"{posted_year}-{posted_month}-{posted_day}",
                "description": lines[index + 4],
                # Trailing minus is the statement's credit notation: money back, not spend.
                "amount": magnitude if raw_amount.endswith("-") else -magnitude,
                "source_category": "misc",
                "source_account": "Credit Union Visa",
                "transaction_id": lines[index + 3],
            }
        )
    if not rows:
        raise ValueError("No Credit Union Visa statement transactions found in PDF")
    return pd.DataFrame(rows)


def read_uploaded_tabular_file(file_obj, source_file="uploaded.csv"):
    """Read one uploaded CSV or modern Excel workbook into a DataFrame."""
    source_name = Path(str(source_file)).name
    if source_name.lower().endswith(EXCEL_UPLOAD_EXTENSIONS):
        return pd.read_excel(file_obj)
    return pd.read_csv(file_obj)


def normalize_uploaded_statement_file(file_obj, source_file="uploaded"):
    """Normalize an uploaded CSV, Excel workbook, or Credit Union Visa PDF statement."""
    source_name = Path(str(source_file)).name
    if source_name.lower().endswith(".pdf"):
        parsed = parse_credit_union_visa_pdf(file_obj, source_file=source_name)
        return "credit-union-visa-pdf", normalize_personal_transactions(
            parsed,
            source_file=source_name,
            import_batch_id="upload_preview",
        )
    return normalize_uploaded_transactions(read_uploaded_tabular_file(file_obj, source_name), source_file=source_name)


def normalize_uploaded_files(file_items):
    """Normalize one upload or merge multiple Credit Union Visa PDF uploads."""
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
            parse_credit_union_visa_pdf(file_obj, source_file=source_name)
            for (file_obj, _), source_name in zip(file_items, source_names)
        ],
        ignore_index=True,
    )
    source_label = " + ".join(source_names)
    return " + ".join(source_names), "credit-union-visa-pdf-batch", normalize_personal_transactions(
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
    brokerage_date_col = _first_existing_column(df, BROKERAGE_DATE_COLUMNS)
    brokerage_amount_col = _first_existing_column(df, BROKERAGE_AMOUNT_COLUMNS)
    brokerage_identity_col = _first_existing_column(df, BROKERAGE_ACTION_COLUMNS + BROKERAGE_DESCRIPTION_COLUMNS + BROKERAGE_SYMBOL_COLUMNS)
    if brokerage_date_col and brokerage_amount_col and brokerage_identity_col:
        return "brokerage-activity", normalize_brokerage_activity_export(
            df,
            source_file=source_file,
            import_batch_id="upload_preview",
        )
    raise ValueError(
        "Unsupported upload columns. Use either "
        f"{', '.join(REQUIRED_IMPORT_COLUMNS)}, {', '.join(FAKE_BANK_EXPORT_COLUMNS)}, "
        "or a brokerage activity export with date, amount, and action/description/symbol columns."
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
