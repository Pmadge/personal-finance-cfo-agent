"""Audit artifacts for local personal workflow runs.

The audit file is a deterministic receipt for the import/review/override flow.
It is intentionally plain Markdown plus JSON so a person, future local app, or
AI assistant can inspect what happened without opening private transaction data.
"""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_AUDIT_OUTPUT_ROOTS = [
    PROJECT_ROOT / "data" / "processed",
    PROJECT_ROOT / "outputs" / "personal",
]
REQUIRED_AUDIT_FIELDS = [
    "run_timestamp",
    "mode",
    "input_file",
    "input_file_sha256",
    "normalized_file",
    "category_review_file",
    "override_file",
    "applied_review_file",
    "row_count",
    "override_count",
    "needs_review_count",
    "self_check_status",
    "output_paths",
    "privacy_status",
    "personal_data_warning",
]
VALID_MODES = {"sample", "personal"}
VALID_SELF_CHECK_STATUSES = {"PASS", "FAIL", "NOT_RUN"}
VALID_PRIVACY_STATUS = "local_only_gitignored_outputs"
SAFE_WORKFLOW_FILE_ROOTS = {
    "normalized_file": [PROJECT_ROOT / "data" / "processed"],
    "category_review_file": [PROJECT_ROOT / "data" / "processed"],
    "applied_review_file": [PROJECT_ROOT / "data" / "processed"],
}
SAFE_OVERRIDE_FILE = PROJECT_ROOT / "config" / "personal_rules.csv"
SAFE_LISTED_OUTPUT_ROOTS = [PROJECT_ROOT / "outputs" / "personal"]


def _utc_timestamp():
    """Return an ISO timestamp without microseconds for stable audit output."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_project_relative(path):
    """Return a project-relative path string when possible, otherwise None."""
    try:
        return str(Path(path).expanduser().resolve().relative_to(PROJECT_ROOT.resolve()))
    except (OSError, ValueError):
        return None


def _normalize_path(value, *, mode="sample", personal_source=False):
    """Store privacy-aware readable paths in audit artifacts.

    Project files are stored relative to the project root. External personal
    source paths are reduced to basenames so audit receipts do not leak local
    folder names if they are copied into a ticket, note, or portfolio draft.
    """
    if value is None:
        return ""
    path = Path(str(value))
    relative = _as_project_relative(path)
    if relative:
        return relative
    if mode == "personal" or personal_source:
        return path.name
    return str(value).replace("\n", " ").strip()


def _resolve_local_path(path):
    """Resolve relative project paths against PROJECT_ROOT, not the caller's cwd."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _sha256_file(path):
    """Return a SHA-256 digest for an existing local input file, or blank if absent."""
    try:
        resolved_path = _resolve_local_path(path)
        if not resolved_path.is_file():
            return ""
        return hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _is_under_any_root(path, roots):
    """Return True when path resolves under one of the approved roots."""
    resolved_path = _resolve_local_path(path)
    for root in roots:
        resolved_root = Path(root).resolve()
        if resolved_path == resolved_root or resolved_root in resolved_path.parents:
            return True
    return False


def validate_safe_audit_output_path(output_path):
    """Return True when an audit artifact path is under a private output root."""
    return _is_under_any_root(output_path, SAFE_AUDIT_OUTPUT_ROOTS)


def validate_safe_listed_output_path(output_path):
    """Return True when an output listed in the audit is under private report roots."""
    return _is_under_any_root(output_path, SAFE_LISTED_OUTPUT_ROOTS)


def validate_safe_workflow_path(field_name, path):
    """Return True when a workflow path matches its approved local-first location."""
    if field_name == "override_file":
        return _resolve_local_path(path) == SAFE_OVERRIDE_FILE.resolve()
    roots = SAFE_WORKFLOW_FILE_ROOTS.get(field_name)
    if roots is None:
        raise ValueError(f"Unknown workflow path field: {field_name}")
    return _is_under_any_root(path, roots)


def _normalized_review_status(reviewed_df):
    """Return normalized review status text for consistent audit/self-check counts."""
    if "review_status" not in reviewed_df.columns:
        return pd.Series([], dtype=str)
    return reviewed_df["review_status"].astype(str).str.strip().str.lower()


