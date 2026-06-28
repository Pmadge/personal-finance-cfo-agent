"""Generate a local category review CSV from normalized personal transactions.

This uses fake/sample paths by default. For real personal data later, keep inputs
and outputs inside Git-ignored local folders and review categories before reports.
"""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from modules.categorization_review import build_category_review, write_category_review_file

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "normalized_personal_transactions.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "category_review.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a local category review CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(
            f"Missing normalized input: {args.input}\n"
            "Run scripts/import_personal_csv.py first."
        )

    normalized_df = pd.read_csv(args.input)
    review_df = build_category_review(normalized_df)
    output_path = write_category_review_file(review_df, args.output)
    needs_review = int((review_df["review_status"] == "needs_review").sum())

    print(f"Wrote category review rows: {len(review_df)}")
    print(f"Rows needing manual review: {needs_review}")
    print(f"Output: {output_path}")
    print("Reminder: review final_category before trusting personal reports.")


if __name__ == "__main__":
    main()
