"""Automated QA checks for the fictional Alex Rivera CFO Agent."""

from pathlib import Path
import sys

import fitz
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.action_items import generate_action_items
from modules.analytics import budget_vs_actual, monthly_summary, upcoming_obligations
from modules.categorizer import calculate_accuracy
from modules.config import ALEX_ASSETS, ALEX_BUDGET, ALEX_LIABILITIES
from modules.detectors import detect_unusual
from modules.forecast import forecast_cash_flow
from modules.net_worth import debt_payoff_comparison, net_worth_snapshot
from modules.reports.pdf_report import main as generate_monthly_pdf
from modules.reports.trend_report import main as generate_trend_pdf


def load_categorized():
    return pd.read_csv(PROJECT_ROOT / "data" / "alex_rivera_transactions_categorized.csv")


def test_categorization_accuracy_is_above_target():
    df = load_categorized()
    assert calculate_accuracy(df) >= 85


def test_month_2_savings_rate_matches_manual_check():
    df = load_categorized()
    summary = monthly_summary(df, "2026-02")
    assert summary["Income"] == 4860.00
    assert summary["Total Expenses"] == 2449.18
    assert summary["Savings Rate"] == 49.61


def test_month_1_food_variance_matches_manual_check():
    df = load_categorized()
    food_row = budget_vs_actual(df, "2026-01", ALEX_BUDGET)
    food_row = food_row[food_row["Category"] == "Food & Dining"].iloc[0]
    assert food_row["Actual Amount"] == 722.59
    assert food_row["Variance ($)"] == -472.59
    assert food_row["Variance (%)"] == -189.04


def test_fixed_obligations_exclude_discretionary_repeat_vendors():
    df = load_categorized()
    obligations = upcoming_obligations(df)
    vendors = set(obligations["Vendor"])
    assert "Parkside Rent Portal" in vendors
    assert "Federal Student Loan Servicer" in vendors
    assert "Blue Bottle Coffee" not in vendors
    assert "Chipotle" not in vendors
    assert "Safeway" not in vendors
    assert "Target" not in vendors


def test_unusual_flags_are_high_signal():
    df = load_categorized()
    unusual = detect_unusual(df)
    vendors = set(unusual["Vendor"])
    assert "Gap Flagship Store" in vendors
    assert "Dentist Copay" in vendors
    assert "Auto Registration Renewal" in vendors
    assert "Verizon Wireless" not in vendors
    assert "Whole Foods Market" not in vendors


def test_400_coffee_test_charge_fires_without_changing_source_data():
    df = load_categorized()
    test_row = {
        "date": "2026-03-20",
        "vendor": "Blue Bottle Coffee",
        "amount": -400.00,
        "raw_category": "dining",
        "assigned_category": "Food & Dining",
        "classification_method": "test_in_memory",
    }
    test_df = pd.concat([df, pd.DataFrame([test_row])], ignore_index=True)
    unusual = detect_unusual(test_df)
    flag = unusual[unusual["Vendor"] == "Blue Bottle Coffee"]["Flag Message"].iloc[-1]
    assert "Blue Bottle Coffee charge of $400.00" in flag
    assert len(load_categorized()) == len(df)


def test_action_items_pass_required_format():
    df = load_categorized()
    actions = generate_action_items(df, "2026-02", ALEX_BUDGET)
    assert len(actions) == 3
    assert set(actions["Evaluation"]) == {"PASS"}
    assert actions["Owner"].eq("Alex Rivera").all()


def test_net_worth_and_debt_payoff_math():
    snapshot = net_worth_snapshot(ALEX_ASSETS, ALEX_LIABILITIES)
    assert snapshot["Net Worth"] == -19900.00
    debts = [
        {"name": name, "balance": details["balance"], "interest_rate": details["interest_rate"]}
        for name, details in ALEX_LIABILITIES.items()
    ]
    payoff = debt_payoff_comparison(debts)
    assert payoff["Total Interest Paid"].round(2).tolist() == [6437.95, 6437.95]
    assert payoff["Months to Payoff"].tolist() == [104, 104]


def test_forecast_returns_three_scenarios_for_30_and_90_days():
    df = load_categorized()
    forecast = forecast_cash_flow(df)
    assert set(forecast["Scenario"]) == {"Upside", "Base", "Downside"}
    assert set(forecast["Period Days"]) == {30, 90}


def test_monthly_pdf_contains_required_sections():
    generate_monthly_pdf()
    pdf_path = PROJECT_ROOT / "outputs" / "alex_rivera_monthly_cfo_report_2026_03.pdf"
    document = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in document)
    document.close()
    required_sections = [
        "Executive Summary",
        "CFO Commentary",
        "Outcomes Scorecard",
        "Cash Flow Overview",
        "Cash Runway",
        "12-Month Cash Projection",
        "What-If Scenarios",
        "Budget vs. Actual",
        "Spending by Category",
        "Savings Rate Trend",
        "Month-over-Month",
        "Recurring Vendor Tracker",
        "Unusual Expense Flags",
        "Upcoming Obligations",
        "Net Worth Snapshot",
        "Debt Payoff Analysis",
        "Goal Tracker",
        "Risk Register",
        "Capital Event: Home Purchase Readiness",
        "Rent vs Buy",
        "AI Action Items",
        "Your CFO Engagement",
        "Model Version Log",
    ]
    for section in required_sections:
        assert section in text


def test_trend_pdf_is_one_page():
    generate_trend_pdf()
    pdf_path = PROJECT_ROOT / "outputs" / "alex_rivera_3_month_trend_summary_2026_q1.pdf"
    document = fitz.open(pdf_path)
    page_count = document.page_count
    document.close()
    assert page_count == 1
