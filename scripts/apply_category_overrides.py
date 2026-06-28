"""Apply local category overrides to a category review CSV.

This script is for the private, local personal-finance workflow. It expects a
Git-ignored override CSV such as config/personal_rules.csv.
"""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.categorization_review import (
    apply_category_overrides_file,
    build_category_review,
    write_override_template,
)

DEFAULT_REVIEW = PROJECT_ROOT / "data" / "processed" / "category_review.csv"
DEFAULT_OVERRIDES = PROJECT_ROOT / "config" / "personal_rules.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "category_review_applied.csv"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Apply local category overrides to reviewed personal transactions."
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--create-template",
        action="store_true",
        help="Create a blank override template from the review CSV, then stop.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.review.exists():
        raise SystemExit(
            f"Missing review file: {args.review}\n"
            "Run scripts/import_personal_csv.py and scripts/generate_category_review.py first."
        )

    if args.create_template:
        import pandas as pd

        review_df = pd.read_csv(args.review, keep_default_na=False)
        template_path = write_override_template(review_df, args.overrides)
        print(f"Wrote override template: {template_path}")
        print("Edit override_category only with approved categories, then rerun without --create-template.")
        return

    if not args.overrides.exists():
        raise SystemExit(
            f"Missing override file: {args.overrides}\n"
            "Create one with: python3 scripts/apply_category_overrides.py --create-template"
        )

    output_path = apply_category_overrides_file(args.review, args.overrides, args.output)
    print(f"Applied category overrides: {output_path}")
    print("Reminder: inspect final_category before trusting personal reports.")


if __name__ == "__main__":
    main()
