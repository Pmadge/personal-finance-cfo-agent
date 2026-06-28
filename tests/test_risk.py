"""Tests for the personal risk register."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.risk import HIGH, LOW, MEDIUM, build_risk_register, risk_summary


def _frame(rows):
    out = []
    for m in ("01", "02", "03"):
        for day, vendor, amount, category in rows:
            out.append({
                "date": f"2026-{m}-{day}", "vendor": vendor, "amount": amount,
                "raw_category": category.lower(), "assigned_category": category,
                "classification_method": "t",
            })
    return pd.DataFrame(out)


HEALTHY = [
    ("01", "Payroll", 5000.0, "Income"),
    ("03", "Rent", -1200.0, "Housing"),       # 24% of income
    ("06", "Geico Insurance", -120.0, "Subscriptions"),
    ("10", "Groceries", -400.0, "Food & Dining"),
]
STRESSED = [
    ("01", "Payroll", 3000.0, "Income"),
    ("03", "Rent", -1400.0, "Housing"),       # 47% of income -> high burden
    ("10", "Groceries", -900.0, "Food & Dining"),
    ("18", "Shopping", -900.0, "Shopping"),   # overspending -> negative net
]


def _level(register, risk):
    return register[register["Risk"] == risk]["Level"].iloc[0]


def test_healthy_profile_is_mostly_low_risk():
    register = build_risk_register(
        _frame(HEALTHY),
        assets={"Checking": 5000, "Savings": 15000, "Investments": 0},
        liabilities={},
    )
    assert _level(register, "Cash Flow") == LOW
    assert _level(register, "Housing Cost Burden") == LOW  # 24% of income
    assert _level(register, "Insurance Coverage") == LOW   # Geico detected
    counts, _ = risk_summary(register)
    assert counts["High"] == 0


def test_stressed_profile_flags_high_risks():
    register = build_risk_register(
        _frame(STRESSED),
        assets={"Checking": 300, "Savings": 0, "Investments": 0},
        liabilities={"Credit Card": {"balance": 25000, "interest_rate": 23.0}},
    )
    assert _level(register, "Cash Flow") == HIGH             # spends more than earns
    assert _level(register, "Housing Cost Burden") == HIGH   # 47% of income
    assert _level(register, "Emergency Fund") == HIGH        # ~0 months runway
    assert _level(register, "Debt Load") in (HIGH, MEDIUM)   # underwater + high interest
    assert _level(register, "Insurance Coverage") == MEDIUM  # none detected
    counts, overall = risk_summary(register)
    assert counts["High"] >= 3
    assert "Attention needed" in overall


def test_single_income_source_flags_concentration():
    register = build_risk_register(
        _frame(HEALTHY),  # only one income vendor (Payroll)
        assets={"Checking": 20000, "Savings": 0, "Investments": 0},
        liabilities={},
    )
    assert _level(register, "Income Concentration") == MEDIUM


def test_high_interest_debt_is_flagged_even_when_assets_cover_it():
    register = build_risk_register(
        _frame(HEALTHY),
        assets={"Checking": 50000, "Savings": 50000, "Investments": 0},  # debt-to-asset low
        liabilities={"Credit Card": {"balance": 4000, "interest_rate": 22.0}},
    )
    assert _level(register, "Debt Load") == MEDIUM
    finding = register[register["Risk"] == "Debt Load"]["Finding"].iloc[0]
    assert "High-interest debt" in finding


def test_register_has_all_six_risks():
    register = build_risk_register(
        _frame(HEALTHY), assets={"Checking": 5000, "Savings": 5000, "Investments": 0}, liabilities={}
    )
    assert len(register) == 6
    assert set(register["Risk"]) == {
        "Emergency Fund", "Income Concentration", "Debt Load",
        "Cash Flow", "Housing Cost Burden", "Insurance Coverage",
    }
