"""Build the Alex Rivera Monthly CFO Report PDF."""

from pathlib import Path
import shutil
import sys
from xml.sax.saxutils import escape

import fitz
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.action_items import generate_action_items
from modules.analytics import (
    budget_vs_actual,
    cumulative_budget_vs_actual,
    monthly_summary,
    upcoming_obligations,
)
from modules.categorizer import categorize_file
from modules.charts import generate_all_charts
from modules.capital_events import home_purchase_readiness, major_purchase_check, rent_vs_buy
from modules.config import (
    ALEX_ASSETS,
    ALEX_BUDGET,
    ALEX_GOALS,
    ALEX_HOME_TARGET,
    ALEX_LIABILITIES,
    ALEX_MAJOR_PURCHASE,
    ALEX_SCENARIOS,
    APPROVED_CATEGORIES,
    MODEL_VERSION,
    PORTFOLIO_DEMO_ASSETS,
    PORTFOLIO_DEMO_BUDGET,
    PORTFOLIO_DEMO_CATEGORIZED,
    PORTFOLIO_DEMO_FICTIONAL_DATA_NOTICE,
    PORTFOLIO_DEMO_GOALS,
    PORTFOLIO_DEMO_HOME_TARGET,
    PORTFOLIO_DEMO_LIABILITIES,
    PORTFOLIO_DEMO_MAJOR_PURCHASE,
    PORTFOLIO_DEMO_PDF,
    PORTFOLIO_DEMO_PERSONA_NAME,
    PORTFOLIO_DEMO_SCENARIOS,
    PORTFOLIO_DEMO_TRANSACTIONS,
    REPORT_MONTH,
    REPORT_MONTH_LABEL,
)
from modules.detectors import detect_recurring, detect_unusual
from modules.goals import track_goals
from modules.risk import build_risk_register, risk_summary
from modules.scenarios import compare_scenarios
from modules.scorecard import ENGAGEMENT_CADENCE, ENGAGEMENT_SCOPE, outcomes_scorecard
from modules.forecast import cash_runway, forecast_cash_flow, project_cash_flow
from modules.net_worth import debt_payoff_comparison, net_worth_snapshot
from modules.narrative import cfo_commentary, executive_summary
from modules.self_checks import assert_pipeline_self_checks
from modules.validation import build_audit_log


MONTH = REPORT_MONTH
MONTH_LABEL = REPORT_MONTH_LABEL
PDF_PATH = PROJECT_ROOT / "test_personas" / "starter_person" / "outputs" / "monthly_cfo_report.pdf"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "pdf_review"
FOOTER = f"{MODEL_VERSION} | Fictional Alex Rivera data only | Generated for {MONTH_LABEL}"


def default_report_config():
    """Return the default fictional Alex Rivera report configuration."""
    return {
        "persona_name": "Alex Rivera",
        "fictional_notice": "Fictional Alex Rivera data only",
        "raw_path": PROJECT_ROOT / "test_personas" / "starter_person" / "transactions.csv",
        "categorized_path": PROJECT_ROOT / "test_personas" / "starter_person" / "transactions_categorized.csv",
        "pdf_path": PDF_PATH,
        "budget": ALEX_BUDGET,
        "assets": ALEX_ASSETS,
        "liabilities": ALEX_LIABILITIES,
        "goals": ALEX_GOALS,
        "scenarios": ALEX_SCENARIOS,
        "home_target": ALEX_HOME_TARGET,
        "major_purchase": ALEX_MAJOR_PURCHASE,
        "dashboard_note": (
            "One-page CFO answer: Alex has strong monthly cash generation, but the dashboard highlights the "
            "thin emergency runway, debt load, goal progress, and capital-event readiness before the detailed pages."
        ),
    }


