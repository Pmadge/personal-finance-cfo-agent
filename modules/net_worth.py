"""Net worth and debt payoff analysis for fictional starter-person data."""

import pandas as pd


MONTHLY_DEBT_PAYMENT = 300.00
# Backstop so a non-amortizing plan (monthly interest >= payment) can never loop
# forever. 1200 months is 100 years; reaching it means the debt is not payable
# at the given payment.
MAX_PAYOFF_MONTHS = 1200


def _liability_balance(liability):
    """Read a liability balance from either a number or a debt dictionary."""
    if isinstance(liability, dict):
        return float(liability.get("balance", 0.0))
    return float(liability)


def net_worth_snapshot(assets, liabilities):
    """Calculate total assets, liabilities, net worth, and debt-to-asset ratio."""
    total_assets = sum(float(amount) for amount in assets.values())
    total_liabilities = sum(_liability_balance(debt) for debt in liabilities.values())
    net_worth = total_assets - total_liabilities
    debt_to_asset_ratio = (
        (total_liabilities / total_assets) * 100 if total_assets else 0.0
    )

    return {
        "Total Assets": round(total_assets, 2),
        "Total Liabilities": round(total_liabilities, 2),
        "Net Worth": round(net_worth, 2),
        "Debt-to-Asset Ratio": round(debt_to_asset_ratio, 2),
    }


def _active_debts(debts):
    """Keep payoff inputs with real balances and ignore zero-balance debts."""
    return [
        {
            "name": debt["name"],
            "balance": float(debt["balance"]),
            "interest_rate": float(debt["interest_rate"]),
        }
        for debt in debts
        if float(debt.get("balance", 0.0)) > 0
    ]


def _simulate_payoff(debts, method, monthly_payment=MONTHLY_DEBT_PAYMENT):
    """Simulate monthly payoff using avalanche or snowball ordering.

    Stops and reports the plan as not feasible if the total balance is not
    decreasing month over month (monthly interest meets or exceeds the payment),
    so a real mortgage or high-interest card can never cause an infinite loop.
    """
    active_debts = _active_debts(debts)
    total_interest_paid = 0.0
    months = 0
    payoff_possible = True

    while active_debts:
        balance_before = sum(debt["balance"] for debt in active_debts)
        months += 1

        for debt in active_debts:
            monthly_interest = debt["balance"] * (debt["interest_rate"] / 100 / 12)
            debt["balance"] += monthly_interest
            total_interest_paid += monthly_interest

        if method == "Avalanche":
            active_debts.sort(key=lambda debt: debt["interest_rate"], reverse=True)
        else:
            active_debts.sort(key=lambda debt: debt["balance"])

        payment_remaining = monthly_payment
        for debt in active_debts:
            if payment_remaining <= 0:
                break

            payment = min(payment_remaining, debt["balance"])
            debt["balance"] -= payment
            payment_remaining -= payment

        active_debts = [debt for debt in active_debts if debt["balance"] > 0.005]
        balance_after = sum(debt["balance"] for debt in active_debts)

        # If the payment cannot outpace interest, the balance stops shrinking.
        if active_debts and (
            balance_after >= balance_before - 0.005 or months >= MAX_PAYOFF_MONTHS
        ):
            payoff_possible = False
            break

    return {
        "Method": method,
        "Total Interest Paid": round(total_interest_paid, 2),
        "Months to Payoff": months if payoff_possible else MAX_PAYOFF_MONTHS,
        "Payoff Possible": payoff_possible,
    }


def _recommend_method(avalanche_result, snowball_result, monthly_payment=MONTHLY_DEBT_PAYMENT):
    """Choose a payoff method using the CFO Agent recommendation rule."""
    if not avalanche_result["Payoff Possible"] or not snowball_result["Payoff Possible"]:
        recommendation = (
            f"At ${monthly_payment:,.2f} per month the debt does not amortize "
            "because monthly interest meets or exceeds the payment. Increase the "
            "monthly payment above the total monthly interest before comparing "
            "avalanche and snowball."
        )
        return "Increase Payment", recommendation

    interest_saved = (
        snowball_result["Total Interest Paid"]
        - avalanche_result["Total Interest Paid"]
    )

    if interest_saved > 200:
        recommended_method = "Avalanche"
        recommendation = (
            f"Use the avalanche method because it saves ${interest_saved:.2f} in "
            "interest versus snowball, which is above the $200 decision threshold."
        )
    else:
        recommended_method = "Snowball"
        recommendation = (
            "Use the snowball method because avalanche does not save more than "
            "$200 in interest at this payment level, so paying the smallest "
            "balances first keeps momentum without a meaningful interest penalty."
        )

    return recommended_method, recommendation


def debt_payoff_comparison(debts, monthly_payment=MONTHLY_DEBT_PAYMENT):
    """Compare avalanche and snowball payoff results side by side."""
    avalanche_result = _simulate_payoff(debts, "Avalanche", monthly_payment)
    snowball_result = _simulate_payoff(debts, "Snowball", monthly_payment)
    recommended_method, recommendation = _recommend_method(
        avalanche_result, snowball_result, monthly_payment
    )

    rows = []
    for result in [avalanche_result, snowball_result]:
        rows.append(
            {
                "Method": result["Method"],
                "Total Interest Paid": result["Total Interest Paid"],
                "Months to Payoff": result["Months to Payoff"],
                "Recommended Method": recommended_method,
                "Recommendation Explanation": recommendation,
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "Method",
            "Total Interest Paid",
            "Months to Payoff",
            "Recommended Method",
            "Recommendation Explanation",
        ],
    )
