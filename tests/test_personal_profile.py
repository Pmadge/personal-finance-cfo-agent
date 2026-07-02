"""Tests for loading the local personal financial profile."""

from pathlib import Path
import json
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.personal_profile import DEFAULT_PROFILE_PATH, build_onboarding_profile, load_personal_profile, write_personal_profile
from modules.config import SAMPLE_PERSONAL_PROFILE


def test_falls_back_to_sample_when_no_local_file(tmp_path):
    profile = load_personal_profile(tmp_path / "does_not_exist.json")
    assert profile["goals"] == SAMPLE_PERSONAL_PROFILE["goals"]
    # A copy, not the shared constant, so callers can mutate safely.
    assert profile is not SAMPLE_PERSONAL_PROFILE


def test_loads_local_profile_when_present(tmp_path):
    custom = {
        "assets": {"Checking": 100.0, "Savings": 200.0, "Investments": 0.0},
        "liabilities": {},
        "goals": [{"name": "Test", "type": "savings", "target_amount": 1000.0, "current_amount": 250.0}],
        "scenarios": [{"name": "Raise", "monthly_income_change": 100.0}],
        "home_target": {"home_price": 200000.0},
    }
    path = tmp_path / "personal_profile.json"
    path.write_text(json.dumps(custom))
    profile = load_personal_profile(path)
    assert profile["assets"]["Checking"] == 100.0
    # Optional fields get filled with safe defaults.
    assert profile["monthly_debt_payment"] == 300.0
    assert profile["major_purchase"] == 0.0


def test_missing_required_keys_raises(tmp_path):
    path = tmp_path / "personal_profile.json"
    path.write_text(json.dumps({"assets": {}}))  # missing liabilities/goals/scenarios/home_target
    with pytest.raises(ValueError, match="missing required keys"):
        load_personal_profile(path)


def test_committed_example_profile_is_valid():
    example = PROJECT_ROOT / "config" / "personal_profile.example.json"
    assert example.exists()
    profile = load_personal_profile(example)  # should load and validate without error
    assert set(["assets", "liabilities", "goals", "scenarios", "home_target"]).issubset(profile)


def test_default_profile_path_is_local_and_gitignored():
    # The real profile path is the local config file, not the example template.
    assert DEFAULT_PROFILE_PATH.name == "personal_profile.json"


def test_build_onboarding_profile_creates_valid_local_baseline():
    profile = build_onboarding_profile(
        household_name="Test Household",
        current_state="Building emergency fund",
        checking=100,
        savings=500,
        investments=250,
        credit_card_debt=300,
        monthly_debt_payment=50,
        primary_goal="Move fund",
        primary_goal_target=2000,
        primary_goal_current=100,
        emergency_fund_target=1000,
        savings_rate_target=15,
        target_date="2027-01-01",
    )

    assert profile["household"]["name"] == "Test Household"
    assert profile["assets"]["Savings"] == 500.0
    assert profile["liabilities"]["Credit Card"]["balance"] == 300.0
    assert {goal["name"] for goal in profile["goals"]} >= {"Emergency Fund", "Move fund", "Pay Down Debt"}
    assert set(["assets", "liabilities", "goals", "scenarios", "home_target"]).issubset(profile)


def test_build_onboarding_profile_has_no_default_money_or_goal_answers():
    profile = build_onboarding_profile()

    assert profile["assets"] == {"Checking": 0.0, "Savings": 0.0, "Investments": 0.0}
    assert profile["liabilities"] == {}
    assert profile["goals"] == []
    assert profile["home_target"] == {"home_price": 0.0, "down_payment_pct": 0.0, "mortgage_rate": 0.0, "term_years": 30}


def test_write_personal_profile_round_trips_onboarding_profile(tmp_path):
    path = tmp_path / "personal_profile.json"
    profile = build_onboarding_profile(household_name="Round Trip", savings=1000, emergency_fund_target=2000)

    written = write_personal_profile(profile, path)
    loaded = load_personal_profile(written)

    assert loaded["household"]["name"] == "Round Trip"
    assert loaded["assets"]["Savings"] == 1000.0
