"""Robustness tests across diverse personas.

These lock the fixes found by the multi-persona stress test: the forecast must
keep rent/housing in the model, debt payoff must never infinite-loop, and action
items must not crash for people who lack the starter person's specific spending categories.
"""

from pathlib import Path
import sys
import time

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.action_items import generate_action_items
from modules.forecast import forecast_cash_flow
from modules.net_worth import MAX_PAYOFF_MONTHS, debt_payoff_comparison


def _frame(rows):
    return pd.DataFrame(rows)


def _three_month(category_rows):
    """Repeat a set of (vendor, amount, assigned_category) rows across Jan-Mar."""
    rows = []
    for m in ("01", "02", "03"):
        for day, vendor, amount, category in category_rows:
            rows.append({
                "date": f"2026-{m}-{day}",
                "vendor": vendor,
                "amount": amount,
                "raw_category": category.lower(),
                "assigned_category": category,
                "classification_method": "test",
            })
    return _frame(rows)


# --- Fix 1: forecast must not silently drop rent / fixed costs ---------------

def test_forecast_includes_housing_as_fixed_obligation():
    df = _three_month([
        ("01", "Payroll", 1900.00, "Income"),
        ("03", "Anytown Apartments", -1100.00, "Housing"),
        ("08", "Corner Market", -200.00, "Food & Dining"),
    ])
    forecast = forecast_cash_flow(df, starting_cash=800)
    base_30 = forecast[(forecast["Scenario"] == "Base") & (forecast["Period Days"] == 30)].iloc[0]
    # Rent (~$1,100/month) must appear in fixed obligations, not vanish.
    assert base_30["Fixed Obligations"] >= 1000
    # And the modeled spend should roughly cover rent + groceries, not just groceries.
    modeled = base_30["Fixed Obligations"] + base_30["Variable Spending"]
    assert modeled >= 1200


# --- Fix 2: debt payoff must terminate and flag non-amortizing plans ---------

def test_debt_payoff_does_not_infinite_loop_on_high_interest_debt():
    debts = [{"name": "Card", "balance": 25000, "interest_rate": 23.0}]
    start = time.time()
    result = debt_payoff_comparison(debts, monthly_payment=300)
    assert time.time() - start < 5  # completing at all proves no infinite loop
    assert (result["Months to Payoff"] == MAX_PAYOFF_MONTHS).all()
    assert result["Recommended Method"].iloc[0] == "Increase Payment"
    assert "does not amortize" in result["Recommendation Explanation"].iloc[0]


def test_debt_payoff_still_amortizes_with_sufficient_payment():
    debts = [{"name": "Card", "balance": 1000, "interest_rate": 12.0}]
    result = debt_payoff_comparison(debts, monthly_payment=300)
    assert (result["Months to Payoff"] < MAX_PAYOFF_MONTHS).all()
    assert (result["Months to Payoff"] > 0).all()


# --- Fix 3: action items must not crash for non-starter-person spending shapes ---------

def test_action_items_no_crash_without_shopping_category():
    df = _three_month([
        ("01", "Payroll", 3000.00, "Income"),
        ("03", "Rent Co", -1400.00, "Housing"),
        ("08", "Big Grocer", -500.00, "Food & Dining"),  # over the $300 food budget
    ])
    budget = {"Housing": 1400, "Food": 300, "Misc": 50}
    actions = generate_action_items(df, "2026-03", budget)
    assert actions.empty or set(actions["Evaluation"]) == {"PASS"}
    joined = " ".join(actions["Action Item"]) if not actions.empty else ""
    # Must never inject the sample persona's hardcoded fallback vendors.
    assert "Gap Flagship Store" not in joined
    assert "Verizon" not in joined
    # The real food overage should surface.
    assert actions.empty or actions["Action Item"].str.contains("Food & Dining").any()


def test_action_items_empty_when_everything_within_budget():
    df = _three_month([
        ("01", "Payroll", 3000.00, "Income"),
        ("03", "Rent Co", -1400.00, "Housing"),
    ])
    budget = {"Housing": 1400, "Misc": 50}
    actions = generate_action_items(df, "2026-03", budget)
    assert actions.empty  # nothing over budget => no invented action items, no crash