def portfolio_demo_report_config():
    """Return the richer fictional household configuration used for portfolio screenshots."""
    return {
        "persona_name": PORTFOLIO_DEMO_PERSONA_NAME,
        "fictional_notice": f"{PORTFOLIO_DEMO_FICTIONAL_DATA_NOTICE} only",
        "raw_path": PROJECT_ROOT / PORTFOLIO_DEMO_TRANSACTIONS,
        "categorized_path": PROJECT_ROOT / PORTFOLIO_DEMO_CATEGORIZED,
        "pdf_path": PROJECT_ROOT / PORTFOLIO_DEMO_PDF,
        "budget": PORTFOLIO_DEMO_BUDGET,
        "assets": PORTFOLIO_DEMO_ASSETS,
        "liabilities": PORTFOLIO_DEMO_LIABILITIES,
        "goals": PORTFOLIO_DEMO_GOALS,
        "scenarios": PORTFOLIO_DEMO_SCENARIOS,
        "home_target": PORTFOLIO_DEMO_HOME_TARGET,
        "major_purchase": PORTFOLIO_DEMO_MAJOR_PURCHASE,
        "dashboard_note": (
            "One-page CFO answer: this richer fictional household combines dual income, mortgage-level housing, "
            "childcare, debt payoff, savings transfers, home-buying goals, and surprise expenses so the report "
            "shows more real-life financial complexity than a simple starter persona."
        ),
    }


def resolve_report_config(report_config=None):
    """Merge a custom report configuration with the default report settings."""
    config = default_report_config()
    if report_config:
        config.update(report_config)
    return config


def money(value):
    """Format a numeric value as dollars."""
    return f"${float(value):,.2f}"


def percent(value):
    """Format a numeric value as a percentage."""
    return f"{float(value):.2f}%"


def clean_text(value):
    """Keep PDF text ASCII-friendly and readable."""
    text = str(value)
    replacements = {
        "⚠️": "Warning:",
        "🟢": "Green:",
        "🟡": "Yellow:",
        "🔴": "Red:",
        "✅": "",
        "📊": "",
        "⚪": "",
        "—": "-",
        "–": "-",
        "×": "x",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return escape(text)


def risk_level_counts(risk_df):
    """Count risk levels after stripping visual status prefixes."""
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for level in risk_df["Level"]:
        clean_level = clean_text(level)
        for key in counts:
            if key in clean_level:
                counts[key] += 1
                break
    return counts


def table_paragraph(value, styles):
    """Wrap table cells safely."""
    return Paragraph(clean_text(value), styles["TableCell"])


def build_styles():
    """Create report styles."""
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextClean",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItalicCommentary",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            leading=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )
    )
    return styles


def section(title, styles):
    """Create a section heading."""
    return Paragraph(title, styles["SectionTitle"])


def styled_table(headers, rows, styles, col_widths=None):
    """Create a styled report table with wrapped text."""
    data = [[Paragraph(clean_text(header), styles["TableHeader"]) for header in headers]]
    for row in rows:
        data.append([table_paragraph(cell, styles) for cell in row])

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
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


def chart_image(path, width=6.8 * inch):
    """Create a reportlab image scaled to fit the page."""
    image = Image(str(path))
    ratio = image.imageHeight / float(image.imageWidth)
    image.drawWidth = width
    image.drawHeight = width * ratio
    return image


