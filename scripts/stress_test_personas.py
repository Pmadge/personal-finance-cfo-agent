"""Saved multi-persona robustness stress test for the CFO Agent engine.

This script creates fully fictional sample datasets and runs each one through the
real local analytics pipeline. It writes inspectable CSV/JSON/Markdown results so
Paul can review both the inputs and the outputs by hand.

Fictional data only. This script never touches real personal data.

Run:
    python3 scripts/stress_test_personas.py
    python3 scripts/stress_test_personas.py --count 120 --output-dir outputs/stress_tests/my_run
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import argparse
import json
import random
import signal
import shutil
import sys
import time
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.action_items import generate_action_items
from modules.analytics import (
    budget_vs_actual,
    cumulative_budget_vs_actual,
    mom_comparison,
    monthly_summary,
    upcoming_obligations,
)
from modules.capital_events import home_purchase_readiness, major_purchase_check
from modules.categorizer import categorize_file
from modules.config import APPROVED_CATEGORIES
from modules.detectors import detect_recurring, detect_unusual
from modules.forecast import cash_runway, forecast_cash_flow, project_cash_flow
from modules.goals import track_goals
from modules.net_worth import debt_payoff_comparison, net_worth_snapshot
from modules.risk import build_risk_register, risk_summary
from modules.scenarios import compare_scenarios
from modules.scorecard import outcomes_scorecard
from modules.self_checks import assert_pipeline_self_checks

REPORT_MONTH = "2026-03"
PRIOR_MONTH = "2026-02"
MONTHS = ["2026-01", "2026-02", "2026-03"]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "stress_tests"

LIFE_STAGES = [
    "college student",
    "early career renter",
    "young family",
    "mid-career homeowner",
    "single parent",
    "freelancer",
    "small business owner",
    "late-career professional",
    "pre-retiree",
    "retiree",
]
CAREERS = [
    "student worker",
    "teacher",
    "nurse",
    "software engineer",
    "sales rep",
    "freelance designer",
    "restaurant manager",
    "electrician",
    "law associate",
    "small business owner",
    "consultant",
    "retired public employee",
]
WEALTH_PROFILES = [
    "negative net worth",
    "paycheck-to-paycheck",
    "thin emergency fund",
    "stable saver",
    "high income high spend",
    "mass affluent",
    "wealthy investor",
    "retired fixed income",
]
SPENDING_STYLES = [
    "minimalist",
    "food-heavy",
    "commuter-heavy",
    "subscription-heavy",
    "family/household-heavy",
    "shopping-heavy",
    "medical-heavy",
    "education-heavy",
    "travel/entertainment-heavy",
    "balanced",
]
PLAN_TYPES = [
    "debt payoff",
    "emergency fund rebuild",
    "home down payment",
    "new baby buffer",
    "career transition",
    "business runway",
    "retirement glidepath",
    "investment acceleration",
    "large purchase readiness",
    "spending reset",
]

VENDORS = {
    "income": ["ACME Payroll Direct Deposit", "State University Payroll", "Freelance Client Payment", "Zelle From Client", "Pension Deposit"],
    "rent": ["Parkside Rent Portal", "Riverside Rent", "Maple Street Apartments", "Wells Fargo Mortgage", "Sunset Apartments Rent"],
    "groceries": ["Trader Joe's", "Safeway", "Costco Wholesale #123", "Kroger", "Whole Foods Market"],
    "dining": ["Chipotle", "Starbucks Store 555", "Sushi Spot", "Uber Eats Burger Bar", "Local Taqueria"],
    "transportation": ["Shell Oil Gas Station", "Chevron 0421", "Uber", "Lyft", "Bay Area Transit"],
    "subscription": ["Netflix", "Spotify", "Comcast Xfinity", "Hulu", "Apple iCloud"],
    "gym": ["CityFit Gym", "Planet Fitness", "Yoga Studio Monthly"],
    "clothing": ["Zara", "Target", "Amazon Marketplace", "Nordstrom Rack", "Old Navy"],
    "household": ["Home Depot", "IKEA", "Target", "Amazon Marketplace", "Costco Wholesale #123"],
    "phone": ["Verizon Wireless", "AT&T Wireless", "T-Mobile"],
    "health": ["CVS Pharmacy", "Dentist Copay", "Kaiser Medical", "Walgreens Pharmacy"],
    "student_loan": ["Federal Student Loan Servicer", "Sallie Mae Student Loan"],
    "unusual": ["Apple Store Repair", "Auto Registration Renewal", "Emergency Vet Clinic", "Moving Company"],
}

SPENDING_MULTIPLIERS = {
    "minimalist": {"Food": 0.75, "Transport": 0.75, "Shopping": 0.45, "Subscriptions": 0.6, "Entertainment": 0.4},
    "food-heavy": {"Food": 1.55, "Entertainment": 1.1},
    "commuter-heavy": {"Transport": 1.9},
    "subscription-heavy": {"Subscriptions": 2.2, "Entertainment": 1.15},
    "family/household-heavy": {"Food": 1.35, "Shopping": 1.6, "Medical": 1.25},
    "shopping-heavy": {"Shopping": 2.1, "Entertainment": 1.25},
    "medical-heavy": {"Medical": 2.4, "Shopping": 0.8},
    "education-heavy": {"Education": 2.0, "Subscriptions": 1.1},
    "travel/entertainment-heavy": {"Entertainment": 2.1, "Transport": 1.4},
    "balanced": {},
}


class StepTimeout(Exception):
    """Raised when one pipeline step takes too long."""


@contextmanager
def time_limit(seconds: int):
    """Hard safety net so a regression can never hang the stress test."""

    def handler(signum, frame):  # noqa: ARG001 - signal handler signature
        raise StepTimeout(f"exceeded {seconds}s")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def tx(date: str, vendor: str, amount: float, raw_category: str) -> dict[str, Any]:
    """Create one fictional transaction row."""
    return {
        "date": date,
        "vendor": vendor,
        "amount": round(float(amount), 2),
        "raw_category": raw_category,
    }


def _slug(text: str) -> str:
    """Make a safe folder/file identifier."""
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")


def _jsonable(value: Any) -> Any:
    """Convert common pandas/numpy values into JSON-safe values."""
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001 - fallback stringification is safer for reports
            return str(value)
    return value


def _pick(rng: random.Random, values: list[str]) -> str:
    return values[rng.randrange(len(values))]


def _income_for_profile(rng: random.Random, wealth_profile: str, career: str) -> float:
    ranges = {
        "negative net worth": (1800, 4200),
        "paycheck-to-paycheck": (2400, 5600),
        "thin emergency fund": (3500, 7500),
        "stable saver": (4500, 9500),
        "high income high spend": (9000, 18000),
        "mass affluent": (11000, 22000),
        "wealthy investor": (16000, 35000),
        "retired fixed income": (2200, 7500),
    }
    low, high = ranges[wealth_profile]
    if career in {"software engineer", "law associate", "consultant", "small business owner"}:
        high *= 1.15
    if career in {"student worker", "teacher", "restaurant manager"}:
        high *= 0.9
    return round(rng.uniform(low, high), 2)


def _asset_liability_profile(
    rng: random.Random,
    monthly_income: float,
    wealth_profile: str,
    life_stage: str,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Create fictional balance-sheet inputs with a wide wealth range."""
    if wealth_profile == "negative net worth":
        checking = rng.uniform(100, 1500)
        savings = rng.uniform(0, 1500)
        investments = rng.uniform(0, 3000)
        card = rng.uniform(6000, 35000)
        student = rng.uniform(5000, 100000)
    elif wealth_profile == "paycheck-to-paycheck":
        checking = rng.uniform(100, monthly_income * 0.8)
        savings = rng.uniform(0, monthly_income * 0.5)
        investments = rng.uniform(0, monthly_income)
        card = rng.uniform(1000, 18000)
        student = rng.uniform(0, 70000)
    elif wealth_profile == "thin emergency fund":
        checking = rng.uniform(monthly_income * 0.2, monthly_income)
        savings = rng.uniform(monthly_income * 0.2, monthly_income * 1.5)
        investments = rng.uniform(0, monthly_income * 3)
        card = rng.uniform(0, 12000)
        student = rng.uniform(0, 60000)
    elif wealth_profile == "stable saver":
        checking = rng.uniform(monthly_income * 0.4, monthly_income * 1.5)
        savings = rng.uniform(monthly_income * 2, monthly_income * 8)
        investments = rng.uniform(monthly_income * 2, monthly_income * 20)
        card = rng.uniform(0, 4000)
        student = rng.uniform(0, 40000)
    elif wealth_profile == "high income high spend":
        checking = rng.uniform(monthly_income * 0.3, monthly_income * 1.2)
        savings = rng.uniform(monthly_income * 0.5, monthly_income * 4)
        investments = rng.uniform(monthly_income, monthly_income * 15)
        card = rng.uniform(5000, 45000)
        student = rng.uniform(0, 160000)
    elif wealth_profile == "mass affluent":
        checking = rng.uniform(monthly_income * 0.5, monthly_income * 2)
        savings = rng.uniform(monthly_income * 4, monthly_income * 12)
        investments = rng.uniform(monthly_income * 20, monthly_income * 80)
        card = rng.uniform(0, 8000)
        student = rng.uniform(0, 70000)
    elif wealth_profile == "wealthy investor":
        checking = rng.uniform(monthly_income, monthly_income * 3)
        savings = rng.uniform(monthly_income * 6, monthly_income * 18)
        investments = rng.uniform(monthly_income * 80, monthly_income * 250)
        card = rng.uniform(0, 12000)
        student = rng.uniform(0, 90000)
    else:  # retired fixed income
        checking = rng.uniform(monthly_income * 0.5, monthly_income * 2)
        savings = rng.uniform(monthly_income * 3, monthly_income * 20)
        investments = rng.uniform(monthly_income * 10, monthly_income * 120)
        card = rng.uniform(0, 8000)
        student = 0

    assets = {
        "Checking": round(checking, 2),
        "Savings": round(savings, 2),
        "Investments": round(investments, 2),
    }
    liabilities: dict[str, dict[str, float]] = {}
    if card > 500:
        liabilities["Credit Card"] = {"balance": round(card, 2), "interest_rate": round(rng.uniform(16, 29), 2)}
    if student > 500:
        liabilities["Student Loan"] = {"balance": round(student, 2), "interest_rate": round(rng.uniform(3.5, 8.5), 2)}
    if life_stage in {"young family", "mid-career homeowner", "late-career professional", "pre-retiree"}:
        if rng.random() < 0.65:
            liabilities["Mortgage"] = {
                "balance": round(rng.uniform(180000, 950000), 2),
                "interest_rate": round(rng.uniform(3.5, 7.5), 2),
            }
    if rng.random() < 0.45:
        liabilities["Car Loan"] = {"balance": round(rng.uniform(4000, 55000), 2), "interest_rate": round(rng.uniform(4, 12), 2)}
    return assets, liabilities


