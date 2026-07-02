"""Load a local personal financial profile for the personal report.

The personal report's pillar suite (runway, goals, scenarios, risk, capital
events) needs financial inputs beyond transactions: assets, liabilities, goals,
what-if scenarios, and a home target. This loader returns those from a local,
Git-ignored JSON file (`config/personal_profile.json`) when the user has created
one, and otherwise falls back to the fictional SAMPLE_PERSONAL_PROFILE so the demo
keeps working. The committed `config/personal_profile.example.json` documents the
expected shape.

Keeping the real profile local-only and Git-ignored follows the project's
privacy rules; nothing here enables real bank data or transaction import.
"""

import copy
import json
from pathlib import Path

from modules.config import SAMPLE_PERSONAL_PROFILE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "config" / "personal_profile.json"
REQUIRED_KEYS = ("assets", "liabilities", "goals", "scenarios", "home_target")


def _money(value):
    """Return a non-negative float for simple local setup form inputs."""
    try:
        text = "" if value is None else str(value).strip()
        cleaned = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
        return max(float(cleaned or 0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_onboarding_profile(
    *,
    household_name="",
    current_state="",
    checking=0.0,
    savings=0.0,
    investments=0.0,
    credit_card_debt=0.0,
    student_loan_debt=0.0,
    other_debt=0.0,
    monthly_debt_payment=0.0,
    primary_goal="",
    primary_goal_target=0.0,
    primary_goal_current=0.0,
    emergency_fund_target=0.0,
    savings_rate_target="",
    target_date="",
    home_price=0.0,
    down_payment_pct="",
    mortgage_rate="",
    major_purchase=0.0,
):
    """Build the first-run local profile from plain-English onboarding answers."""
    assets = {
        "Checking": _money(checking),
        "Savings": _money(savings),
        "Investments": _money(investments),
    }
    liabilities = {}
    for name, balance in {
        "Credit Card": credit_card_debt,
        "Student Loan": student_loan_debt,
        "Other Debt": other_debt,
    }.items():
        balance = _money(balance)
        if balance:
            liabilities[name] = {"balance": balance, "interest_rate": 0.0}

    goals = []
    emergency_target = _money(emergency_fund_target)
    if emergency_target:
        goals.append(
            {
                "name": "Emergency Fund",
                "type": "savings",
                "target_amount": emergency_target,
                "current_amount": assets["Savings"],
                "target_date": target_date,
            }
        )
    goal_target = _money(primary_goal_target)
    if primary_goal and goal_target:
        goals.append(
            {
                "name": str(primary_goal).strip(),
                "type": "savings",
                "target_amount": goal_target,
                "current_amount": _money(primary_goal_current),
                "target_date": target_date,
            }
        )
    total_debt = sum(item["balance"] for item in liabilities.values())
    if total_debt:
        goals.append(
            {
                "name": "Pay Down Debt",
                "type": "debt_payoff",
                "target_amount": 0.0,
                "current_amount": total_debt,
                "starting_amount": total_debt,
                "monthly_contribution": _money(monthly_debt_payment),
                "target_date": target_date,
            }
        )
    savings_target = _money(savings_rate_target)
    if savings_target:
        goals.append(
            {
                "name": "Hit Savings Rate Target",
                "type": "savings_rate",
                "target_amount": savings_target,
                "current_amount": 0.0,
            }
        )

    return {
        "_note": "Local profile created by first-run Streamlit onboarding. This file is Git-ignored and stays on this Mac.",
        "household": {
            "name": str(household_name or "My Household").strip(),
            "current_state": str(current_state or "").strip(),
        },
        "assets": assets,
        "liabilities": liabilities,
        "monthly_debt_payment": _money(monthly_debt_payment),
        "goals": goals,
        "scenarios": [
            {"name": "Lose job (no income)", "monthly_income": 0.0},
            {"name": "Unexpected $3,000 cost", "one_time_cost": 3000.0},
        ],
        "home_target": {
            "home_price": _money(home_price),
            "down_payment_pct": _money(down_payment_pct),
            "mortgage_rate": _money(mortgage_rate),
            "term_years": 30,
        },
        "major_purchase": _money(major_purchase),
    }


def write_personal_profile(profile, path=DEFAULT_PROFILE_PATH):
    """Write a local personal profile JSON file. Never commits or uploads data."""
    profile_path = Path(path)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return profile_path


def load_personal_profile(path=None):
    """Return the local profile JSON when present and valid, else the sample profile.

    Raises ValueError if a profile file exists but is missing required keys, so a
    malformed profile fails clearly instead of producing a confusing report.
    """
    profile_path = Path(path) if path is not None else DEFAULT_PROFILE_PATH
    if not profile_path.exists():
        return copy.deepcopy(SAMPLE_PERSONAL_PROFILE)

    with open(profile_path, encoding="utf-8") as handle:
        profile = json.load(handle)

    missing = [key for key in REQUIRED_KEYS if key not in profile]
    if missing:
        raise ValueError(
            f"Personal profile {profile_path.name} is missing required keys: "
            f"{', '.join(missing)}"
        )

    # Optional fields get safe defaults so the report sections always render.
    profile.setdefault("monthly_debt_payment", 300.0)
    profile.setdefault("major_purchase", 0.0)
    return profile
