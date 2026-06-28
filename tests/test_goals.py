"""Tests for personal financial goal tracking."""

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.goals import track_goals


def test_savings_goal_on_track_when_contribution_covers_what_is_needed():
    goals = [{
        "name": "Emergency Fund", "type": "savings",
        "target_amount": 6000.0, "current_amount": 3000.0,
        "target_date": "2026-12-31", "monthly_contribution": 600.0,
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert row["Remaining"] == 3000.0
    assert row["Progress (%)"] == 50.0
    # 3000 remaining over 6 months = 500/mo needed; contributing 600 -> on track.
    assert row["Monthly Needed"] == 500.0
    assert row["Status"].startswith("🟢 On track")


def test_savings_goal_behind_when_contribution_too_small():
    goals = [{
        "name": "Down Payment", "type": "savings",
        "target_amount": 12000.0, "current_amount": 3000.0,
        "target_date": "2026-12-31", "monthly_contribution": 200.0,
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert row["Status"].startswith("🔴 Behind")


def test_savings_goal_achieved():
    goals = [{
        "name": "Vacation", "type": "savings",
        "target_amount": 2000.0, "current_amount": 2200.0,
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert row["Remaining"] == 0.0
    assert row["Progress (%)"] == 100.0
    assert row["Status"] == "✅ Achieved"


def test_debt_payoff_progress_uses_starting_balance():
    goals = [{
        "name": "Car Loan", "type": "debt_payoff",
        "target_amount": 0.0, "current_amount": 4000.0, "starting_amount": 8000.0,
        "interest_rate": 7.0, "monthly_contribution": 500.0,
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert row["Progress (%)"] == 50.0  # 4000 of 8000 paid down
    assert row["Status"].startswith("🟢 On track")


def test_debt_payoff_off_track_when_payment_below_interest():
    goals = [{
        "name": "Credit Card", "type": "debt_payoff",
        "target_amount": 0.0, "current_amount": 25000.0, "starting_amount": 25000.0,
        "interest_rate": 23.0, "monthly_contribution": 300.0,  # interest ~$479/mo
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert "Off track" in row["Status"]
    assert "below the" in row["Status"]


def test_savings_rate_goal_meeting_and_below():
    meeting = track_goals(
        [{"name": "Save 10%", "type": "savings_rate", "target_amount": 10.0, "current_amount": 12.0}],
        as_of_date="2026-06-30",
    ).iloc[0]
    assert meeting["Status"].startswith("✅ Meeting target")

    below = track_goals(
        [{"name": "Save 10%", "type": "savings_rate", "target_amount": 10.0, "current_amount": 4.0}],
        as_of_date="2026-06-30",
    ).iloc[0]
    assert below["Status"].startswith("🔴 Below target")


def test_net_worth_goal_progress_and_behind_when_date_passed():
    goals = [{
        "name": "Positive Net Worth", "type": "net_worth",
        "target_amount": 0.0, "current_amount": -5000.0, "target_date": "2026-01-31",
    }]
    row = track_goals(goals, as_of_date="2026-06-30").iloc[0]
    assert row["Remaining"] == 5000.0
    assert "Behind" in row["Status"]  # target date already passed


def test_unknown_goal_type_raises():
    with pytest.raises(ValueError, match="Unknown goal type"):
        track_goals([{"name": "X", "type": "retirement", "target_amount": 1, "current_amount": 0}],
                    as_of_date="2026-06-30")


def test_sample_alex_goals_track_without_error():
    from modules.config import ALEX_GOALS

    tracker = track_goals(ALEX_GOALS, as_of_date="2026-03-31", default_monthly=400.0)
    assert len(tracker) == len(ALEX_GOALS)
    assert set(tracker["Type"]) == {"savings", "debt_payoff", "net_worth", "savings_rate"}