def _monthly_budget(monthly_income: float, housing: float, style: str) -> dict[str, float]:
    """Generate a realistic monthly budget for the fictional persona."""
    base = {
        "Housing": housing,
        "Food": monthly_income * 0.11,
        "Transport": monthly_income * 0.055,
        "Subscriptions": max(40, monthly_income * 0.018),
        "Shopping": monthly_income * 0.06,
        "Misc": monthly_income * 0.035,
        "Entertainment": monthly_income * 0.04,
        "Medical": monthly_income * 0.025,
        "Education": monthly_income * 0.02,
    }
    for key, multiplier in SPENDING_MULTIPLIERS.get(style, {}).items():
        if key in base:
            base[key] *= multiplier
    return {key: round(value, 2) for key, value in base.items() if value > 0}


def _spending_amounts(monthly_income: float, housing: float, style: str, rng: random.Random) -> dict[str, float]:
    """Generate monthly spending levels; some personas intentionally overrun budget."""
    budget = _monthly_budget(monthly_income, housing, style)
    volatility = rng.uniform(0.75, 1.35)
    amounts = {
        "rent": housing,
        "groceries": budget["Food"] * rng.uniform(0.45, 0.75) * volatility,
        "dining": budget["Food"] * rng.uniform(0.20, 0.65) * volatility,
        "transportation": budget["Transport"] * rng.uniform(0.75, 1.35),
        "subscription": budget["Subscriptions"] * rng.uniform(0.7, 1.4),
        "gym": max(0, rng.choice([0, 0, 25, 45, 90])),
        "clothing": budget["Shopping"] * rng.uniform(0.35, 1.25),
        "household": budget["Shopping"] * rng.uniform(0.20, 1.0),
        "phone": max(35, monthly_income * rng.uniform(0.008, 0.018)),
        "health": budget["Medical"] * rng.uniform(0.15, 1.6),
        "student_loan": budget["Education"] * rng.uniform(0.0, 2.0),
        "unusual": 0,
    }
    if rng.random() < 0.28:
        amounts["unusual"] = rng.uniform(250, monthly_income * 0.8)
    return {key: round(value, 2) for key, value in amounts.items()}