def test_categorizer_handles_common_real_world_vendors():
    """Realistic merchants should categorize, not fall into Misc (foundation fix)."""
    from modules.categorizer import categorize_transaction

    cases = [
        ("Costco Wholesale #123", -200.0, "Food & Dining"),
        ("Kroger", -80.0, "Food & Dining"),
        ("Starbucks Store 555", -6.25, "Food & Dining"),
        ("Shell Oil Gas Station", -50.0, "Transport"),
        ("Chevron 0421", -45.0, "Transport"),
        ("Amazon Marketplace", -60.0, "Shopping"),
        ("Home Depot", -130.0, "Shopping"),
        ("CVS Pharmacy", -20.0, "Medical"),
        ("Comcast Xfinity", -90.0, "Subscriptions"),
        ("Geico Insurance", -120.0, "Subscriptions"),
        ("Wells Fargo Mortgage", -1800.0, "Housing"),
        ("Vanguard Brokerage", -500.0, "Savings Transfer"),
        ("AMC Theatres 16", -30.0, "Entertainment"),
        ("ACME Payroll Direct Deposit", 3000.0, "Income"),
    ]
    misclassified = []
    for vendor, amount, expected in cases:
        result = categorize_transaction({"vendor": vendor, "amount": amount})
        if result["assigned_category"] != expected:
            misclassified.append((vendor, result["assigned_category"], expected))
    assert not misclassified, misclassified

    misc = sum(
        categorize_transaction({"vendor": v, "amount": a})["assigned_category"] == "Misc"
        for v, a, _ in cases
    )
    assert misc == 0


def test_action_items_handle_zero_income_without_divide_by_zero():
    import warnings

    rows = []
    for m in ("01", "02", "03"):
        rows += [
            {"date": f"2026-{m}-03", "vendor": "Riverside Rent", "amount": -1000.0,
             "raw_category": "rent", "assigned_category": "Housing", "classification_method": "test"},
            {"date": f"2026-{m}-10", "vendor": "Big Grocer", "amount": -500.0,
             "raw_category": "groceries", "assigned_category": "Food & Dining", "classification_method": "test"},
        ]
    budget = {"Housing": 1000, "Food": 300}  # food over budget while income is $0
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a divide-by-zero RuntimeWarning would raise here
        actions = generate_action_items(_frame(rows), "2026-03", budget)
    assert actions.empty or set(actions["Evaluation"]) == {"PASS"}


def test_refund_is_not_categorized_as_income():
    from modules.categorizer import classify

    refund_category, _ = classify("Refund - Local Shop", 50.0)
    assert refund_category != "Income"

    income_category, _ = classify("ACME Payroll Deposit", 3000.0)
    assert income_category == "Income"


def test_refund_excluded_from_income_and_nets_against_spend(tmp_path):
    from modules.categorizer import categorize_file
    from modules.analytics import budget_vs_actual, monthly_summary

    rows = [
        {"date": "2026-03-01", "vendor": "Payroll Deposit", "amount": 3000.0, "raw_category": "income"},
        {"date": "2026-03-03", "vendor": "Riverside Rent", "amount": -1200.0, "raw_category": "rent"},
        {"date": "2026-03-10", "vendor": "Target", "amount": -300.0, "raw_category": "shopping"},
        {"date": "2026-03-15", "vendor": "Refund - Target", "amount": 120.0, "raw_category": "refund"},
    ]
    src = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    df, _ = categorize_file(src, out)

    summary = monthly_summary(df, "2026-03")
    assert summary["Income"] == 3000.00  # refund must NOT inflate income

    budget = budget_vs_actual(df, "2026-03", {"Shopping": 250})
    shopping = budget[budget["Category"] == "Shopping"].iloc[0]
    assert shopping["Actual Amount"] == 180.00  # 300 spent minus 120 refunded


def test_action_items_owner_is_configurable():
    df = _three_month([
        ("01", "Payroll", 3000.00, "Income"),
        ("03", "Rent Co", -1400.00, "Housing"),
        ("08", "Big Grocer", -500.00, "Food & Dining"),
    ])
    budget = {"Housing": 1400, "Food": 300}
    actions = generate_action_items(df, "2026-03", budget, owner="Maya Chen")
    assert actions.empty or actions["Owner"].eq("Maya Chen").all()
