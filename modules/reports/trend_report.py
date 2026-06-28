"""Build the Alex Rivera 3-Month Trend Summary PDF."""

from pathlib import Path
import shutil
import sys
from xml.sax.saxutils import escape

import fitz
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.analytics import monthly_summary, upcoming_obligations
from modules.categorizer import categorize_file
from modules.config import (
    APPROVED_CATEGORIES,
    MODEL_VERSION,
    MONTH_LABELS,
    REPORT_MONTH_LABEL,
    TREND_MONTHS,
)
from modules.detectors import detect_unusual
from modules.self_checks import assert_pipeline_self_checks


PDF_PATH = PROJECT_ROOT / "outputs" / "alex_rivera_3_month_trend_summary_2026_q1.pdf"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "trend_report_review"
FOOTER = f"{MODEL_VERSION} | Fictional Alex Rivera data only | 3-Month Trend Summary"
MONTHS = TREND_MONTHS
START_DEBT_BALANCE = 24500.00


def money(value):
    """Format dollars."""
    return f"${float(value):,.2f}"


def percent(value):
    """Format percentages."""
    return f"{float(value):.2f}%"


def clean_text(value):
    """Escape PDF paragraph text."""
    text = str(value).replace("—", "-").replace("–", "-")
    return escape(text).replace("\n", "<br/>")


def build_styles():
    """Create compact report styles."""
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TrendTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TrendSubtitle",
            parent=styles["BodyText"],
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading3"],
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#111827"),
            spaceBefore=4,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontSize=7,
            leading=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontSize=7,
            leading=8,
            textColor=colors.white,
        )
    )
    return styles


def cell(value, styles):
    """Wrap a table cell."""
    return Paragraph(clean_text(value), styles["TableCell"])


def header_cell(value, styles):
    """Wrap a table header."""
    return Paragraph(clean_text(value), styles["TableHeader"])


def compact_table(headers, rows, styles, col_widths):
    """Create a compact table for the one-page trend report."""
    data = [[header_cell(header, styles) for header in headers]]
    data.extend([[cell(value, styles) for value in row] for row in rows])
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def trend_arrow(current, previous):
    """Return an ASCII-safe trend marker."""
    if previous is None:
        return "Flat"
    if current > previous:
        return "Up"
    if current < previous:
        return "Down"
    return "Flat"