def _monthly_income_series(monthly_income: float, career: str, rng: random.Random) -> dict[str, float]:
    """Generate steady, irregular, zero-income, or fixed income patterns."""
    if career in {"freelance designer", "consultant", "small business owner"}:
        return {month: round(max(0, monthly_income * rng.uniform(0.45, 1.75)), 2) for month in MONTHS}
    if career in {"student worker", "restaurant manager", "sales rep"}:
        return {month: round(max(0, monthly_income * rng.uniform(0.75, 1.25)), 2) for month in MONTHS}
    if career == "retired public employee":
        return {month: round(monthly_income, 2) for month in MONTHS}
    return {month: round(monthly_income * rng.uniform(0.96, 1.04), 2) for month in MONTHS}


def generate_persona(index: int, seed: int) -> dict[str, Any]:
    """Generate one fictional stress-test persona and transaction dataset."""
    rng = random.Random(seed + index * 7919)
    life_stage = _pick(rng, LIFE_STAGES)
    career = _pick(rng, CAREERS)
    wealth_profile = _pick(rng, WEALTH_PROFILES)
    spending_style = _pick(rng, SPENDING_STYLES)
    plan_type = _pick(rng, PLAN_TYPES)
    monthly_income = _income_for_profile(rng, wealth_profile, career)
    housing = monthly_income * rng.uniform(0.18, 0.48)
    if life_stage in {"college student", "early career renter"}:
        housing *= rng.uniform(0.65, 0.95)
    if life_stage in {"young family", "mid-career homeowner"}:
        housing *= rng.uniform(1.05, 1.35)
    housing = round(max(450, housing), 2)

    assets, liabilities = _asset_liability_profile(rng, monthly_income, wealth_profile, life_stage)
    budget = _monthly_budget(monthly_income, housing, spending_style)
    spend = _spending_amounts(monthly_income, housing, spending_style, rng)
    income_by_month = _monthly_income_series(monthly_income, career, rng)

    rows: list[dict[str, Any]] = []
    for month in MONTHS:
        rows.append(tx(f"{month}-01", _pick(rng, VENDORS["income"]), income_by_month[month], "income"))
        rows.append(tx(f"{month}-03", _pick(rng, VENDORS["rent"]), -spend["rent"], "rent"))
        rows.append(tx(f"{month}-05", _pick(rng, VENDORS["groceries"]), -spend["groceries"], "groceries"))
        rows.append(tx(f"{month}-12", _pick(rng, VENDORS["dining"]), -spend["dining"], "dining"))
        rows.append(tx(f"{month}-08", _pick(rng, VENDORS["transportation"]), -spend["transportation"], "transportation"))
        rows.append(tx(f"{month}-06", _pick(rng, VENDORS["subscription"]), -spend["subscription"], "subscription"))
        if spend["gym"] > 0:
            rows.append(tx(f"{month}-07", _pick(rng, VENDORS["gym"]), -spend["gym"], "gym"))
        rows.append(tx(f"{month}-15", _pick(rng, VENDORS["clothing"]), -spend["clothing"], "clothing"))
        rows.append(tx(f"{month}-19", _pick(rng, VENDORS["household"]), -spend["household"], "household"))
        rows.append(tx(f"{month}-21", _pick(rng, VENDORS["phone"]), -spend["phone"], "phone"))
        if spend["health"] > 30:
            rows.append(tx(f"{month}-23", _pick(rng, VENDORS["health"]), -spend["health"], "health"))
        if spend["student_loan"] > 25:
            rows.append(tx(f"{month}-25", _pick(rng, VENDORS["student_loan"]), -spend["student_loan"], "student_loan"))
    if spend["unusual"] > 0:
        rows.append(tx("2026-03-27", _pick(rng, VENDORS["unusual"]), -spend["unusual"], "unusual"))
    if rng.random() < 0.18:
        rows.append(tx("2026-03-17", "Refund - Target", round(rng.uniform(20, 400), 2), "household"))

    net = net_worth_snapshot(assets, liabilities)
    liquid_cash = assets["Checking"] + assets["Savings"]
    goals = _goals_for_persona(index, plan_type, assets, liabilities, monthly_income, net["Net Worth"])
    scenarios = [
        {"name": "Lose income", "monthly_income": 0.0},
        {"name": "Raise or new client", "monthly_income_change": round(monthly_income * 0.10, 2)},
        {"name": "Cut variable spending 15%", "variable_spend_pct": -0.15},
        {"name": "Housing cost jump", "monthly_expense_change": round(housing * 0.15, 2)},
        {"name": "Large one-time purchase", "one_time_cost": round(max(1500, liquid_cash * 0.35), 2)},
    ]
    home_target = {
        "home_price": round(max(150000, monthly_income * rng.uniform(45, 95)), 2),
        "down_payment_pct": rng.choice([3.5, 5.0, 10.0, 20.0]),
        "mortgage_rate": round(rng.uniform(5.5, 7.5), 2),
        "term_years": 30,
    }
    major_purchase = round(max(1000, monthly_income * rng.uniform(0.25, 1.8)), 2)
    monthly_debt_payment = round(max(150, monthly_income * rng.uniform(0.04, 0.18)), 2)
    persona_id = f"persona_{index:03d}_{_slug(life_stage)}_{_slug(spending_style)}"
    return {
        "persona_id": persona_id,
        "display_name": f"Fictional Persona {index:03d}",
        "life_stage": life_stage,
        "career": career,
        "wealth_profile": wealth_profile,
        "spending_style": spending_style,
        "plan_type": plan_type,
        "report_month": REPORT_MONTH,
        "prior_month": PRIOR_MONTH,
        "monthly_income_target": monthly_income,
        "budget": budget,
        "assets": assets,
        "liabilities": liabilities,
        "monthly_debt_payment": monthly_debt_payment,
        "goals": goals,
        "scenarios": scenarios,
        "home_target": home_target,
        "major_purchase": major_purchase,
        "rows": rows,
    }


