"""Generate a draft personal CFO report from reviewed fake personal rows."""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from modules.config import APPROVED_CATEGORIES
from modules.personal_report_charts import build_personal_insights, generate_personal_report_charts
from modules.personal_report_inputs import build_report_transactions_from_review
from modules.self_checks import assert_personal_report_self_checks
from modules.workflow_audit import validate_safe_listed_output_path

DEFAULT_REVIEWED_INPUT = PROJECT_ROOT / "data" / "processed" / "category_review_applied.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "personal" / "personal_cfo_report_draft.pdf"
DEFAULT_CHARTS_DIR = PROJECT_ROOT / "outputs" / "personal" / "charts"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a local draft personal CFO report from reviewed fake data."
    )
    parser.add_argument("--reviewed-input", type=Path, default=DEFAULT_REVIEWED_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--charts-dir", type=Path, default=DEFAULT_CHARTS_DIR)
    parser.add_argument(
        "--allow-unsafe-input-for-tests",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _relative(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def _is_under(path, root):
    resolved_path = Path(path).expanduser().resolve()
    resolved_root = Path(root).resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _validate_paths(reviewed_input, output, charts_dir, allow_unsafe_input_for_tests=False):
    if not Path(reviewed_input).exists():
        raise SystemExit(f"Missing reviewed input: {reviewed_input}")
    if not allow_unsafe_input_for_tests:
        if Path(reviewed_input).expanduser().resolve() != DEFAULT_REVIEWED_INPUT.resolve():
            raise SystemExit(
                "Fake personal report generation only accepts the default reviewed "
                "sample workflow file until personal mode is approved: "
                f"{DEFAULT_REVIEWED_INPUT}"
            )
        if not _is_under(reviewed_input, PROJECT_ROOT / "data" / "processed"):
            raise SystemExit("Reviewed input must stay under data/processed/ until personal mode is approved.")
    if not validate_safe_listed_output_path(output):
        raise SystemExit(f"Unsafe personal report output path. Use outputs/personal/: {output}")
    if not validate_safe_listed_output_path(charts_dir):
        raise SystemExit(f"Unsafe personal report charts path. Use outputs/personal/: {charts_dir}")


def _money(value):
    return f"${value:,.2f}"


def _image(path, width=6.1 * inch):
    """Return a reportlab image scaled for the page."""
    image = Image(str(path))
    ratio = image.imageHeight / float(image.imageWidth)
    image.drawWidth = width
    image.drawHeight = width * ratio
    return image


def build_draft_personal_report(report_df, output_path, charts_dir=DEFAULT_CHARTS_DIR):
    """Lower-level renderer; callers must run assert_personal_report_self_checks first."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    income = float(report_df.loc[report_df["amount"] > 0, "amount"].sum())
    expenses = float(-report_df.loc[report_df["amount"] < 0, "amount"].sum())
    net_cash_flow = income - expenses
    by_category = (
        report_df.assign(spend=report_df["amount"].where(report_df["amount"] < 0, 0).abs())
        .groupby("assigned_category", as_index=False)["spend"]
        .sum()
        # Keep only categories with actual spend so the table matches the
        # spending-by-category chart, which excludes income/zero-spend rows.
        .loc[lambda frame: frame["spend"] > 0]
        .sort_values("spend", ascending=False)
    )
    insights = build_personal_insights(report_df)
    charts = generate_personal_report_charts(report_df, charts_dir)

    styles = getSampleStyleSheet()
    story = [
        Paragraph("Draft Personal CFO Report", styles["Title"]),
        Spacer(1, 0.18 * inch),
        Paragraph("Sample or fictional data only. Do not use real financial data yet.", styles["BodyText"]),
        Spacer(1, 0.2 * inch),
        Paragraph("Visual CFO Snapshot", styles["Heading2"]),
        Table(
            [
                ["Insight", "Value"],
                ["Largest Spending Category", f"{insights['largest_spending_category']} ({_money(insights['largest_spending_amount'])})"],
                ["Savings Rate", f"{insights['savings_rate']:.2f}%"],
                ["Net Cash Flow", _money(insights["net_cash_flow"])],
            ],
            hAlign="LEFT",
        ),
        Spacer(1, 0.2 * inch),
        _image(charts["spending_by_category"], width=5.9 * inch),
        PageBreak(),
        Paragraph("Cash Flow Waterfall", styles["Heading2"]),
        _image(charts["cash_flow_waterfall"], width=5.9 * inch),
        Spacer(1, 0.2 * inch),
        Paragraph("Cash Flow Summary", styles["Heading2"]),
        Table(
            [
                ["Metric", "Amount"],
                ["Income", _money(income)],
                ["Expenses", _money(expenses)],
                ["Net Cash Flow", _money(net_cash_flow)],
            ],
            hAlign="LEFT",
        ),
        Spacer(1, 0.2 * inch),
        Paragraph("Spending by Category", styles["Heading2"]),
    ]

    category_rows = [[row["assigned_category"], _money(float(row["spend"]))] for _, row in by_category.iterrows()]
    story.append(Table([["Category", "Spend"], *category_rows], hAlign="LEFT"))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Reviewed Transactions", styles["Heading2"]))
    transaction_rows = [
        [row["date"], row["vendor"], _money(float(row["amount"])), row["assigned_category"]]
        for _, row in report_df.iterrows()
    ]
    transaction_table = Table([["Date", "Vendor", "Amount", "Category"], *transaction_rows], hAlign="LEFT")
    transaction_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(transaction_table)

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=0.65 * inch, rightMargin=0.65 * inch)
    doc.build(story)
    return output_path


def main():
    args = parse_args()
    _validate_paths(args.reviewed_input, args.output, args.charts_dir, args.allow_unsafe_input_for_tests)
    review_df = pd.read_csv(args.reviewed_input, keep_default_na=False)
    report_df = build_report_transactions_from_review(review_df)
    checks = assert_personal_report_self_checks(review_df, report_df, APPROVED_CATEGORIES)
    print(f"Personal report self-checks passed ({len(checks)} checks).")
    output_path = build_draft_personal_report(report_df, args.output, args.charts_dir)
    print(f"Wrote draft personal report: {_relative(output_path)}")
    print(f"Wrote personal report charts: {_relative(args.charts_dir)}")
    print("Reminder: sample or fictional data only. Do not use real financial data yet.")


if __name__ == "__main__":
    main()
