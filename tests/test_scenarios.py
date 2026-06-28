"""Tests for what-if scenario planning."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.scenarios import compare_scenarios, run_scenario


def _history():
    # earns 4000/mo, spends 1400 rent + 100 subs + 500 food = 2000 -> net +2000
    rows = []
    for m in ("01", "02", "03"):
        rows += [
            {"date": f"2026-{m}-01", "vendor": "Payroll", "amount": 4000.0,
             "raw_category": "income", "assigned_category": "Income", "classification_method": "t"},
            {"date": f"2026-{m}-03", "vendor": "Rent", "amount": -1400.0,
             "raw_category": "rent", "assigned_category": "Housing", "classification_method": "t"},
            {"date": f"2026-{m}-06", "vendor": "Netflix", "amount": -100.0,
             "raw_category": "subscription", "assigned_category": "Subscriptions", "classification_method": "t"},
            {"date": f"2026-{m}-10", "vendor": "Groceries", "amount": -500.0,
             "raw_category": "groceries", "assigned_category": "Food & Dining", "classification_method": "t"},
        ]
    return pd.DataFrame(rows)


def test_job_loss_creates_cash_out_risk():
    result = run_scenario(_history(), liquid_cash=8000.0, scenario={"name": "Job loss", "monthly_income": 0.0})
    assert result["monthly_income"] == 0.0
    assert result["monthly_net"] == -2000.0  # still owes 2000/mo of expenses
    # 8000 cash / 2000 burn = 4 months
    assert result["cash_out_month"] == 4
    assert result["runway_months"] == 4.0


def test_raise_improves_net_and_no_cash_out():
    result = run_scenario(_history(), liquid_cash=8000.0, scenario={"name": "Raise", "monthly_income_change": 500.0})
    assert result["monthly_net"] == 2500.0
    assert result["cash_out_month"] is None


def test_one_time_cost_reduces_starting_cash():
    result = run_scenario(_history(), liquid_cash=8000.0, scenario={"name": "Purchase", "one_time_cost": 5000.0})
    assert result["starting_cash"] == 3000.0


def test_variable_spend_cut_lowers_expenses():
    base = run_scenario(_history(), liquid_cash=8000.0, scenario={"name": "Base"})
    cut = run_scenario(_history(), liquid_cash=8000.0, scenario={"name": "Cut 20%", "variable_spend_pct": -0.20})
    # only the 500 food is variable; 20% cut = 100 less expense
    assert round(base["monthly_expenses"] - cut["monthly_expenses"], 2) == 100.0


def test_compare_scenarios_includes_baseline_first():
    scenarios = [
        {"name": "Job loss", "monthly_income": 0.0},
        {"name": "Raise", "monthly_income_change": 500.0},
    ]
    table = compare_scenarios(_history(), liquid_cash=8000.0, scenarios=scenarios)
    assert list(table["Scenario"])[0] == "Baseline (today)"
    assert len(table) == 3
    job_loss = table[table["Scenario"] == "Job loss"].iloc[0]
    assert "Runs out" in job_loss["Cash-Out Risk"]
    baseline = table.iloc[0]
    assert baseline["Cash-Out Risk"] == "None"
