"""Personal risk register for the CFO Agent.

The "risk and controls" view adapted for an individual: one place that asks what
could go wrong. It pulls signals the other tools already compute (cash runway,
monthly assumptions, net worth) plus a few transaction-derived checks, and rates
each risk Low / Medium / High with a plain-language finding and recommendation.
"""

import pandas as pd

from modules.forecast import cash_runway, monthly_assumptions
from modules.net_worth import net_worth_snapshot

HIGH = "🔴 High"
MEDIUM = "🟡 Medium"
LOW = "🟢 Low"

HIGH_INTEREST_RATE = 15.0  # APR at or above this is treated as high-interest debt
HOUSING_BURDEN_HIGH = 0.35
HOUSING_BURDEN_MEDIUM = 0.28
INSURANCE_SIGNALS = ("INSURANCE", "GEICO", "STATE FARM", "PROGRESSIVE", "ALLSTATE", "ALLSTATE")


def _money(amount):
    return f"${float(amount):,.2f}"


def _income_concentration(df):
    """Share of income from the single largest income source (None if no income)."""
    income_rows = df[df["amount"] > 0]
    if "assigned_category" in df.columns:
        income_rows = income_rows[income_rows["assigned_category"] == "Income"]
    total = float(income_rows["amount"].sum())
    if total <= 0:
        return None
    by_vendor = income_rows.groupby("vendor")["amount"].sum()
    return float(by_vendor.max() / total)


def _monthly_housing(df):
    """Average monthly Housing spend, for the housing-cost-burden check."""
    if "assigned_category" not in df.columns:
        return 0.0
    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working["month"] = working["date"].dt.to_period("M").astype(str)
    housing = working[(working["amount"] < 0) & (working["assigned_category"] == "Housing")]
    if housing.empty:
        return 0.0
    monthly = housing.assign(spend=housing["amount"].abs()).groupby("month")["spend"].sum()
    return float(monthly.mean())


def _has_insurance(df):
    vendors = df["vendor"].astype(str).str.upper()
    return bool(vendors.apply(lambda v: any(sig in v for sig in INSURANCE_SIGNALS)).any())


def _row(risk, level, finding, recommendation):
    return {"Risk": risk, "Level": level, "Finding": finding, "Recommendation": recommendation}