def _count_overrides(reviewed_df):
    """Count rows where a manual override was applied."""
    return int((_normalized_review_status(reviewed_df) == "manual_override").sum())


def _count_needs_review(reviewed_df):
    """Count rows that still need review after overrides."""
    return int((_normalized_review_status(reviewed_df) == "needs_review").sum())


def _personal_data_warning(mode):
    """Return a compact warning keyed to sample vs personal mode."""
    if mode == "sample":
        return "sample_or_fictional_data_only"
    if mode == "personal":
        return "private_local_data_do_not_commit"
    raise ValueError(f"Unsupported audit mode: {mode}")


def build_personal_workflow_audit(
    *,
    mode,
    input_file,
    normalized_file,
    category_review_file,
    override_file,
    applied_review_file,
    reviewed_df,
    self_check_status="NOT_RUN",
    output_paths=None,
    run_timestamp=None,
    allow_unsafe_paths=False,
):
    """Return audit metadata for one personal import/review/override run."""
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported audit mode: {mode}")
    if reviewed_df is None or not isinstance(reviewed_df, pd.DataFrame):
        raise ValueError("reviewed_df must be a pandas DataFrame")
    if output_paths is None:
        output_paths = []
    if not allow_unsafe_paths:
        workflow_paths = {
            "normalized_file": normalized_file,
            "category_review_file": category_review_file,
            "override_file": override_file,
            "applied_review_file": applied_review_file,
        }
        for field_name, path in workflow_paths.items():
            if not validate_safe_workflow_path(field_name, path):
                raise ValueError(
                    f"Unsafe workflow path for {field_name}. Use data/processed/ "
                    "for processed workflow files and config/personal_rules.csv "
                    f"for overrides: {path}"
                )
        unsafe_outputs = [str(path) for path in output_paths if not validate_safe_listed_output_path(path)]
        if unsafe_outputs:
            raise ValueError(
                "Unsafe workflow output path. Listed report outputs must stay under "
                f"outputs/personal/: {', '.join(unsafe_outputs)}"
            )

    return {
        "run_timestamp": run_timestamp or _utc_timestamp(),
        "mode": mode,
        "input_file": _normalize_path(input_file, mode=mode, personal_source=True),
        "input_file_sha256": _sha256_file(input_file),
        "normalized_file": _normalize_path(normalized_file, mode=mode),
        "category_review_file": _normalize_path(category_review_file, mode=mode),
        "override_file": _normalize_path(override_file, mode=mode),
        "applied_review_file": _normalize_path(applied_review_file, mode=mode),
        "row_count": int(len(reviewed_df)),
        "override_count": _count_overrides(reviewed_df),
        "needs_review_count": _count_needs_review(reviewed_df),
        "self_check_status": str(self_check_status),
        "output_paths": [_normalize_path(path, mode=mode) for path in output_paths],
        "privacy_status": VALID_PRIVACY_STATUS,
        "personal_data_warning": _personal_data_warning(mode),
    }


def _validate_timestamp(value):
    """Validate that run_timestamp is ISO-like and parseable."""
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid run_timestamp: {value}") from exc


def _validate_count(audit, field):
    """Validate non-negative integer count fields."""
    value = audit[field]
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid audit count for {field}: {value}")


