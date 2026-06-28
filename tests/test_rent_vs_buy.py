"""Tests for the rent-vs-buy capital-event analysis."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.capital_events import _remaining_loan_balance, rent_vs_buy


def _housing_frame(monthly_rent):
    rows = []
    for m in ("01", "02", "03"):
        rows += [
            {"date": f"2026-{m}-01", "vendor": "Payroll", "amount": 5000.0,
             "raw_category": "income", "assigned_category": "Income", "classification_method": "t"},
            {"date": f"2026-{m}-03", "vendor": "Rent", "amount": -monthly_rent,
             "raw_category": "rent", "assigned_category": "Housing", "classification_method": "t"},
        ]
    return pd.DataFrame(rows)


def test_remaining_balance_starts_at_loan_and_ends_near_zero():
    assert round(_remaining_loan_balance(200000, 6.0, 30, 0), 2) == 200000.0
    assert _remaining_loan_balance(200000, 6.0, 30, 360) < 1.0  # paid off after the full term


def test_high_rent_makes_buying_cheaper():
    # Pays $4,000/mo rent; buying a modestly priced home should win over 5 years.
    result = rent_vs_buy(_housing_frame(4000.0), home_price=300000, horizon_years=5)
    assert result["cheaper"] == "Buying"
    assert result["current_monthly_rent"] == 4000.0
    assert result["buy_net_cost"] < result["rent_net_cost"]


def test_low_rent_makes_renting_cheaper():
    # Cheap rent vs an expensive home -> renting wins over a short horizon.
    result = rent_vs_buy(_housing_frame(900.0), home_price=600000, horizon_years=5)
    assert result["cheaper"] == "Renting"


def test_uses_explicit_rent_when_provided():
    result = rent_vs_buy(_housing_frame(1000.0), home_price=300000, current_monthly_rent=2500.0)
    assert result["current_monthly_rent"] == 2500.0


def test_handles_no_housing_gracefully():
    income_only = pd.DataFrame([{
        "date": "2026-03-01", "vendor": "Payroll", "amount": 5000.0,
        "raw_category": "income", "assigned_category": "Income", "classification_method": "t",
    }])
    result = rent_vs_buy(income_only, home_price=300000)
    assert result["cheaper"] == "Unknown"
    assert "not meaningful" in result["recommendation"]