def footer_for(report_config):
    """Create a PDF footer function for the selected fictional report persona."""
    footer_text = f"{MODEL_VERSION} | {report_config['fictional_notice']} | Generated for {MONTH_LABEL}"

    def _footer(canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(doc.leftMargin, 0.42 * inch, footer_text)
        canvas.drawRightString(letter[0] - doc.rightMargin, 0.42 * inch, f"Page {doc.page}")
        canvas.restoreState()

    return _footer


def collect_report_data(output_dir=None, report_config=None):
    """Collect all computed data used by the PDF."""
    report_config = resolve_report_config(report_config)
    raw_path = Path(report_config["raw_path"])
    categorized_path = Path(report_config["categorized_path"])
    output_dir = Path(output_dir) if output_dir is not None else PROJECT_ROOT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    budget = report_config["budget"]
    assets = report_config["assets"]
    liabilities = report_config["liabilities"]
    goals = report_config["goals"]
    scenarios = report_config["scenarios"]
    home_target = report_config["home_target"]
    major_purchase_amount = report_config["major_purchase"]

    df, accuracy_rate = categorize_file(raw_path, categorized_path)
    assert_pipeline_self_checks(
        df,
        report_month=MONTH,
        approved_categories=APPROVED_CATEGORIES,
    )
    chart_metadata = generate_all_charts(df, budget, output_dir)

    summary = monthly_summary(df, MONTH)
    budget_df = budget_vs_actual(df, MONTH, budget)
    cumulative_budget_df = cumulative_budget_vs_actual(df, budget)
    upcoming_df = upcoming_obligations(df)
    recurring_df = detect_recurring(df)
    unusual_df = detect_unusual(df)
    unusual_df = unusual_df[unusual_df["Transaction Date"].str.startswith(MONTH)]
    forecast_df = forecast_cash_flow(df)
    liquid_cash = assets["Checking"] + assets["Savings"]
    runway = cash_runway(df, liquid_cash)
    projection_df = project_cash_flow(
        df, starting_cash=liquid_cash, months=12, start_month=str(pd.Period(MONTH, freq="M") + 1)
    )
    scenario_df = compare_scenarios(df, liquid_cash, scenarios)
    audit_df = build_audit_log(df, accuracy_rate, raw_path, PROJECT_ROOT)
    debts = [
        {"name": name, "balance": details["balance"], "interest_rate": details["interest_rate"]}
        for name, details in liabilities.items()
    ]
    net_worth = net_worth_snapshot(assets, liabilities)
    debt_df = debt_payoff_comparison(debts)
    action_df = generate_action_items(df, MONTH, budget, owner=report_config["persona_name"])

    # Goal tracker: fill the live net-worth and savings-rate values for this month.
    live_goals = [dict(goal) for goal in goals]
    for goal in live_goals:
        if goal["type"] == "net_worth":
            goal["current_amount"] = net_worth["Net Worth"]
        elif goal["type"] == "savings_rate":
            goal["current_amount"] = summary["Savings Rate"]
    goal_df = track_goals(
        live_goals,
        as_of_date=f"{MONTH}-28",
        default_monthly=summary["Net Cash Flow"],
    )
    risk_df = build_risk_register(df, assets, liabilities, liquid_cash)
    _, risk_overall = risk_summary(risk_df)
    home_readiness = home_purchase_readiness(df, assets, **home_target)
    major_purchase = major_purchase_check(df, assets, major_purchase_amount, liquid_cash=liquid_cash)
    rent_buy = rent_vs_buy(df, **home_target)
    scorecard_df = outcomes_scorecard(df, MONTH, str(pd.Period(MONTH, freq="M") - 1))

    biggest_budget_miss = budget_df.sort_values("Variance ($)").iloc[0].to_dict()
    month_data = {
        "summary": summary,
        "biggest_budget_miss": biggest_budget_miss,
        "upcoming_total": upcoming_df["Expected Amount"].sum(),
        "upcoming_count": len(upcoming_df),
        "month_label": MONTH_LABEL,
    }

    return {
        "summary": summary,
        "budget_df": budget_df,
        "cumulative_budget_df": cumulative_budget_df,
        "upcoming_df": upcoming_df,
        "recurring_df": recurring_df,
        "unusual_df": unusual_df,
        "forecast_df": forecast_df,
        "runway": runway,
        "projection_df": projection_df,
        "scenario_df": scenario_df,
        "audit_df": audit_df,
        "net_worth": net_worth,
        "debt_df": debt_df,
        "goal_df": goal_df,
        "risk_df": risk_df,
        "risk_overall": risk_overall,
        "home_readiness": home_readiness,
        "major_purchase": major_purchase,
        "rent_vs_buy": rent_buy,
        "scorecard_df": scorecard_df,
        "action_df": action_df,
        "executive_summary": executive_summary(month_data),
        "cfo_commentary": cfo_commentary(month_data),
        "chart_metadata": chart_metadata,
        "report_config": report_config,
    }


def add_cover(story, styles, report_config=None):
    """Add the report cover page."""
    report_config = resolve_report_config(report_config)
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph(f"{report_config['persona_name']} - Monthly CFO Report: {MONTH_LABEL}", styles["CoverTitle"]))
    story.append(Paragraph("Prepared by: CFO Agent", styles["Title"]))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(f"{report_config['fictional_notice']} - no real personal financial data.", styles["BodyTextClean"]))
    story.append(PageBreak())


