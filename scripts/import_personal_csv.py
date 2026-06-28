"""Beginner-friendly local CSV normalization script.

This script uses fake/sample paths by default. For real personal data later,
keep input files under data/personal/ and output files under data/processed/.
"""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from modules.importers.personal_csv import (
    import_batch_id_for_file,
    normalize_fake_bank_export,
    normalize_personal_csv,
    resolve_local_path,
    validate_safe_output_path,
)

DEFAULT_INPUT = PROJECT_ROOT / "data" / "sample" / "personal_transactions_template.csv"
DEFAULT_FAKE_BANK_INPUT = PROJECT_ROOT / "data" / "sample" / "fake_bank_export_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "normalized_personal_transactions.csv"


def parse_args():
    """Parse optional input/output paths."""
    parser = argparse.ArgumentParser(
        description="Normalize a local personal-style CSV into the CFO Agent schema."
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "personal"],
        default="sample",
        help="Import mode. Personal mode is intentionally disabled until safety gates are complete.",
    )
    parser.add_argument(
        "--profile",
        choices=["template", "fake-bank"],
        default="template",
        help="Sample-only import profile to use. Does not enable real personal-data import.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to a CSV using the personal import template columns.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path where the normalized CSV should be written.",
    )
    return parser.parse_args()


def _is_under(path, root):
    """Return True when path resolves under root."""
    resolved_path = Path(path).expanduser().resolve()
    resolved_root = Path(root).resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _ensure_allowed_import_mode(args):
    """Keep the standalone import script aligned with fake-only project posture."""
    if args.mode == "personal":
        raise SystemExit(
            "Personal import mode is intentionally disabled until real-data safety gates are complete."
        )
    if not _is_under(args.input, PROJECT_ROOT / "data" / "sample"):
        raise SystemExit(
            "Sample import mode only accepts files under data/sample/. "
            "Do not import real statements until personal mode is explicitly approved."
        )


def _write_fake_bank_profile(input_path, output_path):
    """Normalize the fake bank profile and write the processed CSV."""
    if not validate_safe_output_path(output_path):
        raise SystemExit(
            "Unsafe personal output path. Use data/processed/ or outputs/personal/."
        )
    output_path = resolve_local_path(output_path)
    raw_df = pd.read_csv(input_path)
    normalized = normalize_fake_bank_export(
        raw_df,
        source_file=Path(input_path).name,
        import_batch_id=import_batch_id_for_file(input_path),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False)
    return normalized


def _normalize_with_profile(args):
    """Run the selected sample-only import profile."""
    if args.profile == "fake-bank" and args.input == DEFAULT_INPUT:
        args.input = DEFAULT_FAKE_BANK_INPUT
    if args.profile == "fake-bank":
        return _write_fake_bank_profile(args.input, args.output)
    return normalize_personal_csv(args.input, args.output)


def main():
    """Normalize a CSV and print the safe local output path."""
    args = parse_args()
    _ensure_allowed_import_mode(args)
    normalized = _normalize_with_profile(args)
    print(f"Normalized {len(normalized)} rows")
    print(f"Profile: {args.profile}")
    print(f"Input: {Path(args.input)}")
    print(f"Output: {Path(args.output)}")
    print("Reminder: keep real financial files in Git-ignored local folders only.")


if __name__ == "__main__":
    main()
