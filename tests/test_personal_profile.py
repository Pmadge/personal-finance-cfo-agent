"""Tests for loading the local personal financial profile."""

from pathlib import Path
import json
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.personal_profile import DEFAULT_PROFILE_PATH, load_personal_profile
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