def add_cash_flow(story, styles, summary):
    """Add cash flow overview table."""
    rows = [
        ["Income", money(summary["Income"])],
        ["Total Expenses", money(summary["Total Expenses"])],
        ["Net Cash Flow", money(summary["Net Cash Flow"])],
        ["Savings Rate", percent(summary["Savings Rate"])],
    ]
    story.append(section("Cash Flow Overview", styles))
    story.append(styled_table(["Metric", "Amount"], rows, styles, [2.4 * inch, 2.4 * inch]))


def add_forecast_section(story, styles, forecast_df):
    """Add base/upside/downside forecast scenarios."""
    rows = [
        [
            row["Scenario"],
            row["Period Days"],
            money(row["Forecast Income"]),
            money(row["Fixed Obligations"]),
            money(row["Variable Spending"]),
            money(row["Net Cash Flow"]),
            percent(row["Savings Rate"]),
            money(row["Ending Cash"]),
        ]
        for _, row in forecast_df.iterrows()
    ]
    story.append(Spacer(1, 0.2 * inch))
    story.append(section("Forward Forecast Scenarios", styles))
    story.append(
        styled_table(
            [
                "Scenario",
                "Days",
                "Income",
                "Fixed",
                "Variable",
                "Net Cash Flow",
                "Savings Rate",
                "Ending Cash",
            ],
            rows,
            styles,
            [0.75 * inch, 0.45 * inch, 0.8 * inch, 0.75 * inch, 0.75 * inch, 0.9 * inch, 0.75 * inch, 0.8 * inch],
        )
    )


def add_scorecard(story, styles, scorecard_df):
    """Add the outcomes scorecard: this month vs last month, with direction."""
    story.append(Spacer(1, 0.18 * inch))
    story.append(section("Outcomes Scorecard", styles))
    rows = []
    for _, row in scorecard_df.iterrows():
        is_rate = row["Metric"] == "Savings Rate"
        fmt = (lambda v: f"{v:.2f}%") if is_rate else money
        rows.append([row["Metric"], fmt(row["This Month"]), fmt(row["Last Month"]), fmt(row["Change"]), row["Trend"]])
    story.append(
        styled_table(
            ["Metric", "This Month", "Last Month", "Change", "Trend"],
            rows,
            styles,
            [1.5 * inch, 1.2 * inch, 1.2 * inch, 1.1 * inch, 1.6 * inch],
        )
    )