def _goals_for_persona(
    index: int,
    plan_type: str,
    assets: dict[str, float],
    liabilities: dict[str, dict[str, float]],
    monthly_income: float,
    net_worth: float,
) -> list[dict[str, Any]]:
    """Create goal diversity: savings, debt, net worth, and savings-rate goals."""
    savings = assets.get("Savings", 0.0)
    card = liabilities.get("Credit Card", {"balance": 0.0, "interest_rate": 0.0})
    goals = [
        {
            "name": f"{plan_type.title()} Emergency Buffer",
            "type": "savings",
            "target_amount": round(max(monthly_income * 3, savings + monthly_income), 2),
            "current_amount": round(savings, 2),
            "target_date": "2026-12-31",
        },
        {
            "name": "Primary Debt Payoff",
            "type": "debt_payoff",
            "target_amount": 0.0,
            "current_amount": round(float(card.get("balance", 0.0)), 2),
            "starting_amount": round(float(card.get("balance", 0.0)), 2),
            "interest_rate": round(float(card.get("interest_rate", 0.0)), 2),
            "monthly_contribution": round(max(100, monthly_income * 0.06), 2),
            "target_date": "2027-12-31",
        },
        {
            "name": "Net Worth Milestone",
            "type": "net_worth",
            "target_amount": round(max(0, net_worth + monthly_income * (6 + index % 12)), 2),
            "current_amount": round(net_worth, 2),
            "target_date": "2028-12-31",
        },
        {
            "name": "Savings Rate Target",
            "type": "savings_rate",
            "target_amount": float(8 + (index % 18)),
            "current_amount": 0.0,
        },
    ]
    return goals