def collect_trend_data():
    """Compute all data used by the 3-month trend report."""
    raw_path = PROJECT_ROOT / "data" / "alex_rivera_transactions.csv"
    categorized_path = PROJECT_ROOT / "data" / "alex_rivera_transactions_categorized.csv"
    df, _ = categorize_file(raw_path, categorized_path)
    for month in MONTHS:
        assert_pipeline_self_checks(
            df,
            report_month=month,
            approved_categories=APPROVED_CATEGORIES,
        )
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)

    monthly_rows = []
    previous_savings_rate = None
    previous_subscription_total = None
    top_category_rows = []
    subscription_rows = []

    for month in MONTHS:
        summary = monthly_summary(df, month)
        savings_arrow = trend_arrow(summary["Savings Rate"], previous_savings_rate)
        monthly_rows.append(
            [
                MONTH_LABELS[month],
                percent(summary["Savings Rate"]),
                savings_arrow,
                money(summary["Net Cash Flow"]),
            ]
        )
        previous_savings_rate = summary["Savings Rate"]

        month_expenses = df[(df["month"] == month) & (df["amount"] < 0)].copy()
        month_expenses["spend"] = month_expenses["amount"].abs()
        top3 = (
            month_expenses.groupby("assigned_category")["spend"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
        )
        top_category_rows.append(
            [
                MONTH_LABELS[month],
                "\n".join([f"{category}: {money(amount)}" for category, amount in top3.items()]),
            ]
        )

        subscription_total = month_expenses[
            month_expenses["assigned_category"] == "Subscriptions"
        ]["spend"].sum()
        subscription_arrow = trend_arrow(subscription_total, previous_subscription_total)
        subscription_rows.append(
            [MONTH_LABELS[month], money(subscription_total), subscription_arrow]
        )
        previous_subscription_total = subscription_total

    unusual_df = detect_unusual(df)
    if unusual_df.empty:
        highest_unusual_month = MONTHS[-1]
        highest_unusual_count = 0
    else:
        unusual_df["Month"] = unusual_df["Transaction Date"].str.slice(0, 7)
        unusual_counts = unusual_df.groupby("Month").size()
        highest_unusual_month = unusual_counts.idxmax()
        highest_unusual_count = int(unusual_counts.loc[highest_unusual_month])

    fixed_obligations = upcoming_obligations(df)
    fixed_obligation_total = (
        float(fixed_obligations["Expected Amount"].sum())
        if not fixed_obligations.empty
        else 0.0
    )

    student_loan_payments = df[
        (df["vendor"] == "Federal Student Loan Servicer")
        & (df["amount"] < 0)
    ]["amount"].abs().sum()
    ending_debt_balance = START_DEBT_BALANCE - student_loan_payments

    first_summary = monthly_summary(df, MONTHS[0])
    last_summary = monthly_summary(df, MONTHS[-1])
    total_net_cash_flow = sum(monthly_summary(df, month)["Net Cash Flow"] for month in MONTHS)
    savings_rate_change = last_summary["Savings Rate"] - first_summary["Savings Rate"]

    cfo_summary = (
        f"Alex generated {money(total_net_cash_flow)} of net cash flow over 3 months, "
        f"while savings rate moved from {percent(first_summary['Savings Rate'])} in January "
        f"to {percent(last_summary['Savings Rate'])} in March, a {savings_rate_change:.2f} percentage-point change. "
        f"Financial health is positive but softening because March net cash flow fell to "
        f"{money(last_summary['Net Cash Flow'])} and next-month fixed obligations are {money(fixed_obligation_total)}."
    )

    return {
        "monthly_rows": monthly_rows,
        "top_category_rows": top_category_rows,
        "subscription_rows": subscription_rows,
        "highest_unusual_month": MONTH_LABELS[highest_unusual_month],
        "highest_unusual_count": highest_unusual_count,
        "student_loan_payments": student_loan_payments,
        "ending_debt_balance": ending_debt_balance,
        "fixed_obligation_total": fixed_obligation_total,
        "cfo_summary": cfo_summary,
    }


def footer(canvas, doc):
    """Draw one-page report footer."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(doc.leftMargin, 0.35 * inch, FOOTER)
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.35 * inch, "Page 1")
    canvas.restoreState()


def build_pdf(output_path=None):
    """Build the one-page trend summary PDF."""
    pdf_path = Path(output_path) if output_path is not None else PDF_PATH
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    data = collect_trend_data()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.55 * inch,
    )

    story = [
        Paragraph("Alex Rivera - 3-Month Trend Summary Report", styles["TrendTitle"]),
        Paragraph("Quarter in Review: January-March 2026", styles["TrendSubtitle"]),
        Paragraph("Savings Rate and Net Cash Flow", styles["SectionTitle"]),
        compact_table(
            ["Month", "Savings Rate", "Trend", "Net Cash Flow"],
            data["monthly_rows"],
            styles,
            [1.1 * inch, 1.1 * inch, 0.8 * inch, 1.2 * inch],
        ),
        Spacer(1, 0.08 * inch),
        Paragraph("Top 3 Spending Categories", styles["SectionTitle"]),
        compact_table(
            ["Month", "Top Categories"],
            data["top_category_rows"],
            styles,
            [1.1 * inch, 5.8 * inch],
        ),
        Spacer(1, 0.08 * inch),
        Paragraph("Unusual Expense and Subscription Audit", styles["SectionTitle"]),
        compact_table(
            ["Metric", "Result"],
            [
                [
                    "Highest unusual expense count",
                    f"{data['highest_unusual_month']} with {data['highest_unusual_count']} unusual expense flags",
                ],
                [
                    "Subscription audit",
                    "\n".join(
                        [
                            f"{row[0]}: {row[1]} ({row[2]})"
                            for row in data["subscription_rows"]
                        ]
                    ),
                ],
                [
                    "Next-month fixed obligations",
                    money(data["fixed_obligation_total"]),
                ],
            ],
            styles,
            [2.1 * inch, 4.8 * inch],
        ),
        Spacer(1, 0.08 * inch),
        Paragraph("Debt Balance Trend", styles["SectionTitle"]),
        compact_table(
            ["Start Debt", "Visible Payments", "Ending Debt"],
            [
                [
                    money(START_DEBT_BALANCE),
                    money(data["student_loan_payments"]),
                    money(data["ending_debt_balance"]),
                ]
            ],
            styles,
            [1.7 * inch, 1.7 * inch, 1.7 * inch],
        ),
        Spacer(1, 0.08 * inch),
        Paragraph("CFO Summary", styles["SectionTitle"]),
        Paragraph(clean_text(data["cfo_summary"]), styles["BodySmall"]),
    ]

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return pdf_path


def render_pdf_for_review(pdf_path, review_dir=None):
    """Render the trend summary PDF to PNG for visual review."""
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
    """Build PDF and render a review image."""
    pdf_path = build_pdf()
    rendered_paths = render_pdf_for_review(pdf_path)
    print(f"Trend PDF generated: {pdf_path}")
    print(f"Rendered review pages: {REVIEW_DIR}")
    print(f"Page count: {len(rendered_paths)}")
    for path in rendered_paths:
        print(path)


if __name__ == "__main__":
    main()