def add_executive_dashboard(story, styles, data):
    """Add a one-page dashboard that consolidates the board pack's key answer."""
    summary = data["summary"]
    runway = data["runway"]
    risk_counts = risk_level_counts(data["risk_df"])
    top_action = data["action_df"].sort_values("Rank").iloc[0]
    top_goal = data["goal_df"].iloc[0]
    home = data["home_readiness"]
    rent_buy = data["rent_vs_buy"]

    story.append(section("Executive Dashboard", styles))
    story.append(
        Paragraph(
            clean_text(data["report_config"]["dashboard_note"]),
            styles["BodyTextClean"],
        )
    )
    savings_note = (
        "Above the target savings rate for the month."
        if summary["Savings Rate"] >= 20 else
        "Below the target savings rate; review the drivers before adding new commitments."
    )
    rows = [
        ["Net Cash Flow", money(summary["Net Cash Flow"]), "Core monthly surplus available for goals and risk reduction."],
        ["Savings Rate", percent(summary["Savings Rate"]), savings_note],
        [
            "Emergency Runway",
            f"{runway['Emergency Runway (months)']} months" if runway["Emergency Runway (months)"] is not None else "n/a",
            runway["Status"],
        ],
        [
            "Risk Register",
            f"High {risk_counts.get('High', 0)} / Medium {risk_counts.get('Medium', 0)} / Low {risk_counts.get('Low', 0)}",
            clean_text(data["risk_overall"]),
        ],
        ["Top Goal", top_goal["Goal"], top_goal["Status"]],
        ["Capital Event", f"Home purchase: {home['verdict']}", "Do not buy until cash and payment gaps close."],
        ["Rent vs Buy", rent_buy["cheaper"], rent_buy["recommendation"]],
        ["Next Action", top_action["Action Item"], f"Impact: {money(top_action['Estimated Dollar Impact'])}"],
    ]
    story.append(
        styled_table(
            ["Area", "Current Readout", "CFO Interpretation"],
            rows,
            styles,
            [1.25 * inch, 1.75 * inch, 3.65 * inch],
        )
    )
    story.append(PageBreak())


