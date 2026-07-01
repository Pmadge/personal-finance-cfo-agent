"""Rolling forecast scenarios for the fictional starter-person CFO Agent."""

import pandas as pd

from modules.config import STARTER_PERSON_ASSETS, FIXED_OBLIGATION_CATEGORIES, FORECAST_SCENARIOS


VARIABLE_CATEGORIES = {
    "Food & Dining",
    "Transport",
    "Entertainment",
    "Shopping",
    "Medical",
    "Misc",
}


def _prepare(df):
    """Return a transaction frame with month and spend columns."""
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    working_df["month"] = working_df["date"].dt.to_period("M").astype(str)
    working_df["spend"] = working_df["amount"].abs()
    return working_df


def _monthly_income_average(df):
    income_rows = df[df["amount"] > 0]
    if "assigned_category" in df.columns:
        income_rows = income_rows[income_rows["assigned_category"] == "Income"]
    income = income_rows.groupby("month")["amount"].sum()
    return float(income.mean()) if not income.empty else 0.0


def _monthly_variable_spend_average(df):
    expenses = df[(df["amount"] < 0) & (df["assigned_category"].isin(VARIABLE_CATEGORIES))]
    monthly_spend = expenses.groupby("month")["spend"].sum()
    return float(monthly_spend.mean()) if not monthly_spend.empty else 0.0


def monthly_assumptions(df):
    """Average monthly income, fixed obligations, and variable spend from history.

    The shared baseline the runway, projection, and scenario tools all build on.
    """
    working_df = _prepare(df)
    income = _monthly_income_average(working_df)
    fixed = _monthly_fixed_obligations(working_df)
    variable = _monthly_variable_spend_average(working_df)
    total_expenses = fixed + variable
    return {
        "income": income,
        "fixed": fixed,
        "variable": variable,
        "total_expenses": total_expenses,
        "net": income - total_expenses,
    }


def _monthly_fixed_obligations(df):
    """Average monthly spend for fixed (non-discretionary) expense categories.

    Fixed obligations are derived from the expense category (Housing,
    Subscriptions, Education) rather than from a hardcoded vendor allowlist.
    This keeps rent, mortgage, and other fixed costs in the forecast for any
    person, not only the sample persona whose vendor names were special-cased.
    """
    expenses = df[
        (df["amount"] < 0)
        & (df["assigned_category"].isin(FIXED_OBLIGATION_CATEGORIES))
    ]
    monthly_spend = expenses.groupby("month")["spend"].sum()
    return float(monthly_spend.mean()) if not monthly_spend.empty else 0.0


def forecast_cash_flow(df, periods=(30, 90), starting_cash=None):
    """Return base/upside/downside cash-flow forecasts for 30 and 90 days."""
    working_df = _prepare(df)
    starting_cash = float(starting_cash if starting_cash is not None else STARTER_PERSON_ASSETS["Checking"])
    income_average = _monthly_income_average(working_df)
    variable_spend_average = _monthly_variable_spend_average(working_df)
    fixed_obligations = _monthly_fixed_obligations(working_df)

    rows = []
    for scenario, assumptions in FORECAST_SCENARIOS.items():
        for days in periods:
            months = days / 30
            income = income_average * months
            variable_spend = (
                variable_spend_average
                * (1 + assumptions["variable_spend_change"])
                * months
            )
            fixed_spend = fixed_obligations * months
            unusual_charge = assumptions["unusual_charge"]
            total_expenses = variable_spend + fixed_spend + unusual_charge
            net_cash_flow = income - total_expenses
            savings_rate = (net_cash_flow / income * 100) if income else 0.0
            ending_cash = starting_cash + net_cash_flow

            rows.append(
                {
                    "Scenario": scenario,
                    "Period Days": days,
                    "Forecast Income": round(income, 2),
                    "Fixed Obligations": round(fixed_spend, 2),
                    "Variable Spending": round(variable_spend, 2),
                    "Unusual Reserve": round(unusual_charge, 2),
                    "Net Cash Flow": round(net_cash_flow, 2),
                    "Savings Rate": round(savings_rate, 2),
                    "Ending Cash": round(ending_cash, 2),
                }
            )

    return pd.DataFrame(rows)


