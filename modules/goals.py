"""Personal financial goal tracking for the CFO Agent.

Turns a person's goals (saving for something, paying off debt, growing net worth,
hitting a savings rate) into a progress tracker the reports can show: how far
along they are, how much remains, whether they are on track for a target date,
and what monthly amount keeps them on schedule.

The engine is pure and deterministic: the caller passes each goal's current value
(usually pulled from the same numbers the monthly report already computes), and
this module computes progress and status. Projections are directional estimates,
not guarantees, and are labeled as such in the status text.
"""

import math

import pandas as pd

GOAL_TYPES = {"savings", "debt_payoff", "net_worth", "savings_rate"}


def _months_until(target_date, as_of_date):
    """Whole calendar months from as_of_date to target_date (can be negative)."""
    target = pd.Timestamp(target_date)
    as_of = pd.Timestamp(as_of_date)
    return (target.year - as_of.year) * 12 + (target.month - as_of.month)


def _money(amount):
    return f"${float(amount):,.2f}"


def _amount_goal_row(goal, as_of_date, default_monthly, lower_is_better):
    """Progress for a dollar-amount goal (savings, debt_payoff, net_worth)."""
    target = float(goal["target_amount"])
    current = float(goal["current_amount"])
    monthly = goal.get("monthly_contribution", default_monthly)
    monthly = float(monthly) if monthly is not None else None
    target_date = goal.get("target_date")

    if lower_is_better:
        # Debt: progress is how much of the starting balance has been paid down.
        starting = float(goal.get("starting_amount", current))
        remaining = max(current - target, 0.0)
        paid = max(starting - current, 0.0)
        denominator = max(starting - target, 0.0)
        progress = min(paid / denominator * 100, 100.0) if denominator else 100.0
    else:
        # Savings / net worth: progress is how much of the target is reached.
        remaining = max(target - current, 0.0)
        progress = min(current / target * 100, 100.0) if target > 0 else (
            100.0 if current >= target else 0.0
        )

    months = _months_until(target_date, as_of_date) if target_date else None
    monthly_needed = None
    if remaining <= 0:
        status = "✅ Achieved"
    elif goal["type"] == "debt_payoff" and goal.get("interest_rate") and monthly is not None:
        monthly_interest = current * float(goal["interest_rate"]) / 100 / 12
        if monthly <= monthly_interest:
            status = (
                f"🔴 Off track: {_money(monthly)}/mo payment is below the "
                f"{_money(monthly_interest)} monthly interest"
            )
        else:
            months_to_clear = math.ceil(remaining / (monthly - monthly_interest))
            status = f"🟢 On track: about {months_to_clear} months at {_money(monthly)}/mo (estimate)"
            monthly_needed = remaining / months if months and months > 0 else None
    elif months is not None and months > 0:
        monthly_needed = remaining / months
        if monthly is not None and monthly >= monthly_needed:
            status = f"🟢 On track: {_money(monthly)}/mo covers the {_money(monthly_needed)} needed"
        else:
            have = _money(monthly) if monthly is not None else "$0.00"
            status = f"🔴 Behind: need {_money(monthly_needed)}/mo, have {have}/mo"
    elif months is not None and months <= 0:
        status = "🔴 Behind: target date has passed"
    else:
        status = f"📊 In progress: {progress:.0f}% there"

    return {
        "Goal": goal["name"],
        "Type": goal["type"],
        "Target": round(target, 2),
        "Current": round(current, 2),
        "Remaining": round(remaining, 2),
        "Progress (%)": round(progress, 1),
        "Monthly Needed": round(monthly_needed, 2) if monthly_needed is not None else None,
        "Status": status,
    }


def _rate_goal_row(goal):
    """Progress for a savings-rate goal (a percentage target, not a dollar amount)."""
    target = float(goal["target_amount"])
    current = float(goal["current_amount"])
    progress = min(current / target * 100, 100.0) if target > 0 else 100.0
    if current >= target:
        status = f"✅ Meeting target: {current:.1f}% vs {target:.1f}% goal"
    else:
        status = f"🔴 Below target: {current:.1f}% vs {target:.1f}% goal"
    return {
        "Goal": goal["name"],
        "Type": goal["type"],
        "Target": round(target, 2),
        "Current": round(current, 2),
        "Remaining": round(max(target - current, 0.0), 2),
        "Progress (%)": round(progress, 1),
        "Monthly Needed": None,
        "Status": status,
    }


def track_goals(goals, as_of_date, default_monthly=None):
    """Return a progress tracker DataFrame for a list of personal goals.

    Each goal is a dict with: name, type (one of GOAL_TYPES), target_amount,
    current_amount, and optionally target_date, monthly_contribution,
    interest_rate (debt), and starting_amount (debt). default_monthly is the
    fallback monthly amount (e.g. net cash flow) used when a goal has no explicit
    monthly_contribution.
    """
    columns = ["Goal", "Type", "Target", "Current", "Remaining", "Progress (%)", "Monthly Needed", "Status"]
    rows = []
    for goal in goals:
        goal_type = goal.get("type")
        if goal_type not in GOAL_TYPES:
            raise ValueError(f"Unknown goal type: {goal_type}")
        if goal_type == "savings_rate":
            rows.append(_rate_goal_row(goal))
        else:
            rows.append(
                _amount_goal_row(
                    goal,
                    as_of_date,
                    default_monthly,
                    lower_is_better=(goal_type == "debt_payoff"),
                )
            )
    return pd.DataFrame(rows, columns=columns)
