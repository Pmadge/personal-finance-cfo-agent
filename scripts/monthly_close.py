"""Run the safe sample monthly close workflow in one beginner-friendly command.

This script intentionally defaults to fake/sample data only. Real personal-data
mode is blocked until the project has more safety review and a clearer approval
workflow.
"""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from modules.categorization_review import (
    apply_category_overrides_file,
    build_category_review,
    write_category_review_file,
    write_override_template,
)
from modules.importers.personal_csv import normalize_personal_csv
from modules.workflow_audit import (
    build_personal_workflow_audit,
    validate_safe_audit_output_path,
    validate_safe_listed_output_path,
    validate_safe_workflow_path,
    write_personal_workflow_audit,
)

DEFAULT_INPUT = PROJECT_ROOT / "data" / "sample" / "personal_transactions_template.csv"
DEFAULT_NORMALIZED_OUTPUT = PROJECT_ROOT / "data" / "processed" / "normalized_personal_transactions.csv"
DEFAULT_REVIEW_OUTPUT = PROJECT_ROOT / "data" / "processed" / "category_review.csv"
DEFAULT_OVERRIDES = PROJECT_ROOT / "config" / "personal_rules.csv"
DEFAULT_APPLIED_REVIEW_OUTPUT = PROJECT_ROOT / "data" / "processed" / "category_review_applied.csv"
DEFAULT_AUDIT_MARKDOWN = PROJECT_ROOT / "data" / "processed" / "workflow_audit.md"
DEFAULT_AUDIT_JSON = PROJECT_ROOT / "data" / "processed" / "workflow_audit.json"
DEFAULT_REPORT_OUTPUT = PROJECT_ROOT / "outputs" / "personal" / "personal_cfo_report_draft.pdf"


def _relative(path):
    """Return project-relative path text when possible for beginner-friendly output."""
    path = Path(path)
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the local-first monthly close workflow with fake sample data."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run the safe fake/sample workflow. This is the only enabled mode for now.",
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "personal"],
        default="sample",
        help="Workflow mode. Personal mode is intentionally disabled for now.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--normalized-output", type=Path, default=DEFAULT_NORMALIZED_OUTPUT)
    parser.add_argument("--review-output", type=Path, default=DEFAULT_REVIEW_OUTPUT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--applied-review-output", type=Path, default=DEFAULT_APPLIED_REVIEW_OUTPUT)
    parser.add_argument("--audit-markdown", type=Path, default=DEFAULT_AUDIT_MARKDOWN)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
        help="Future report output path to list in the audit receipt.",
    )
    return parser.parse_args()


def _ensure_sample_mode(args):
    """Fail closed if the user tries personal mode before it is approved."""
    if args.mode == "personal":
        raise SystemExit(
            "Personal mode is intentionally disabled for now. "
            "Use --sample until the personal workflow has more safety review."
        )


def _is_under(path, root):
    """Return True when path resolves under root."""
    resolved_path = Path(path).expanduser().resolve()
    resolved_root = Path(root).resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _ensure_sample_input(input_path):
    """Sample mode must only process committed fake sample files."""
    if not _is_under(input_path, PROJECT_ROOT / "data" / "sample"):
        raise SystemExit(
            "Sample mode only accepts files under data/sample/. "
            "Personal or external CSVs are disabled until personal mode is approved."
        )


def _ensure_safe_paths(args):
    """Validate every writable or audit-listed path before any files are written."""
    workflow_output_paths = {
        "normalized_file": args.normalized_output,
        "category_review_file": args.review_output,
        "applied_review_file": args.applied_review_output,
    }
    for field_name, output_path in workflow_output_paths.items():
        if not validate_safe_workflow_path(field_name, output_path):
            raise SystemExit(
                "Processed workflow CSVs must stay under data/processed/. "
                f"Invalid {field_name}: {output_path}"
            )
    for audit_path in [args.audit_markdown, args.audit_json]:
        if not validate_safe_audit_output_path(audit_path):
            raise SystemExit(
                "Unsafe personal output path. Workflow audit artifacts must stay "
                f"under data/processed/ or outputs/personal/: {audit_path}"
            )
    if not validate_safe_workflow_path("override_file", args.overrides):
        raise SystemExit(
            "Unsafe override rules path. Use the Git-ignored local rules file "
            f"config/personal_rules.csv: {args.overrides}"
        )
    if not validate_safe_listed_output_path(args.report_output):
        raise SystemExit(
            "Unsafe personal output path. Listed report outputs must stay under "
            f"outputs/personal/: {args.report_output}"
        )


def _ensure_input_exists(input_path):
    """Fail before creating misleading outputs when the input file is missing."""
    if not Path(input_path).exists():
        raise SystemExit(f"Missing monthly close input: {input_path}")


def run_monthly_close(args):
    """Run import, review, overrides, and audit generation in order."""
    _ensure_sample_mode(args)
    _ensure_input_exists(args.input)
    _ensure_sample_input(args.input)
    _ensure_safe_paths(args)

    normalized_df = normalize_personal_csv(args.input, args.normalized_output)
    print(f"Step 1/5: normalized personal CSV -> {_relative(args.normalized_output)}")

    review_df = build_category_review(normalized_df)
    write_category_review_file(review_df, args.review_output)
    needs_review = int((review_df["review_status"] == "needs_review").sum())
    print(
        "Step 2/5: generated category review -> "
        f"{_relative(args.review_output)} ({needs_review} rows need review)"
    )

    if not args.overrides.exists():
        write_override_template(review_df, args.overrides)
        template_action = "created"
    else:
        template_action = "kept existing"
    print(
        "Step 3/5: ensured local override template -> "
        f"{_relative(args.overrides)} ({template_action})"
    )

    apply_category_overrides_file(
        args.review_output,
        args.overrides,
        args.applied_review_output,
    )
    reviewed_df = pd.read_csv(args.applied_review_output, keep_default_na=False)
    print(
        "Step 4/5: applied category overrides -> "
        f"{_relative(args.applied_review_output)}"
    )

    audit = build_personal_workflow_audit(
        mode="sample",
        input_file=args.input,
        normalized_file=args.normalized_output,
        category_review_file=args.review_output,
        override_file=args.overrides,
        applied_review_file=args.applied_review_output,
        reviewed_df=reviewed_df,
        self_check_status="NOT_RUN",
        output_paths=[args.report_output],
    )
    write_personal_workflow_audit(
        audit,
        markdown_path=args.audit_markdown,
        json_path=args.audit_json,
    )
    print(
        "Step 5/5: wrote workflow audit -> "
        f"{_relative(args.audit_markdown)} and {_relative(args.audit_json)}"
    )
    print("")
    print("Monthly close sample workflow complete.")
    print(f"Next: review {_relative(args.audit_markdown)}")
    print(f"If categories need changes, edit {_relative(args.overrides)} and rerun this command.")
    print("Reminder: do not use real financial data yet.")


def main():
    args = parse_args()
    run_monthly_close(args)


if __name__ == "__main__":
    main()