def build_risk_register(df, assets, liabilities, liquid_cash=None):
    """Return a risk-register DataFrame: Risk, Level, Finding, Recommendation."""
    assumptions = monthly_assumptions(df)
    income = assumptions["income"]
    net = assumptions["net"]
    if liquid_cash is None:
        liquid_cash = float(assets.get("Checking", 0.0)) + float(assets.get("Savings", 0.0))
    runway = cash_runway(df, liquid_cash)
    net_worth = net_worth_snapshot(assets, liabilities)
    savings_rate = (net / income * 100) if income else 0.0

    rows = []

    # 1. Emergency fund adequacy (from cash runway).
    runway_months = runway["Emergency Runway (months)"]
    if runway_months is None or runway_months >= 6:
        rows.append(_row(
            "Emergency Fund", LOW,
            f"Liquid cash covers {runway_months if runway_months is not None else '6+'} months of expenses.",
            "Maintain at least 3 to 6 months of expenses in liquid savings.",
        ))
    elif runway_months >= 3:
        rows.append(_row(
            "Emergency Fund", MEDIUM,
            f"Liquid cash covers {runway_months} months of expenses (target 3 to 6).",
            "Build the cushion toward 6 months of expenses.",
        ))
    else:
        rows.append(_row(
            "Emergency Fund", HIGH,
            f"Liquid cash covers only {runway_months} months of expenses (target 3 to 6).",
            "Prioritize building an emergency fund before new discretionary spending.",
        ))

    # 2. Income concentration.
    concentration = _income_concentration(df)
    if concentration is None:
        rows.append(_row(
            "Income Concentration", HIGH,
            "No income detected in the period.",
            "Establish a reliable income source.",
        ))
    elif concentration >= 0.90:
        rows.append(_row(
            "Income Concentration", MEDIUM,
            f"About {concentration * 100:.0f}% of income comes from a single source.",
            "A single income source raises job-loss risk; keep a strong emergency fund and consider diversifying.",
        ))
    else:
        rows.append(_row(
            "Income Concentration", LOW,
            f"Income is spread across sources (largest is {concentration * 100:.0f}%).",
            "Diversified income lowers job-loss risk.",
        ))

    # 3. Debt load (debt-to-asset plus high-interest debt).
    debt_to_asset = net_worth["Debt-to-Asset Ratio"]
    high_interest = [
        name for name, debt in liabilities.items()
        if isinstance(debt, dict) and float(debt.get("interest_rate", 0)) >= HIGH_INTEREST_RATE
        and float(debt.get("balance", 0)) > 0
    ]
    if debt_to_asset > 100:
        level = HIGH
    elif debt_to_asset >= 50 or high_interest:
        level = MEDIUM
    else:
        level = LOW
    finding = f"Debt is {debt_to_asset:.0f}% of assets."
    if high_interest:
        finding += f" High-interest debt: {', '.join(high_interest)}."
    rows.append(_row(
        "Debt Load", level, finding,
        "Pay down high-interest debt first and keep total debt well below assets."
        if level != LOW else "Debt level is manageable relative to assets.",
    ))

    # 4. Cash flow health.
    if net < 0:
        rows.append(_row(
            "Cash Flow", HIGH,
            f"Spending exceeds income by {_money(-net)} per month.",
            "Cut expenses or raise income; ongoing negative cash flow depletes savings.",
        ))
    elif savings_rate < 10:
        rows.append(_row(
            "Cash Flow", MEDIUM,
            f"Savings rate is {savings_rate:.1f}% (below the 10% target).",
            "Trim discretionary spending to lift the savings rate toward 10%+.",
        ))
    else:
        rows.append(_row(
            "Cash Flow", LOW,
            f"Positive cash flow with a {savings_rate:.1f}% savings rate.",
            "Keep directing the surplus to goals and the emergency fund.",
        ))

    # 5. Housing cost burden (the ~30% rule).
    housing = _monthly_housing(df)
    if income <= 0:
        rows.append(_row(
            "Housing Cost Burden", MEDIUM,
            "No income to compare housing cost against.",
            "Re-check once income is recorded.",
        ))
    else:
        burden = housing / income
        if burden > HOUSING_BURDEN_HIGH:
            level = HIGH
        elif burden >= HOUSING_BURDEN_MEDIUM:
            level = MEDIUM
        else:
            level = LOW
        rows.append(_row(
            "Housing Cost Burden", level,
            f"Housing is {burden * 100:.0f}% of income ({_money(housing)} of {_money(income)}).",
            "Keep housing near or below 30% of income for flexibility."
            if level != LOW else "Housing cost is within a comfortable share of income.",
        ))

    # 6. Insurance coverage (soft prompt from transaction signals).
    if _has_insurance(df):
        rows.append(_row(
            "Insurance Coverage", LOW,
            "Insurance payments were detected in the period.",
            "Review coverage levels annually.",
        ))
    else:
        rows.append(_row(
            "Insurance Coverage", MEDIUM,
            "No insurance payments were detected in the period.",
            "Verify health, renters/home, and auto coverage; a gap is a major financial risk.",
        ))

    return pd.DataFrame(rows, columns=["Risk", "Level", "Finding", "Recommendation"])


def risk_summary(register_df):
    """Return counts of High/Medium/Low and a one-line overall assessment."""
    counts = {
        "High": int((register_df["Level"] == HIGH).sum()),
        "Medium": int((register_df["Level"] == MEDIUM).sum()),
        "Low": int((register_df["Level"] == LOW).sum()),
    }
    if counts["High"]:
        overall = f"Attention needed: {counts['High']} high and {counts['Medium']} medium risks."
    elif counts["Medium"]:
        overall = f"Generally healthy with {counts['Medium']} medium risks to watch."
    else:
        overall = "Strong financial health: no elevated risks detected."
    return counts, overall
