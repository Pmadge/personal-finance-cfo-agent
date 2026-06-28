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
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from modules.analytics import monthly_summary
from modules.capital_events import home_purchase_readiness, major_purchase_check
from modules.config import APPROVED_CATEGORIES, SAMPLE_PERSONAL_PROFILE
from modules.forecast import cash_runway, project_cash_flow
from modules.goals import track_goals
from modules.net_worth import net_worth_snapshot
from modules.personal_report_charts import build_personal_insights, generate_personal_report_charts
from modules.personal_report_inputs import build_report_transactions_from_review
from modules.risk import build_risk_register, risk_summary
from modules.scenarios import compare_scenarios
from modules.scorecard import outcomes_scorecard
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


_EMOJI_REPLACEMENTS = {
    "🟢": "[Green]", "🟡": "[Yellow]", "🔴": "[Red]",
    "✅": "", "📊": "", "⚪": "", "⚠️": "Warning:",
}


def _clean(text):
    """Strip status emoji so the PDF font renders the text cleanly."""
    result = str(text)
    for emoji, replacement in _EMOJI_REPLACEMENTS.items():
        result = result.replace(emoji, replacement)
    return result.strip()


def _para_table(headers, rows, col_widths, header_style, cell_style):
    """A wrapped-text table so long findings and status text never overflow."""
    data = [[Paragraph(_clean(h), header_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(_clean(str(cell)), cell_style) for cell in row])
    table = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _add_pillar_sections(story, report_df, profile, styles):
    """Append the full CFO pillar suite to the personal report.

    Runway, 12-month projection, goals, scenarios, risk register, and capital-event
    readiness all run on the reviewed transactions plus the supplied financial
    profile (assets, liabilities, goals, scenarios, home target). The outcomes
    scorecard is added only when the data spans more than one month.
    """
    header_style = ParagraphStyle(
        "PillarHeader", parent=styles["BodyText"], textColor=colors.white,
        fontName="Helvetica-Bold", fontSize=9, leading=11,
    )
    cell_style = ParagraphStyle("PillarCell", parent=styles["BodyText"], fontSize=9, leading=11)

    assets = profile["assets"]
    liabilities = profile["liabilities"]
    liquid_cash = float(assets.get("Checking", 0.0)) + float(assets.get("Savings", 0.0))
    months = pd.to_datetime(report_df["date"]).dt.to_period("M").astype(str)
    report_month = months.max()
    prior_month = str(pd.Period(report_month, freq="M") - 1)
    summary = monthly_summary(report_df, report_month)
    net_worth = net_worth_snapshot(assets, liabilities)

    story.append(PageBreak())
    story.append(Paragraph("Cash Runway", styles["Heading2"]))
    runway = cash_runway(report_df, liquid_cash)
    runway_months = runway["Emergency Runway (months)"]
    runway_rows = [
        ["Liquid Cash", _money(runway["Liquid Cash"])],
        ["Average Monthly Expenses", _money(runway["Monthly Expenses"])],
        ["Monthly Net Cash Flow", _money(runway["Monthly Net Cash Flow"])],
        ["Emergency Runway", f"{runway_months} months" if runway_months is not None else "No recurring expenses"],
        ["Assessment", runway["Status"]],
    ]
    story.append(_para_table(["Metric", "Value"], runway_rows, [3.0 * inch, 3.3 * inch], header_style, cell_style))

    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("12-Month Cash Projection", styles["Heading2"]))
    projection = project_cash_flow(
        report_df, starting_cash=liquid_cash, months=12,
        start_month=str(pd.Period(report_month, freq="M") + 1),
    )
    projection_rows = [
        [r["Month"], _money(r["Projected Income"]), _money(r["Projected Expenses"]), _money(r["Net Cash Flow"]), _money(r["Ending Cash"])]
        for _, r in projection.iterrows()
    ]
    story.append(_para_table(
        ["Month", "Income", "Expenses", "Net", "Ending Cash"], projection_rows,
        [1.0 * inch, 1.35 * inch, 1.35 * inch, 1.3 * inch, 1.3 * inch], header_style, cell_style,
    ))

    story.append(PageBreak())
    story.append(Paragraph("Goal Tracker", styles["Heading2"]))
    live_goals = [dict(goal) for goal in profile["goals"]]
    for goal in live_goals:
        if goal["type"] == "net_worth":
            goal["current_amount"] = net_worth["Net Worth"]
        elif goal["type"] == "savings_rate":
            goal["current_amount"] = summary["Savings Rate"]
    goals = track_goals(live_goals, as_of_date=f"{report_month}-28", default_monthly=summary["Net Cash Flow"])
    goal_rows = [
        [r["Goal"], _money(r["Target"]), _money(r["Current"]), f"{r['Progress (%)']:.0f}%", r["Status"]]
        for _, r in goals.iterrows()
    ]
    story.append(_para_table(
        ["Goal", "Target", "Current", "Progress", "Status"], goal_rows,
        [1.4 * inch, 0.95 * inch, 0.95 * inch, 0.7 * inch, 2.3 * inch], header_style, cell_style,
    ))

    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("What-If Scenarios", styles["Heading2"]))
    scenarios = compare_scenarios(report_df, liquid_cash, profile["scenarios"])
    scenario_rows = [
        [r["Scenario"], _money(r["Net Cash Flow"]),
         f"{r['Runway (months)']}" if r["Runway (months)"] is not None else "n/a",
         _money(r["Cash in 12 Months"]), r["Cash-Out Risk"]]
        for _, r in scenarios.iterrows()
    ]
    story.append(_para_table(
        ["Scenario", "Net", "Runway", "Cash 12mo", "Cash-Out Risk"], scenario_rows,
        [1.6 * inch, 1.1 * inch, 0.8 * inch, 1.2 * inch, 1.6 * inch], header_style, cell_style,
    ))

    story.append(PageBreak())
    story.append(Paragraph("Risk Register", styles["Heading2"]))
    risk = build_risk_register(report_df, assets, liabilities, liquid_cash)
    _, risk_overall = risk_summary(risk)
    story.append(Paragraph(_clean(risk_overall), styles["BodyText"]))
    story.append(Spacer(1, 0.08 * inch))
    risk_rows = [[r["Risk"], r["Level"], r["Finding"], r["Recommendation"]] for _, r in risk.iterrows()]
    story.append(_para_table(
        ["Risk", "Level", "Finding", "Recommendation"], risk_rows,
        [1.2 * inch, 0.85 * inch, 2.3 * inch, 2.0 * inch], header_style, cell_style,
    ))

    story.append(PageBreak())
    story.append(Paragraph("Capital Event: Home Purchase Readiness", styles["Heading2"]))
    home = home_purchase_readiness(report_df, assets, **profile["home_target"])
    story.append(Paragraph(_clean(f"Readiness to buy a {_money(home['home_price'])} home: {home['verdict']}"), styles["BodyText"]))
    story.append(Spacer(1, 0.08 * inch))
    payment_pct = f"{home['payment_to_income']}%" if home["payment_to_income"] is not None else "n/a"
    home_rows = [
        ["Down Payment + Closing", _money(home["cash_needed"])],
        ["Liquid Cash Available", _money(home["liquid_cash"])],
        ["Cash After Purchase", _money(home["cash_after_purchase"])],
        ["Monthly Payment (PITI)", _money(home["monthly_payment_piti"])],
        ["Payment as % of Income (target <=28%)", payment_pct],
    ]
    story.append(_para_table(["Metric", "Value"], home_rows, [3.0 * inch, 3.3 * inch], header_style, cell_style))
    if home["gaps"]:
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(_clean("Gaps to close: " + " ".join(home["gaps"])), styles["BodyText"]))
    purchase = major_purchase_check(report_df, assets, profile["major_purchase"], liquid_cash=liquid_cash)
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        _clean(f"Major purchase check ({_money(purchase['amount'])}): {purchase['verdict']} - {purchase['note']}"),
        styles["BodyText"],
    ))

    if bool((months == prior_month).any()):
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Outcomes Scorecard", styles["Heading2"]))
        card = outcomes_scorecard(report_df, report_month, prior_month)

        def _fmt(metric, value):
            return f"{value:.2f}%" if metric == "Savings Rate" else _money(value)

        card_rows = [
            [r["Metric"], _fmt(r["Metric"], r["This Month"]), _fmt(r["Metric"], r["Last Month"]), _fmt(r["Metric"], r["Change"]), r["Trend"]]
            for _, r in card.iterrows()
        ]
        story.append(_para_table(
            ["Metric", "This Month", "Last Month", "Change", "Trend"], card_rows,
            [1.4 * inch, 1.2 * inch, 1.2 * inch, 1.1 * inch, 1.4 * inch], header_style, cell_style,
        ))


def build_draft_personal_report(report_df, output_path, charts_dir=DEFAULT_CHARTS_DIR, profile=None):
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

    _add_pillar_sections(story, report_df, profile or SAMPLE_PERSONAL_PROFILE, styles)

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