def run_step(name: str, fn, results: list[dict[str, Any]], timeout: int = 8) -> Any:
    """Run one pipeline step and record pass/fail/timeout without stopping the run."""
    try:
        with time_limit(timeout):
            out = fn()
        results.append({"step": name, "status": "PASS", "detail": ""})
        return out
    except StepTimeout as exc:
        results.append({"step": name, "status": "TIMEOUT", "detail": str(exc)})
    except Exception as exc:  # noqa: BLE001 - stress tests should record every failure shape
        results.append({"step": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
    return None


def _write_table(value: Any, path: Path) -> None:
    """Persist a table-like value as CSV when possible, JSON otherwise."""
    if isinstance(value, pd.DataFrame):
        value.to_csv(path.with_suffix(".csv"), index=False)
    elif isinstance(value, dict):
        path.with_suffix(".json").write_text(json.dumps(_jsonable(value), indent=2, ensure_ascii=False))
    elif value is not None:
        path.with_suffix(".json").write_text(json.dumps(_jsonable(value), indent=2, ensure_ascii=False))


def run_persona(persona: dict[str, Any], persona_dir: Path) -> dict[str, Any]:
    """Run one fictional persona through the full local analytics stack."""
    persona_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = persona_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    input_path = persona_dir / "input_transactions.csv"
    output_path = persona_dir / "categorized_transactions.csv"
    pd.DataFrame(persona["rows"]).to_csv(input_path, index=False)
    profile = {key: value for key, value in persona.items() if key != "rows"}
    (persona_dir / "profile.json").write_text(json.dumps(_jsonable(profile), indent=2, ensure_ascii=False))

    results: list[dict[str, Any]] = []
    categorized = run_step("categorize_file", lambda: categorize_file(input_path, output_path), results)
    df = None
    accuracy = None
    misc_rate = None
    outputs: dict[str, Any] = {}

    if categorized is not None:
        df, accuracy = categorized
        misc_rate = round(float((df["assigned_category"] == "Misc").mean() * 100), 2)
        outputs["self_checks"] = run_step(
            "assert_pipeline_self_checks",
            lambda: assert_pipeline_self_checks(df, persona["report_month"], APPROVED_CATEGORIES),
            results,
        )
        outputs["monthly_summary"] = run_step(
            "monthly_summary", lambda: monthly_summary(df, persona["report_month"]), results
        )
        outputs["prior_month_summary"] = run_step(
            "prior_month_summary", lambda: monthly_summary(df, persona["prior_month"]), results
        )
        outputs["budget_vs_actual"] = run_step(
            "budget_vs_actual",
            lambda: budget_vs_actual(df, persona["report_month"], persona["budget"]),
            results,
        )
        outputs["cumulative_budget_vs_actual"] = run_step(
            "cumulative_budget_vs_actual",
            lambda: cumulative_budget_vs_actual(df, persona["budget"]),
            results,
        )
        outputs["mom_comparison"] = run_step("mom_comparison", lambda: mom_comparison(df), results)
        outputs["recurring"] = run_step("detect_recurring", lambda: detect_recurring(df), results)
        outputs["unusual"] = run_step("detect_unusual", lambda: detect_unusual(df), results)
        outputs["upcoming_obligations"] = run_step("upcoming_obligations", lambda: upcoming_obligations(df), results)
        outputs["forecast_cash_flow"] = run_step(
            "forecast_cash_flow",
            lambda: forecast_cash_flow(df, starting_cash=persona["assets"].get("Checking", 0.0)),
            results,
        )
        liquid_cash = persona["assets"].get("Checking", 0.0) + persona["assets"].get("Savings", 0.0)
        outputs["cash_runway"] = run_step("cash_runway", lambda: cash_runway(df, liquid_cash), results)
        outputs["cash_projection"] = run_step(
            "project_cash_flow",
            lambda: project_cash_flow(df, starting_cash=liquid_cash, months=12, start_month="2026-04"),
            results,
        )
        outputs["scenarios"] = run_step(
            "compare_scenarios",
            lambda: compare_scenarios(df, liquid_cash, persona["scenarios"]),
            results,
        )
        outputs["risk_register"] = run_step(
            "risk_register",
            lambda: build_risk_register(df, persona["assets"], persona["liabilities"], liquid_cash),
            results,
        )
        if isinstance(outputs["risk_register"], pd.DataFrame):
            outputs["risk_summary"] = run_step(
                "risk_summary", lambda: risk_summary(outputs["risk_register"]), results
            )
        outputs["home_purchase"] = run_step(
            "home_purchase_readiness",
            lambda: home_purchase_readiness(df, persona["assets"], **persona["home_target"]),
            results,
        )
        outputs["major_purchase"] = run_step(
            "major_purchase_check",
            lambda: major_purchase_check(df, persona["assets"], persona["major_purchase"], liquid_cash=liquid_cash),
            results,
        )
        outputs["scorecard"] = run_step(
            "outcomes_scorecard",
            lambda: outcomes_scorecard(df, persona["report_month"], persona["prior_month"]),
            results,
        )
        live_goals = [dict(goal) for goal in persona["goals"]]
        if isinstance(outputs["monthly_summary"], dict):
            for goal in live_goals:
                if goal["type"] == "savings_rate":
                    goal["current_amount"] = outputs["monthly_summary"]["Savings Rate"]
        outputs["goals"] = run_step(
            "track_goals",
            lambda: track_goals(
                live_goals,
                as_of_date="2026-03-28",
                default_monthly=(outputs["monthly_summary"] or {}).get("Net Cash Flow")
                if isinstance(outputs["monthly_summary"], dict)
                else None,
            ),
            results,
        )
        outputs["action_items"] = run_step(
            "generate_action_items",
            lambda: generate_action_items(df, persona["report_month"], persona["budget"], owner=persona["display_name"]),
            results,
        )

    outputs["net_worth"] = run_step(
        "net_worth_snapshot", lambda: net_worth_snapshot(persona["assets"], persona["liabilities"]), results
    )
    debts = [
        {"name": name, "balance": debt["balance"], "interest_rate": debt["interest_rate"]}
        for name, debt in persona["liabilities"].items()
    ]
    if debts:
        outputs["debt_payoff"] = run_step(
            "debt_payoff_comparison",
            lambda: debt_payoff_comparison(debts, monthly_payment=persona["monthly_debt_payment"]),
            results,
        )

    for name, output in outputs.items():
        _write_table(output, tables_dir / name)

    (persona_dir / "step_results.json").write_text(json.dumps(_jsonable(results), indent=2, ensure_ascii=False))
    summary = _persona_summary(persona, results, outputs, accuracy, misc_rate)
    (persona_dir / "report_summary.md").write_text(_persona_markdown(persona, summary, results, outputs))
    return summary


def _dict_output(outputs: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a dict output or an empty dict for failed/not-run steps."""
    value = outputs.get(key)
    return value if isinstance(value, dict) else {}


def _persona_summary(
    persona: dict[str, Any],
    results: list[dict[str, Any]],
    outputs: dict[str, Any],
    accuracy: float | None,
    misc_rate: float | None,
) -> dict[str, Any]:
    failures = [r for r in results if r["status"] != "PASS"]
    monthly = _dict_output(outputs, "monthly_summary")
    net_worth = _dict_output(outputs, "net_worth")
    runway = _dict_output(outputs, "cash_runway")
    risk_counts, risk_overall = ({}, "")
    risk_summary_value = outputs.get("risk_summary")
    if isinstance(risk_summary_value, tuple):
        risk_counts, risk_overall = risk_summary_value
    return {
        "persona_id": persona["persona_id"],
        "display_name": persona["display_name"],
        "status": "PASS" if not failures else "FAIL",
        "failed_steps": ", ".join(f"{r['step']}:{r['status']}" for r in failures),
        "step_count": len(results),
        "transaction_count": len(persona["rows"]),
        "life_stage": persona["life_stage"],
        "career": persona["career"],
        "wealth_profile": persona["wealth_profile"],
        "spending_style": persona["spending_style"],
        "plan_type": persona["plan_type"],
        "accuracy_rate": round(float(accuracy), 2) if accuracy is not None else None,
        "misc_rate": misc_rate,
        "income": monthly.get("Income"),
        "expenses": monthly.get("Total Expenses"),
        "net_cash_flow": monthly.get("Net Cash Flow"),
        "savings_rate": monthly.get("Savings Rate"),
        "net_worth": net_worth.get("Net Worth"),
        "debt_to_asset_ratio": net_worth.get("Debt-to-Asset Ratio"),
        "emergency_runway_months": runway.get("Emergency Runway (months)"),
        "risk_overall": risk_overall,
        "high_risks": risk_counts.get("High", 0) if isinstance(risk_counts, dict) else 0,
    }


def _persona_markdown(
    persona: dict[str, Any],
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    outputs: dict[str, Any],
) -> str:
    """Create a readable one-person report summary."""
    monthly = _dict_output(outputs, "monthly_summary")
    net_worth = _dict_output(outputs, "net_worth")
    home = _dict_output(outputs, "home_purchase")
    purchase = _dict_output(outputs, "major_purchase")
    lines = [
        f"# {persona['display_name']} - {persona['persona_id']}",
        "",
        "Fictional/sample data only. No real personal financial data is used.",
        "",
        "## Profile",
        f"- Life stage: {persona['life_stage']}",
        f"- Career: {persona['career']}",
        f"- Wealth profile: {persona['wealth_profile']}",
        f"- Spending style: {persona['spending_style']}",
        f"- Current plan/goal: {persona['plan_type']}",
        f"- Transactions: {summary['transaction_count']}",
        "",
        "## Key outputs",
        f"- Status: {summary['status']}",
        f"- Categorizer accuracy: {summary['accuracy_rate']}%",
        f"- Misc rate: {summary['misc_rate']}%",
        f"- Income: ${monthly.get('Income', 0):,.2f}",
        f"- Expenses: ${monthly.get('Total Expenses', 0):,.2f}",
        f"- Net cash flow: ${monthly.get('Net Cash Flow', 0):,.2f}",
        f"- Savings rate: {monthly.get('Savings Rate', 0):,.2f}%",
        f"- Net worth: ${net_worth.get('Net Worth', 0):,.2f}",
        f"- Emergency runway: {summary.get('emergency_runway_months')} months",
        f"- Risk summary: {summary.get('risk_overall')}",
        f"- Home readiness: {home.get('verdict', 'not run')}",
        f"- Major purchase readiness: {purchase.get('verdict', 'not run')}",
        "",
        "## Step results",
    ]
    for result in results:
        detail = f" - {result['detail']}" if result["detail"] else ""
        lines.append(f"- {result['step']}: {result['status']}{detail}")
    return "\n".join(lines) + "\n"


def _aggregate_json(summary_rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Create run-level summary metadata."""
    failed = [row for row in summary_rows if row["status"] != "PASS"]
    coverage = {
        "life_stages": sorted({row["life_stage"] for row in summary_rows}),
        "careers": sorted({row["career"] for row in summary_rows}),
        "wealth_profiles": sorted({row["wealth_profile"] for row in summary_rows}),
        "spending_styles": sorted({row["spending_style"] for row in summary_rows}),
        "plan_types": sorted({row["plan_type"] for row in summary_rows}),
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "persona_count": len(summary_rows),
        "passed": len(summary_rows) - len(failed),
        "failed": len(failed),
        "coverage": coverage,
        "failed_personas": [row["persona_id"] for row in failed],
    }


def _write_run_readme(output_dir: Path, aggregate: dict[str, Any]) -> None:
    """Write an inspectable run guide."""
    lines = [
        "# Personal Finance CFO Agent Stress Test Results",
        "",
        "Fictional/sample data only. No real personal financial data is used.",
        "",
        "## Summary",
        f"- Personas: {aggregate['persona_count']}",
        f"- Passed: {aggregate['passed']}",
        f"- Failed: {aggregate['failed']}",
        f"- Seed: {aggregate['seed']}",
        "",
        "## Files",
        "- `summary.csv` - one row per persona with high-level metrics.",
        "- `summary.json` - run metadata and coverage lists.",
        "- `personas/<persona_id>/input_transactions.csv` - generated fictional transactions.",
        "- `personas/<persona_id>/categorized_transactions.csv` - categorized output from the real pipeline.",
        "- `personas/<persona_id>/profile.json` - life stage, career, goals, assets, liabilities, budget, scenarios.",
        "- `personas/<persona_id>/step_results.json` - PASS/FAIL/TIMEOUT by pipeline step.",
        "- `personas/<persona_id>/tables/` - CSV/JSON outputs from each analysis module.",
        "- `personas/<persona_id>/report_summary.md` - human-readable one-person summary.",
        "",
        "## Coverage",
    ]
    for key, values in aggregate["coverage"].items():
        lines.append(f"- {key}: {', '.join(values)}")
    (output_dir / "README.md").write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run saved fictional-persona stress tests.")
    parser.add_argument("--count", type=int, default=100, help="Number of fictional personas to generate.")
    parser.add_argument("--seed", type=int, default=20260627, help="Deterministic generation seed.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where inspectable stress-test results should be written.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not delete an existing output directory before writing.",
    )
    return parser.parse_args()


def _is_replaceable_generated_run_dir(path: Path) -> bool:
    """Only child run directories under the stress-test root may be auto-replaced."""
    resolved_path = path.resolve()
    resolved_root = DEFAULT_OUTPUT_ROOT.resolve()
    return resolved_path != resolved_root and resolved_root in resolved_path.parents


def _remove_generated_output_dir(output_dir: Path) -> None:
    """Remove a generated stress-test directory, retrying macOS metadata races."""
    last_error = None
    for _ in range(3):
        try:
            shutil.rmtree(output_dir)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            for child in sorted(output_dir.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                try:
                    if child.is_dir() and not child.is_symlink():
                        child.rmdir()
                    else:
                        child.unlink(missing_ok=True)
                except OSError:
                    pass
            time.sleep(0.05)
    if output_dir.exists():
        raise SystemExit(f"Could not replace existing generated stress-test directory: {last_error}")


def _prepare_output_dir(output_dir: Path, keep_existing: bool) -> None:
    """Create the output directory, refusing unsafe implicit deletion."""
    if output_dir.exists() and not keep_existing:
        if output_dir.resolve() == DEFAULT_OUTPUT_ROOT.resolve():
            raise SystemExit(
                "Refusing to delete the stress-test root directory. "
                "Choose a child run directory under outputs/stress_tests/."
            )
        if not _is_replaceable_generated_run_dir(output_dir):
            raise SystemExit(
                "Refusing to delete existing custom output directory. "
                "Choose a new --output-dir, pass --keep-existing, or use a child run directory under outputs/stress_tests/."
            )
        _remove_generated_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    output_dir = args.output_dir
    if output_dir is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT_ROOT / f"run_{stamp}_{args.count}_personas"
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir = output_dir.resolve()

    _prepare_output_dir(output_dir, args.keep_existing)
    personas_dir = output_dir / "personas"
    personas_dir.mkdir(exist_ok=True)

    summary_rows = []
    for index in range(1, args.count + 1):
        persona = generate_persona(index, args.seed)
        persona_dir = personas_dir / persona["persona_id"]
        summary_rows.append(run_persona(persona, persona_dir))

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "summary.csv", index=False)
    aggregate = _aggregate_json(summary_rows, args.seed)
    (output_dir / "summary.json").write_text(json.dumps(_jsonable(aggregate), indent=2, ensure_ascii=False))
    _write_run_readme(output_dir, aggregate)

    print("Stress test complete")
    print(f"Personas: {aggregate['persona_count']} | Passed: {aggregate['passed']} | Failed: {aggregate['failed']}")
    print(f"Results: {output_dir}")
    if aggregate["failed"]:
        print("Failed personas:")
        for persona_id in aggregate["failed_personas"]:
            print(f"- {persona_id}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