WEEKS_PER_MONTH = 4.345


def cash_runway(df, liquid_cash, strong_months=6.0, adequate_months=3.0):
    """How long liquid cash would last, the heart of a personal CFO view.

    Returns the emergency runway (how many months current liquid cash covers
    total monthly spending), a bare-bones runway (essential fixed bills only),
    and, when the person is currently spending more than they earn, how many
    months until cash runs out at that burn rate.
    """
    working_df = _prepare(df)
    monthly_income = _monthly_income_average(working_df)
    monthly_fixed = _monthly_fixed_obligations(working_df)
    monthly_variable = _monthly_variable_spend_average(working_df)
    monthly_total = monthly_fixed + monthly_variable
    liquid_cash = float(liquid_cash)

    full_runway = (liquid_cash / monthly_total) if monthly_total > 0 else None
    bare_runway = (liquid_cash / monthly_fixed) if monthly_fixed > 0 else None
    net = monthly_income - monthly_total
    months_until_zero = (liquid_cash / -net) if net < 0 else None

    if full_runway is None or full_runway >= strong_months:
        status = "🟢 Strong: 6+ months of expenses covered"
    elif full_runway >= adequate_months:
        status = "🟡 Adequate: 3 to 6 months of expenses covered"
    else:
        status = "🔴 Thin: under 3 months of expenses covered"

    return {
        "Liquid Cash": round(liquid_cash, 2),
        "Monthly Expenses": round(monthly_total, 2),
        "Essential Monthly Bills": round(monthly_fixed, 2),
        "Monthly Net Cash Flow": round(net, 2),
        "Emergency Runway (months)": round(full_runway, 1) if full_runway is not None else None,
        "Emergency Runway (weeks)": round(full_runway * WEEKS_PER_MONTH) if full_runway is not None else None,
        "Bare-Bones Runway (months)": round(bare_runway, 1) if bare_runway is not None else None,
        "Months Until Cash Runs Out": round(months_until_zero, 1) if months_until_zero is not None else None,
        "Status": status,
    }


def project_cash_flow(df, starting_cash, months=12, start_month=None, scenario="Base"):
    """Project month-by-month ending cash for the next N months (default 12).

    Uses average monthly income, fixed obligations, and variable spend from the
    available history, adjusted by the chosen scenario's variable-spend change.
    Shows the ending-cash trajectory so a person can see where they are heading,
    including if and when cash would go negative.
    """
    working_df = _prepare(df)
    monthly_income = _monthly_income_average(working_df)
    monthly_fixed = _monthly_fixed_obligations(working_df)
    base_variable = _monthly_variable_spend_average(working_df)
    assumptions = FORECAST_SCENARIOS.get(scenario, FORECAST_SCENARIOS["Base"])
    monthly_variable = base_variable * (1 + assumptions["variable_spend_change"])
    monthly_expenses = monthly_fixed + monthly_variable
    net = monthly_income - monthly_expenses

    if start_month is not None:
        start = pd.Period(start_month, freq="M")
    else:
        start = pd.Period(working_df["month"].max(), freq="M") + 1

    rows = []
    ending_cash = float(starting_cash)
    for offset in range(int(months)):
        period = start + offset
        ending_cash += net
        rows.append(
            {
                "Month": str(period),
                "Projected Income": round(monthly_income, 2),
                "Projected Expenses": round(monthly_expenses, 2),
                "Net Cash Flow": round(net, 2),
                "Ending Cash": round(ending_cash, 2),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["Month", "Projected Income", "Projected Expenses", "Net Cash Flow", "Ending Cash"],
    )
