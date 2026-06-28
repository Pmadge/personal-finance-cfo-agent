"""Tests for cash runway and the 12-month cash projection."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.forecast import cash_runway, project_cash_flow


def _three_month(rows_per_month):
    rows = []
    for m in ("01", "02", "03"):
        for day, vendor, amount, category in rows_per_month:
            rows.append({
                "date": f"2026-{m}-{day}", "vendor": vendor, "amount": amount,
                "raw_category": category.lower(), "assigned_category": category,
                "classification_method": "test",
            })
    return pd.DataFrame(rows)


SAVER = [  # earns 3000, spends 2000/mo -> positive net
    ("01", "Payroll", 3000.0, "Income"),
    ("03", "Rent", -1400.0, "Housing"),
    ("06", "Netflix", -100.0, "Subscriptions"),
    ("10", "Groceries", -500.0, "Food & Dining"),
]
OVERSPENDER = [  # earns 3000, spends ~3600/mo -> negative net
    ("01", "Payroll", 3000.0, "Income"),
    ("03", "Rent", -1800.0, "Housing"),
    ("06", "Netflix", -100.0, "Subscriptions"),
    ("10", "Groceries", -900.0, "Food & Dining"),
    ("18", "Shopping", -800.0, "Shopping"),
]


def test_cash_runway_reports_months_and_weeks_of_buffer():
    runway = cash_runway(_three_month(SAVER), liquid_cash=12000.0)
    # 12000 / 2000 monthly expenses = 6 months
    assert runway["Monthly Expenses"] == 2000.0
    assert runway["Emergency Runway (months)"] == 6.0
    assert runway["Emergency Runway (weeks)"] == round(6 * 4.345)
    assert runway["Status"].startswith("🟢 Strong")
    # positive saver is not running out of cash
    assert runway["Months Until Cash Runs Out"] is None


def test_cash_runway_flags_thin_buffer():
    runway = cash_runway(_three_month(SAVER), liquid_cash=3000.0)  # 1.5 months
    assert runway["Emergency Runway (months)"] == 1.5
    assert runway["Status"].startswith("🔴 Thin")


def test_cash_runway_reports_depletion_when_overspending():
    runway = cash_runway(_three_month(OVERSPENDER), liquid_cash=6000.0)
    assert runway["Monthly Net Cash Flow"] < 0
    # burning ~600/mo on 6000 cash -> ~10 months to zero
    assert runway["Months Until Cash Runs Out"] is not None
    assert runway["Months Until Cash Runs Out"] > 0


def test_cash_runway_handles_no_expenses():
    income_only = pd.DataFrame([{
        "date": "2026-03-01", "vendor": "Payroll", "amount": 3000.0,
        "raw_category": "income", "assigned_category": "Income", "classification_method": "test",
    }])
    runway = cash_runway(income_only, liquid_cash=5000.0)
    assert runway["Emergency Runway (months)"] is None  # no recurring expenses
    assert runway["Status"].startswith("🟢 Strong")


def test_projection_returns_twelve_months_with_running_ending_cash():
    projection = project_cash_flow(_three_month(SAVER), starting_cash=5000.0, months=12, start_month="2026-04")
    assert len(projection) == 12
    assert list(projection["Month"])[0] == "2026-04"
    assert list(projection["Month"])[-1] == "2027-03"
    net = projection["Net Cash Flow"].iloc[0]
    # ending cash should be starting + net * 12 at the final month
    assert round(projection["Ending Cash"].iloc[-1], 2) == round(5000.0 + net * 12, 2)


def test_projection_shows_cash_going_negative_for_overspender():
    projection = project_cash_flow(_three_month(OVERSPENDER), starting_cash=2000.0, months=12, start_month="2026-04")
    assert (projection["Ending Cash"] < 0).any()  # overspending depletes the cash
