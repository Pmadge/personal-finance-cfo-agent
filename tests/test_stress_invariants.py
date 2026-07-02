"""Tests for the stress harness value-invariant guard.

A guard that never fires is worthless, so these prove it catches the silent
failure modes (broken reconciliation, infinite values, dropped housing) while
passing clean output.
"""

from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.stress_test_personas import _check_value_invariants, generate_persona, run_persona


def test_invariants_pass_on_clean_outputs():
    outputs = {
        "monthly_summary": {"Income": 3000.0, "Total Expenses": 2000.0, "Net Cash Flow": 1000.0, "Savings Rate": 33.3},
        "cash_runway": {"Emergency Runway (months)": 6.0, "Essential Monthly Bills": 1500.0},
    }
    assert _check_value_invariants({}, None, outputs)["checks_passed"]


def test_invariants_catch_broken_reconciliation():
    outputs = {"monthly_summary": {"Income": 3000.0, "Total Expenses": 2000.0, "Net Cash Flow": 500.0, "Savings Rate": 16.0}}
    with pytest.raises(AssertionError, match="net"):
        _check_value_invariants({}, None, outputs)


def test_invariants_catch_infinite_forecast_value():
    forecast = pd.DataFrame([{"Ending Cash": float("inf"), "Net Cash Flow": 100.0}])
    with pytest.raises(AssertionError, match="infinite"):
        _check_value_invariants({}, None, {"forecast_cash_flow": forecast})


def test_invariants_catch_dropped_housing_in_runway():
    df = pd.DataFrame([{"assigned_category": "Housing", "amount": -1000.0, "date": "2026-03-03", "vendor": "Rent"}])
    outputs = {"cash_runway": {"Emergency Runway (months)": 5.0, "Essential Monthly Bills": 0.0}}
    with pytest.raises(AssertionError, match="rent dropped"):
        _check_value_invariants({}, df, outputs)


def test_invariants_catch_too_many_action_items():
    actions = pd.DataFrame([{"Evaluation": "PASS"}] * 4)
    with pytest.raises(AssertionError, match="more than 3"):
        _check_value_invariants({}, None, {"action_items": actions})


def test_stress_persona_writes_full_report(tmp_path):
    persona = generate_persona(index=1, seed=20260627)
    summary = run_persona(persona, tmp_path / persona["persona_id"])

    report = tmp_path / persona["persona_id"] / "full_report.md"
    text = report.read_text()
    assert summary["status"] == "PASS"
    assert "# Full CFO Stress Report" in text
    assert "## Prioritized action items" in text
    assert "## Budget vs actual" in text
    assert "tables/" in text
