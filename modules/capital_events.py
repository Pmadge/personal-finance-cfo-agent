"""Capital-event playbooks for the personal CFO Agent.

The personal equivalent of a company's capital events (fundraising, M&A): the big
money decisions in a person's life. v1 covers the two most common and highest
stakes - buying a home and making a large one-time purchase - with a clear,
numbers-backed readiness verdict instead of a gut feeling.
"""

import pandas as pd

from modules.forecast import cash_runway, monthly_assumptions

FRONT_RATIO_TARGET = 0.28   # housing payment as a share of income (lenders' 28% rule)
FRONT_RATIO_MAX = 0.36      # stretch ceiling before it is clearly unaffordable
EMERGENCY_MONTHS_REQUIRED = 3.0
RENT_GROWTH_PCT = 3.0
APPRECIATION_PCT = 3.0
DEFAULT_HORIZON_YEARS = 5

READY = "🟢 Ready"
CLOSE = "🟡 Close"
NOT_YET = "🔴 Not yet"


def _money(amount):
    return f"${float(amount):,.2f}"


def _mortgage_payment(loan_amount, annual_rate_pct, term_years):
    """Standard amortized monthly principal + interest payment."""
    monthly_rate = annual_rate_pct / 100 / 12
    n_payments = int(term_years * 12)
    if n_payments <= 0:
        return 0.0
    if monthly_rate == 0:
        return loan_amount / n_payments
    growth = (1 + monthly_rate) ** n_payments
    return loan_amount * monthly_rate * growth / (growth - 1)


def home_purchase_readiness(
    df,
    assets,
    home_price,
    down_payment_pct=20.0,
    mortgage_rate=7.0,
    term_years=30,
    property_tax_rate=1.1,
    insurance_rate=0.5,
    closing_cost_pct=3.0,
    emergency_months_required=EMERGENCY_MONTHS_REQUIRED,
):
    """Assess readiness to buy a home at a given price. Returns metrics + verdict + gaps."""
    assumptions = monthly_assumptions(df)
    income = assumptions["income"]
    monthly_expenses = assumptions["total_expenses"]
    liquid_cash = float(assets.get("Checking", 0.0)) + float(assets.get("Savings", 0.0))

    down_payment = home_price * down_payment_pct / 100
    closing_costs = home_price * closing_cost_pct / 100
    cash_needed = down_payment + closing_costs
    loan_amount = home_price - down_payment

    principal_interest = _mortgage_payment(loan_amount, mortgage_rate, term_years)
    monthly_taxes = home_price * property_tax_rate / 100 / 12
    monthly_insurance = home_price * insurance_rate / 100 / 12
    piti = principal_interest + monthly_taxes + monthly_insurance

    front_ratio = (piti / income) if income > 0 else None
    cash_after = liquid_cash - cash_needed
    emergency_buffer_required = monthly_expenses * emergency_months_required

    has_cash = cash_after >= 0
    preserves_emergency = cash_after >= emergency_buffer_required
    affordable = front_ratio is not None and front_ratio <= FRONT_RATIO_TARGET
    stretch_affordable = front_ratio is not None and front_ratio <= FRONT_RATIO_MAX

    gaps = []
    if not has_cash:
        gaps.append(f"Short {_money(-cash_after)} for down payment + closing costs.")
    elif not preserves_emergency:
        gaps.append(
            f"Buying leaves {_money(cash_after)} but a {emergency_months_required:.0f}-month "
            f"emergency fund needs {_money(emergency_buffer_required)}."
        )
    if front_ratio is not None and not affordable:
        over = "above the 36% ceiling" if not stretch_affordable else "above the 28% target"
        gaps.append(f"Estimated payment is {front_ratio * 100:.0f}% of income, {over}.")
    if income <= 0:
        gaps.append("No income on record to assess affordability.")

    if has_cash and preserves_emergency and affordable:
        verdict = READY
    elif (has_cash or cash_after > -0.1 * cash_needed) and stretch_affordable:
        verdict = CLOSE
    else:
        verdict = NOT_YET

    return {
        "home_price": round(home_price, 2),
        "down_payment": round(down_payment, 2),
        "closing_costs": round(closing_costs, 2),
        "cash_needed": round(cash_needed, 2),
        "liquid_cash": round(liquid_cash, 2),
        "cash_after_purchase": round(cash_after, 2),
        "loan_amount": round(loan_amount, 2),
        "monthly_payment_piti": round(piti, 2),
        "income_monthly": round(income, 2),
        "payment_to_income": round(front_ratio * 100, 1) if front_ratio is not None else None,
        "emergency_buffer_required": round(emergency_buffer_required, 2),
        "verdict": verdict,
        "gaps": gaps,
    }


