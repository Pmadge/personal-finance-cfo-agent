"""Capital-event playbooks for the personal CFO Agent.

The personal equivalent of a company's capital events (fundraising, M&A): the big
money decisions in a person's life. v1 covers the two most common and highest
stakes - buying a home and making a large one-time purchase - with a clear,
numbers-backed readiness verdict instead of a gut feeling.
"""

from modules.forecast import cash_runway, monthly_assumptions

FRONT_RATIO_TARGET = 0.28   # housing payment as a share of income (lenders' 28% rule)
FRONT_RATIO_MAX = 0.36      # stretch ceiling before it is clearly unaffordable
EMERGENCY_MONTHS_REQUIRED = 3.0

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