def _validate_audit(audit, *, allow_unsafe_paths=False):
    """Fail closed if an audit dict is missing or misstates required fields."""
    missing = [field for field in REQUIRED_AUDIT_FIELDS if field not in audit]
    if missing:
        raise ValueError(f"Missing audit fields: {', '.join(missing)}")

    if audit["mode"] not in VALID_MODES:
        raise ValueError(f"Invalid audit mode: {audit['mode']}")
    input_hash = audit["input_file_sha256"]
    if input_hash and (
        not isinstance(input_hash, str)
        or len(input_hash) != 64
        or any(char not in "0123456789abcdef" for char in input_hash)
    ):
        raise ValueError("input_file_sha256 must be a lowercase 64-character SHA-256 digest or blank")
    _validate_timestamp(audit["run_timestamp"])
    for field in ["row_count", "override_count", "needs_review_count"]:
        _validate_count(audit, field)
    if audit["self_check_status"] not in VALID_SELF_CHECK_STATUSES:
        raise ValueError(f"Invalid self_check_status: {audit['self_check_status']}")
    if audit["privacy_status"] != VALID_PRIVACY_STATUS:
        raise ValueError(f"Invalid privacy_status: {audit['privacy_status']}")
    if audit["personal_data_warning"] != _personal_data_warning(audit["mode"]):
        raise ValueError("personal_data_warning does not match audit mode")
    if not isinstance(audit["output_paths"], list) or not all(
        isinstance(value, str) for value in audit["output_paths"]
    ):
        raise ValueError("output_paths must be a list of strings")
    if not allow_unsafe_paths:
        for field_name in ["normalized_file", "category_review_file", "override_file", "applied_review_file"]:
            if not validate_safe_workflow_path(field_name, audit[field_name]):
                raise ValueError(f"Unsafe workflow path for {field_name}: {audit[field_name]}")
        unsafe_outputs = [path for path in audit["output_paths"] if not validate_safe_listed_output_path(path)]
        if unsafe_outputs:
            raise ValueError(f"Unsafe workflow output path: {', '.join(unsafe_outputs)}")


def _escape_markdown_inline(value):
    """Escape audit values that are rendered inside Markdown backticks."""
    return str(value).replace("\n", " ").replace("`", "\\`")


def _markdown_list(values):
    """Render a Markdown bullet list, even when empty."""
    if not values:
        return "- None recorded"
    return "\n".join(f"- `{_escape_markdown_inline(value)}`" for value in values)


def _render_markdown(audit):
    """Render one human-readable audit receipt."""
    return f"""# Personal Workflow Audit

Run timestamp: {_escape_markdown_inline(audit['run_timestamp'])}
Mode: {_escape_markdown_inline(audit['mode'])}
Personal data warning: {_escape_markdown_inline(audit['personal_data_warning'])}
Privacy status: {_escape_markdown_inline(audit['privacy_status'])}
Self-check status: {_escape_markdown_inline(audit['self_check_status'])}

## Inputs

- Input file: `{_escape_markdown_inline(audit['input_file'])}`
- Input SHA-256: `{_escape_markdown_inline(audit['input_file_sha256'] or 'not_available')}`
- Normalized file: `{_escape_markdown_inline(audit['normalized_file'])}`
- Category review file: `{_escape_markdown_inline(audit['category_review_file'])}`
- Override file: `{_escape_markdown_inline(audit['override_file'])}`
- Applied review file: `{_escape_markdown_inline(audit['applied_review_file'])}`

## Counts

- Rows processed: {audit['row_count']}
- Manual overrides applied: {audit['override_count']}
- Rows still needing review: {audit['needs_review_count']}

## Outputs

{_markdown_list(audit['output_paths'])}

## Safety Notes

- Keep personal inputs in Git-ignored local folders only.
- Do not publish personal rules, processed personal rows, or private reports.
- Treat reports as trustworthy only when self-check status is PASS and rows needing review are zero.
"""


def write_personal_workflow_audit(
    audit,
    markdown_path,
    json_path,
    *,
    allow_unsafe_output=False,
):
    """Write a Markdown and JSON audit artifact, then return both paths."""
    _validate_audit(audit, allow_unsafe_paths=allow_unsafe_output)
    markdown_path = Path(markdown_path)
    json_path = Path(json_path)
    if not allow_unsafe_output:
        unsafe_paths = [
            str(path)
            for path in [markdown_path, json_path]
            if not validate_safe_audit_output_path(path)
        ]
        if unsafe_paths:
            raise ValueError(
                "Unsafe workflow audit output path. Use data/processed/ or "
                "outputs/personal/, or pass allow_unsafe_output=True only "
                f"for tests/non-personal scratch files: {', '.join(unsafe_paths)}"
            )
        markdown_path = _resolve_local_path(markdown_path)
        json_path = _resolve_local_path(json_path)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_markdown(audit))
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    return {"markdown": markdown_path, "json": json_path}