def major_purchase_check(df, assets, amount, financed=False, liquid_cash=None):
    """Quick affordability read on a large one-time purchase paid from cash."""
    if liquid_cash is None:
        liquid_cash = float(assets.get("Checking", 0.0)) + float(assets.get("Savings", 0.0))
    runway_before = cash_runway(df, liquid_cash)
    cash_after = liquid_cash - float(amount)
    runway_after = cash_runway(df, max(cash_after, 0.0))

    if cash_after < 0:
        verdict = NOT_YET
        note = f"Short {_money(-cash_after)}; not affordable from cash today."
    elif runway_after["Emergency Runway (months)"] is not None and runway_after["Emergency Runway (months)"] < EMERGENCY_MONTHS_REQUIRED:
        verdict = CLOSE
        note = "Affordable, but it drops the emergency runway below 3 months."
    else:
        verdict = READY
        note = "Affordable while keeping a healthy cash buffer."

    return {
        "amount": round(float(amount), 2),
        "liquid_cash": round(liquid_cash, 2),
        "cash_after": round(cash_after, 2),
        "runway_before_months": runway_before["Emergency Runway (months)"],
        "runway_after_months": runway_after["Emergency Runway (months)"],
        "verdict": verdict,
        "note": note,
    }


def _monthly_housing_spend(df):
    """Average monthly Housing spend from transactions, used as the current rent."""
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


def _remaining_loan_balance(loan_amount, annual_rate_pct, term_years, months_elapsed):
    """Outstanding mortgage balance after a number of monthly payments."""
    monthly_rate = annual_rate_pct / 100 / 12
    total_payments = int(term_years * 12)
    elapsed = min(int(months_elapsed), total_payments)
    if total_payments <= 0:
        return 0.0
    if monthly_rate == 0:
        return max(loan_amount * (1 - elapsed / total_payments), 0.0)
    payment = _mortgage_payment(loan_amount, annual_rate_pct, term_years)
    growth = (1 + monthly_rate) ** elapsed
    balance = loan_amount * growth - payment * (growth - 1) / monthly_rate
    return max(balance, 0.0)


def rent_vs_buy(
    df,
    home_price,
    down_payment_pct=20.0,
    mortgage_rate=7.0,
    term_years=30,
    property_tax_rate=1.1,
    insurance_rate=0.5,
    closing_cost_pct=3.0,
    current_monthly_rent=None,
    horizon_years=DEFAULT_HORIZON_YEARS,
    rent_growth_pct=RENT_GROWTH_PCT,
    appreciation_pct=APPRECIATION_PCT,
):
    """Compare the N-year net cost of renting vs buying a target home.

    Renting cost is total rent paid (growing each year). Buying cost is upfront
    cash (down payment + closing) plus total PITI over the horizon, minus the home
    equity owned at the end (appreciated price less remaining loan). This is a
    directional estimate: it excludes the investment opportunity cost of the down
    payment and is sensitive to the rent-growth and appreciation assumptions, both
    of which are returned alongside the result.
    """
    if current_monthly_rent is None:
        current_monthly_rent = _monthly_housing_spend(df)
    current_monthly_rent = float(current_monthly_rent)
    horizon_years = int(horizon_years)
    months = horizon_years * 12

    total_rent = 0.0
    rent = current_monthly_rent
    for _ in range(horizon_years):
        total_rent += rent * 12
        rent *= 1 + rent_growth_pct / 100

    down_payment = home_price * down_payment_pct / 100
    closing_costs = home_price * closing_cost_pct / 100
    loan_amount = home_price - down_payment
    principal_interest = _mortgage_payment(loan_amount, mortgage_rate, term_years)
    monthly_taxes = home_price * property_tax_rate / 100 / 12
    monthly_insurance = home_price * insurance_rate / 100 / 12
    piti = principal_interest + monthly_taxes + monthly_insurance
    total_piti = piti * months

    home_value = home_price * (1 + appreciation_pct / 100) ** horizon_years
    remaining_loan = _remaining_loan_balance(loan_amount, mortgage_rate, term_years, months)
    equity = home_value - remaining_loan
    buy_net_cost = (down_payment + closing_costs + total_piti) - equity
    rent_net_cost = total_rent

    if current_monthly_rent <= 0:
        cheaper = "Unknown"
        recommendation = "No current rent on record, so a rent-vs-buy comparison is not meaningful yet."
    else:
        cheaper = "Renting" if rent_net_cost <= buy_net_cost else "Buying"
        difference = abs(rent_net_cost - buy_net_cost)
        recommendation = (
            f"Over {horizon_years} years, {cheaper.lower()} looks about {_money(difference)} "
            f"cheaper (estimate; excludes investment returns on the down payment and assumes "
            f"{rent_growth_pct:.0f}% rent growth and {appreciation_pct:.0f}% home appreciation)."
        )

    return {
        "horizon_years": horizon_years,
        "current_monthly_rent": round(current_monthly_rent, 2),
        "rent_net_cost": round(rent_net_cost, 2),
        "buy_upfront": round(down_payment + closing_costs, 2),
        "buy_total_piti": round(total_piti, 2),
        "buy_equity_at_horizon": round(equity, 2),
        "buy_net_cost": round(buy_net_cost, 2),
        "cheaper": cheaper,
        "recommendation": recommendation,
    }
