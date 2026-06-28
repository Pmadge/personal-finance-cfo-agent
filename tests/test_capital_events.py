"""Tests for capital-event playbooks (home purchase, major purchase)."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.capital_events import (
    CLOSE, NOT_YET, READY, _mortgage_payment, home_purchase_readiness, major_purchase_check,
)


def _frame(monthly_income, monthly_expense):
    rows = []
    for m in ("01", "02", "03"):
        rows += [
            {"date": f"2026-{m}-01", "vendor": "Payroll", "amount": monthly_income,
             "raw_category": "income", "assigned_category": "Income", "classification_method": "t"},
            {"date": f"2026-{m}-03", "vendor": "Rent", "amount": -monthly_expense,
             "raw_category": "rent", "assigned_category": "Housing", "classification_method": "t"},
        ]
    return pd.DataFrame(rows)


def test_mortgage_payment_matches_known_amortization():
    # $300,000 at 6% for 30 years is about $1,798.65/mo principal+interest.
    payment = _mortgage_payment(300000, 6.0, 30)
    assert abs(payment - 1798.65) < 1.0


def test_mortgage_payment_handles_zero_rate():
    assert round(_mortgage_payment(120000, 0.0, 10), 2) == 1000.0  # 120000 / 120 months


def test_home_readiness_not_yet_for_thin_savings():
    df = _frame(monthly_income=5000.0, monthly_expense=1500.0)
    result = home_purchase_readiness(df, assets={"Checking": 2000, "Savings": 4000}, home_price=350000)
    # 20% down on 350k is 70k + closing; 6k cash cannot cover it
    assert result["verdict"] == NOT_YET
    assert result["cash_after_purchase"] < 0
    assert any("Short" in g for g in result["gaps"])


def test_home_readiness_ready_for_strong_buyer():
    df = _frame(monthly_income=12000.0, monthly_expense=2000.0)
    result = home_purchase_readiness(
        df, assets={"Checking": 50000, "Savings": 80000}, home_price=300000
    )
    assert result["verdict"] == READY
    assert result["payment_to_income"] <= 28
    assert not result["gaps"]


def test_major_purchase_affordable_but_thins_runway():
    df = _frame(monthly_income=4000.0, monthly_expense=2000.0)
    # 5000 cash, buy 4000 -> 1000 left -> 0.5 months runway (below 3)
    result = major_purchase_check(df, assets={"Checking": 5000, "Savings": 0}, amount=4000)
    assert result["verdict"] == CLOSE
    assert result["cash_after"] == 1000.0


def test_major_purchase_not_affordable():
    df = _frame(monthly_income=4000.0, monthly_expense=2000.0)
    result = major_purchase_check(df, assets={"Checking": 1000, "Savings": 0}, amount=4000)
    assert result["verdict"] == NOT_YET
    assert result["cash_after"] < 0