def add_engagement(story, styles):
    """Add the CFO engagement summary: defined scope and cadence."""
    story.append(PageBreak())
    story.append(section("Your CFO Engagement", styles))
    story.append(Paragraph("This personal CFO engagement includes:", styles["BodyTextClean"]))
    for item in ENGAGEMENT_SCOPE:
        story.append(Paragraph(clean_text(f"- {item}"), styles["BodyTextClean"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(clean_text(ENGAGEMENT_CADENCE), styles["BodyTextClean"]))


def add_forecast_depth(story, styles, data):
    """Add the cash runway and the 12-month cash projection."""
    runway = data["runway"]
    story.append(PageBreak())
    story.append(section("Cash Runway", styles))
    em_months = runway["Emergency Runway (months)"]
    emergency = (
        f"{em_months} months ({runway['Emergency Runway (weeks)']} weeks)"
        if em_months is not None else "No recurring expenses"
    )
    bare = runway["Bare-Bones Runway (months)"]
    runway_rows = [
        ["Liquid Cash (checking + savings)", money(runway["Liquid Cash"])],
        ["Average Monthly Expenses", money(runway["Monthly Expenses"])],
        ["Essential Monthly Bills", money(runway["Essential Monthly Bills"])],
        ["Monthly Net Cash Flow", money(runway["Monthly Net Cash Flow"])],
        ["Emergency Runway (covers all spending)", emergency],
        ["Bare-Bones Runway (essential bills only)", f"{bare} months" if bare is not None else "n/a"],
    ]
    if runway["Months Until Cash Runs Out"] is not None:
        runway_rows.append(
            ["Months Until Cash Runs Out (current burn)", f"{runway['Months Until Cash Runs Out']} months"]
        )
    runway_rows.append(["Assessment", runway["Status"]])
    story.append(styled_table(["Metric", "Value"], runway_rows, styles, [3.2 * inch, 3.4 * inch]))

    story.append(Spacer(1, 0.25 * inch))
    story.append(section("12-Month Cash Projection", styles))
    projection_rows = [
        [
            row["Month"],
            money(row["Projected Income"]),
            money(row["Projected Expenses"]),
            money(row["Net Cash Flow"]),
            money(row["Ending Cash"]),
        ]
        for _, row in data["projection_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Month", "Income", "Expenses", "Net Cash Flow", "Ending Cash"],
            projection_rows,
            styles,
            [1.0 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("What-If Scenarios", styles))
    scenario_rows = [
        [
            row["Scenario"],
            money(row["Net Cash Flow"]),
            f"{row['Runway (months)']}" if row["Runway (months)"] is not None else "n/a",
            money(row["Cash in 12 Months"]),
            row["Cash-Out Risk"],
        ]
        for _, row in data["scenario_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Scenario", "Net Cash Flow", "Runway (mo)", "Cash in 12 Mo", "Cash-Out Risk"],
            scenario_rows,
            styles,
            [1.8 * inch, 1.2 * inch, 0.8 * inch, 1.3 * inch, 1.5 * inch],
        )
    )


def add_variance_notes(story, styles, budget_df, cumulative_budget_df):
    """Add FP&A variance explanations and cumulative budget context."""
    over_budget = budget_df[budget_df["Variance ($)"] < 0].copy()
    rows = [
        [
            row["Category"],
            money(row["Budget Amount"]),
            money(row["Actual Amount"]),
            money(row["Variance ($)"]),
            row["Variance Driver"],
            row["Forward Impact"],
        ]
        for _, row in over_budget.iterrows()
    ]
    story.append(Spacer(1, 0.2 * inch))
    story.append(section("Budget Variance Notes", styles))
    story.append(
        styled_table(
            ["Category", "Budget", "Actual", "Variance", "Driver", "Forward Impact"],
            rows,
            styles,
            [0.85 * inch, 0.65 * inch, 0.65 * inch, 0.7 * inch, 1.75 * inch, 1.85 * inch],
        )
    )

    cumulative_rows = [
        [
            row["Category"],
            money(row["3-Month Budget"]),
            money(row["3-Month Actual"]),
            money(row["Variance ($)"]),
            percent(row["Variance (%)"]),
        ]
        for _, row in cumulative_budget_df.iterrows()
    ]
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        styled_table(
            ["Category", "3-Month Budget", "3-Month Actual", "Variance", "Variance %"],
            cumulative_rows,
            styles,
            [1.25 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 0.9 * inch],
        )
    )


def add_chart_section(story, styles, title, image_path):
    """Add one chart with a page break after it."""
    story.append(PageBreak())
    story.append(section(title, styles))
    story.append(chart_image(image_path))


def add_report_tables(story, styles, data):
    """Add all report tables after charts."""
    story.append(PageBreak())
    story.append(section("Recurring Vendor Tracker", styles))
    recurring_rows = [
        [
            row["Vendor"],
            money(row["Avg Monthly Amount"]),
            row["Occurrences"],
            row["Next Expected Date"],
            row["Flag"],
        ]
        for _, row in data["recurring_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Vendor", "Avg Monthly Amount", "Occurrences", "Next Expected Date", "Flag"],
            recurring_rows,
            styles,
            [1.7 * inch, 1.0 * inch, 0.8 * inch, 1.0 * inch, 1.5 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("Unusual Expense Flags", styles))
    unusual_rows = [
        [
            row["Transaction Date"],
            row["Vendor"],
            money(row["Amount"]),
            money(row["Category Average"]),
            row["Flag Type"],
            row["Flag Message"],
        ]
        for _, row in data["unusual_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Date", "Vendor", "Amount", "Category Avg", "Type", "Flag Message"],
            unusual_rows,
            styles,
            [0.75 * inch, 1.0 * inch, 0.7 * inch, 0.75 * inch, 0.9 * inch, 2.7 * inch],
        )
    )

    story.append(Spacer(1, 0.2 * inch))
    story.append(section("Upcoming Obligations - Next 30 Days", styles))
    upcoming_rows = [
        [row["Vendor"], row["Expected Date"], money(row["Expected Amount"])]
        for _, row in data["upcoming_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Vendor", "Expected Date", "Expected Amount"],
            upcoming_rows,
            styles,
            [2.6 * inch, 1.3 * inch, 1.3 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("Net Worth Snapshot", styles))
    net_rows = [[key, money(value) if key != "Debt-to-Asset Ratio" else percent(value)] for key, value in data["net_worth"].items()]
    story.append(styled_table(["Metric", "Value"], net_rows, styles, [2.4 * inch, 2.4 * inch]))

    story.append(Spacer(1, 0.25 * inch))
    story.append(section("Debt Payoff Analysis", styles))
    debt_rows = [
        [
            row["Method"],
            money(row["Total Interest Paid"]),
            row["Months to Payoff"],
            row["Recommended Method"],
            row["Recommendation Explanation"],
        ]
        for _, row in data["debt_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Method", "Total Interest", "Months", "Recommended", "Explanation"],
            debt_rows,
            styles,
            [0.8 * inch, 0.9 * inch, 0.6 * inch, 0.9 * inch, 3.3 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("Goal Tracker", styles))
    goal_rows = [
        [
            row["Goal"],
            money(row["Target"]),
            money(row["Current"]),
            f"{row['Progress (%)']:.0f}%",
            row["Status"],
        ]
        for _, row in data["goal_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Goal", "Target", "Current", "Progress", "Status"],
            goal_rows,
            styles,
            [1.5 * inch, 0.95 * inch, 0.95 * inch, 0.7 * inch, 2.9 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("Risk Register", styles))
    story.append(Paragraph(clean_text(data["risk_overall"]), styles["BodyTextClean"]))
    story.append(Spacer(1, 0.12 * inch))
    risk_rows = [
        [row["Risk"], row["Level"], row["Finding"], row["Recommendation"]]
        for _, row in data["risk_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Risk", "Level", "Finding", "Recommendation"],
            risk_rows,
            styles,
            [1.25 * inch, 0.85 * inch, 2.35 * inch, 2.15 * inch],
        )
    )

    story.append(PageBreak())
    story.append(section("Capital Event: Home Purchase Readiness", styles))
    home = data["home_readiness"]
    story.append(
        Paragraph(
            clean_text(f"Readiness to buy a {money(home['home_price'])} home: {home['verdict']}"),
            styles["BodyTextClean"],
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    payment_pct = f"{home['payment_to_income']}%" if home["payment_to_income"] is not None else "n/a"
    home_rows = [
        ["Down Payment + Closing Costs", money(home["cash_needed"])],
        ["Liquid Cash Available", money(home["liquid_cash"])],
        ["Cash After Purchase", money(home["cash_after_purchase"])],
        ["Loan Amount", money(home["loan_amount"])],
        ["Estimated Monthly Payment (PITI)", money(home["monthly_payment_piti"])],
        ["Payment as % of Income (target <=28%)", payment_pct],
        ["Emergency Buffer to Preserve", money(home["emergency_buffer_required"])],
    ]
    story.append(styled_table(["Metric", "Value"], home_rows, styles, [3.2 * inch, 3.4 * inch]))
    if home["gaps"]:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(clean_text("Gaps to close: " + " ".join(home["gaps"])), styles["BodyTextClean"]))
    purchase = data["major_purchase"]
    story.append(Spacer(1, 0.18 * inch))
    story.append(
        Paragraph(
            clean_text(f"Major purchase check ({money(purchase['amount'])}): {purchase['verdict']} - {purchase['note']}"),
            styles["BodyTextClean"],
        )
    )

    rent_buy = data["rent_vs_buy"]
    story.append(Spacer(1, 0.22 * inch))
    story.append(section(f"Rent vs Buy ({rent_buy['horizon_years']}-Year)", styles))
    rent_buy_rows = [
        ["Current Monthly Rent", money(rent_buy["current_monthly_rent"])],
        [f"Total Rent ({rent_buy['horizon_years']} yrs)", money(rent_buy["rent_net_cost"])],
        ["Buy: Upfront (down + closing)", money(rent_buy["buy_upfront"])],
        [f"Buy: Total PITI ({rent_buy['horizon_years']} yrs)", money(rent_buy["buy_total_piti"])],
        ["Buy: Home Equity at Horizon", money(rent_buy["buy_equity_at_horizon"])],
        ["Buy: Net Cost", money(rent_buy["buy_net_cost"])],
        ["Lower Net Cost", rent_buy["cheaper"]],
    ]
    story.append(styled_table(["Metric", "Value"], rent_buy_rows, styles, [3.2 * inch, 3.4 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(clean_text(rent_buy["recommendation"]), styles["BodyTextClean"]))

    story.append(PageBreak())
    story.append(section("AI Action Items", styles))
    action_rows = [
        [
            row["Rank"],
            row["Action Item"],
            row["Owner"],
            row["Due Date"],
            row["Status"],
            money(row["Estimated Dollar Impact"]),
            row["Evaluation"],
        ]
        for _, row in data["action_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Rank", "Action Item", "Owner", "Due", "Status", "Impact", "Eval"],
            action_rows,
            styles,
            [0.35 * inch, 3.15 * inch, 0.75 * inch, 0.75 * inch, 0.55 * inch, 0.6 * inch, 0.5 * inch],
        )
    )

    story.append(Spacer(1, 0.25 * inch))
    story.append(section("Model Version Log", styles))
    audit_rows = [
        [row["Check"], row["Status"], row["Detail"]]
        for _, row in data["audit_df"].iterrows()
    ]
    story.append(
        styled_table(
            ["Check", "Status", "Detail"],
            audit_rows,
            styles,
            [1.65 * inch, 0.7 * inch, 4.0 * inch],
        )
    )
    story.append(
        Paragraph(
            f"{MODEL_VERSION} - deterministic Python pipeline using {data['report_config']['fictional_notice']}. "
            "Fixed obligations are separated from discretionary recurring behavior; forecasts are scenario estimates, not financial advice.",
            styles["BodyTextClean"],
        )
    )


def build_pdf(output_path=None, output_dir=None, report_config=None):
    """Build the full Monthly CFO Report PDF."""
    report_config = resolve_report_config(report_config)
    pdf_path = Path(output_path) if output_path is not None else Path(report_config["pdf_path"])
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    data = collect_report_data(output_dir=output_dir, report_config=report_config)
    chart_paths = {
        row["Chart"]: Path(row["Path"])
        for _, row in data["chart_metadata"].iterrows()
    }

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.65 * inch,
    )

    story = []
    add_cover(story, styles, report_config)
    story.append(section("Executive Summary", styles))
    story.append(Paragraph(clean_text(data["executive_summary"]), styles["BodyTextClean"]))
    add_executive_dashboard(story, styles, data)
    story.append(section("CFO Commentary", styles))
    story.append(Paragraph(clean_text(data["cfo_commentary"]), styles["ItalicCommentary"]))
    add_scorecard(story, styles, data["scorecard_df"])
    add_cash_flow(story, styles, data["summary"])
    add_variance_notes(story, styles, data["budget_df"], data["cumulative_budget_df"])
    add_forecast_section(story, styles, data["forecast_df"])
    add_forecast_depth(story, styles, data)
    add_chart_section(story, styles, "Budget vs. Actual", chart_paths["Budget vs. Actual"])
    add_chart_section(story, styles, "Spending by Category", chart_paths["Spending by Category"])
    add_chart_section(story, styles, "Savings Rate Trend", chart_paths["Monthly Savings Rate Trend"])
    add_chart_section(story, styles, "Month-over-Month Spending", chart_paths["Month-over-Month Spending"])
    add_report_tables(story, styles, data)
    add_engagement(story, styles)

    footer = footer_for(report_config)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return pdf_path


def render_pdf_for_review(pdf_path, review_dir=None):
    """Render PDF pages to PNG files for visual review."""
    review_dir = Path(review_dir) if review_dir is not None else REVIEW_DIR
    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)

    document = fitz.open(pdf_path)
    rendered_paths = []
    for page_number in range(document.page_count):
        page = document.load_page(page_number)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        output_path = review_dir / f"page_{page_number + 1:02d}.png"
        pixmap.save(output_path)
        rendered_paths.append(output_path)
    document.close()
    return rendered_paths


def main():
    """Build the PDF and render review images."""
    pdf_path = build_pdf()
    rendered_paths = render_pdf_for_review(pdf_path)
    print(f"PDF generated: {pdf_path}")
    print(f"Rendered review pages: {REVIEW_DIR}")
    print(f"Page count: {len(rendered_paths)}")
    for path in rendered_paths:
        print(path)


if __name__ == "__main__":
    main()
