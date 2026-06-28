"""What-if scenario planning for the personal CFO Agent.

A scenario flexes the baseline monthly picture (income, expenses, liquid cash)
and shows how a life change would move the numbers: monthly net cash flow, how
long cash would last, projected cash a year out, and whether the change creates a
cash-out risk. Built on the same monthly assumptions the runway and projection use.

A scenario is a dict with a name and any of these optional adjustments:
- monthly_income:        set monthly income to this absolute amount (e.g. 0 for job loss)
- monthly_income_change: add/subtract this much monthly income (e.g. +500 raise)
- monthly_expense_change: add/subtract this much recurring monthly expense (e.g. +400 rent)
- variable_spend_pct:    scale variable spending (e.g. -0.20 to cut discretionary 20%)
- one_time_cost:         an immediate one-off hit to liquid cash (e.g. 5000 purchase)
"""

import math

import pandas as pd

from modules.forecast import monthly_assumptions


def _adjust(baseline, scenario):
    """Apply a scenario's adjustments to the baseline monthly assumptions."""
    if "monthly_income" in scenario:
        income = float(scenario["monthly_income"])
    else:
        income = baseline["income"] + float(scenario.get("monthly_income_change", 0.0))
    fixed = baseline["fixed"] + float(scenario.get("monthly_expense_change", 0.0))
    variable = baseline["variable"] * (1 + float(scenario.get("variable_spend_pct", 0.0)))
    total_expenses = max(fixed + variable, 0.0)
    return {
        "income": income,
        "fixed": fixed,
        "variable": variable,
        "total_expenses": total_expenses,
        "net": income - total_expenses,
    }


def _months_until_zero(starting_cash, net):
    """Whole months until cash hits zero (0 = already short, None = not declining)."""
    if starting_cash <= 0:
        return 0  # cash is already negative right now (e.g. an unaffordable purchase)
    if net >= 0:
        return None
    return math.ceil(starting_cash / -net)


def _runway_months(starting_cash, total_expenses):
    """Months of buffer; 0 when cash is already negative, None when no expenses."""
    if total_expenses <= 0:
        return None
    if starting_cash <= 0:
        return 0.0
    return starting_cash / total_expenses


def run_scenario(df, liquid_cash, scenario, months=12):
    """Return the adjusted monthly picture, runway, and projection for one scenario."""
    baseline = monthly_assumptions(df)
    adjusted = _adjust(baseline, scenario)
    starting_cash = float(liquid_cash) - float(scenario.get("one_time_cost", 0.0))
    net = adjusted["net"]

    runway_months = _runway_months(starting_cash, adjusted["total_expenses"])
    cash_in_horizon = starting_cash + net * months
    cash_out_month = _months_until_zero(starting_cash, net)

    return {
        "name": scenario.get("name", "Scenario"),
        "monthly_income": round(adjusted["income"], 2),
        "monthly_expenses": round(adjusted["total_expenses"], 2),
        "monthly_net": round(net, 2),
        "starting_cash": round(starting_cash, 2),
        "runway_months": round(runway_months, 1) if runway_months is not None else None,
        "cash_in_horizon": round(cash_in_horizon, 2),
        "cash_out_month": cash_out_month,
    }


def compare_scenarios(df, liquid_cash, scenarios, months=12):
    """Build a side-by-side table comparing each scenario to today's baseline."""
    baseline = monthly_assumptions(df)
    rows = [_summary_row("Baseline (today)", baseline, float(liquid_cash), months)]
    for scenario in scenarios:
        adjusted = _adjust(baseline, scenario)
        starting_cash = float(liquid_cash) - float(scenario.get("one_time_cost", 0.0))
        rows.append(_summary_row(scenario.get("name", "Scenario"), adjusted, starting_cash, months))
    columns = [
        "Scenario", "Monthly Income", "Monthly Expenses", "Net Cash Flow",
        "Runway (months)", "Cash in 12 Months", "Cash-Out Risk",
    ]
    return pd.DataFrame(rows, columns=columns)


def _summary_row(name, assumptions, starting_cash, months):
    """One comparison-table row for a baseline or adjusted monthly picture."""
    net = assumptions["net"]
    total_expenses = assumptions["total_expenses"]
    runway_months = _runway_months(starting_cash, total_expenses)
    cash_out_month = _months_until_zero(starting_cash, net)
    if cash_out_month is None:
        cash_out_risk = "None"
    elif cash_out_month == 0:
        cash_out_risk = "Immediate shortfall"
    elif cash_out_month <= months:
        cash_out_risk = f"Runs out in ~{cash_out_month} months"
    else:
        cash_out_risk = f"Declining (~{cash_out_month} months out)"
    return {
        "Scenario": name,
        "Monthly Income": round(assumptions["income"], 2),
        "Monthly Expenses": round(total_expenses, 2),
        "Net Cash Flow": round(net, 2),
        "Runway (months)": round(runway_months, 1) if runway_months is not None else None,
        "Cash in 12 Months": round(starting_cash + net * months, 2),
        "Cash-Out Risk": cash_out_risk,
    }
