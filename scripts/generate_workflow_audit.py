"""Generate Markdown and JSON audit artifacts for the personal workflow."""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from modules.workflow_audit import (
    build_personal_workflow_audit,
    write_personal_workflow_audit,
)

DEFAULT_INPUT_FILE = PROJECT_ROOT / "data" / "sample" / "personal_transactions_template.csv"
DEFAULT_NORMALIZED_FILE = PROJECT_ROOT / "data" / "processed" / "normalized_personal_transactions.csv"
DEFAULT_CATEGORY_REVIEW_FILE = PROJECT_ROOT / "data" / "processed" / "category_review.csv"
DEFAULT_OVERRIDE_FILE = PROJECT_ROOT / "config" / "personal_rules.csv"
DEFAULT_APPLIED_REVIEW_FILE = PROJECT_ROOT / "data" / "processed" / "category_review_applied.csv"
DEFAULT_MARKDOWN_OUTPUT = PROJECT_ROOT / "data" / "processed" / "workflow_audit.md"
DEFAULT_JSON_OUTPUT = PROJECT_ROOT / "data" / "processed" / "workflow_audit.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate local audit artifacts for a personal finance workflow run."
    )
    parser.add_argument("--mode", choices=["sample", "personal"], default="sample")
    parser.add_argument("--input-file", type=Path, default=DEFAULT_INPUT_FILE)
    parser.add_argument("--normalized-file", type=Path, default=DEFAULT_NORMALIZED_FILE)
    parser.add_argument("--category-review-file", type=Path, default=DEFAULT_CATEGORY_REVIEW_FILE)
    parser.add_argument("--override-file", type=Path, default=DEFAULT_OVERRIDE_FILE)
    parser.add_argument("--applied-review-file", type=Path, default=DEFAULT_APPLIED_REVIEW_FILE)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--self-check-status", choices=["PASS", "FAIL", "NOT_RUN"], default="NOT_RUN")
    parser.add_argument(
        "--allow-unsafe-output-for-tests",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output-path",
        action="append",
        default=[],
        help="Optional generated report/output path to list in the audit. Can be used more than once.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.applied_review_file.exists():
        raise SystemExit(
            f"Missing applied review file: {args.applied_review_file}\n"
            "Run scripts/import_personal_csv.py, scripts/generate_category_review.py, "
            "and scripts/apply_category_overrides.py first."
        )

    reviewed_df = pd.read_csv(args.applied_review_file, keep_default_na=False)
    audit = build_personal_workflow_audit(
        mode=args.mode,
        input_file=args.input_file,
        normalized_file=args.normalized_file,
        category_review_file=args.category_review_file,
        override_file=args.override_file,
        applied_review_file=args.applied_review_file,
        reviewed_df=reviewed_df,
        self_check_status=args.self_check_status,
        output_paths=args.output_path,
        allow_unsafe_paths=args.allow_unsafe_output_for_tests,
    )
    written = write_personal_workflow_audit(
        audit,
        markdown_path=args.markdown_output,
        json_path=args.json_output,
        allow_unsafe_output=args.allow_unsafe_output_for_tests,
    )
    print(f"Wrote workflow audit: {written['markdown']}")
    print(f"Wrote workflow audit JSON: {written['json']}")
    print("Reminder: keep audit artifacts for personal runs in Git-ignored local folders.")


if __name__ == "__main__":
    main()
