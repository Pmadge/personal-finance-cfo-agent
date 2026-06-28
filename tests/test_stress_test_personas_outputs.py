"""Tests for saved multi-persona stress-test outputs."""

from pathlib import Path
import json
import subprocess
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_stress_test_personas_refuses_to_delete_existing_custom_output_dir(tmp_path):
    """A mistyped existing custom --output-dir should not be deleted by default."""
    output_dir = tmp_path / "existing_custom_results"
    output_dir.mkdir()
    marker = output_dir / "do_not_delete.txt"
    marker.write_text("keep me")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/stress_test_personas.py",
            "--count",
            "1",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to delete existing custom output directory" in result.stderr
    assert marker.exists()
    assert marker.read_text() == "keep me"


def test_stress_test_personas_refuses_to_replace_stress_tests_root():
    """The generated stress-test root itself should not be deleted by accident."""
    output_dir = PROJECT_ROOT / "outputs" / "stress_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "do_not_delete_root.txt"
    marker.write_text("keep root")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/stress_test_personas.py",
                "--count",
                "1",
                "--output-dir",
                str(output_dir),
                "--seed",
                "456",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode != 0
        assert "Refusing to delete the stress-test root directory" in result.stderr
        assert marker.exists()
        assert marker.read_text() == "keep root"
    finally:
        marker.unlink(missing_ok=True)


def test_stress_test_personas_replaces_existing_generated_stress_dir():
    """Generated stress-test run folders under outputs/stress_tests may be safely replaced."""
    output_dir = PROJECT_ROOT / "outputs" / "stress_tests" / "pytest_replace_existing"
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "old_file.txt"
    marker.write_text("old")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/stress_test_personas.py",
                "--count",
                "1",
                "--output-dir",
                str(output_dir),
                "--seed",
                "456",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        assert "Stress test complete" in result.stdout
        assert not marker.exists()
        assert (output_dir / "summary.csv").exists()
        assert len(pd.read_csv(output_dir / "summary.csv")) == 1
    finally:
        if output_dir.exists():
            import shutil

            shutil.rmtree(output_dir, ignore_errors=True)


def test_stress_test_personas_writes_inspectable_results(tmp_path):
    """The stress harness should save per-persona and aggregate outputs."""
    output_dir = tmp_path / "stress_results"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/stress_test_personas.py",
            "--count",
            "3",
            "--output-dir",
            str(output_dir),
            "--seed",
            "123",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Stress test complete" in result.stdout
    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "personas").exists()

    summary = pd.read_csv(output_dir / "summary.csv")
    assert len(summary) == 3
    assert bool(summary["status"].eq("PASS").all())
    assert bool(summary["persona_id"].is_unique)
    assert {"life_stage", "career", "wealth_profile", "spending_style"}.issubset(summary.columns)

    aggregate = json.loads((output_dir / "summary.json").read_text())
    assert aggregate["persona_count"] == 3
    assert aggregate["passed"] == 3
    assert aggregate["failed"] == 0
    assert len(aggregate["coverage"]["life_stages"]) >= 2
    assert len(aggregate["coverage"]["wealth_profiles"]) >= 2
    assert len(aggregate["coverage"]["spending_styles"]) >= 2
    assert len(aggregate["coverage"]["plan_types"]) >= 2

    expected_tables = {
        "monthly_summary.json",
        "budget_vs_actual.csv",
        "forecast_cash_flow.csv",
        "cash_runway.json",
        "scenarios.csv",
        "risk_register.csv",
        "scorecard.csv",
        "goals.csv",
        "action_items.csv",
        "net_worth.json",
    }

    for persona_id in summary["persona_id"]:
        persona_dir = output_dir / "personas" / persona_id
        assert (persona_dir / "input_transactions.csv").exists()
        assert (persona_dir / "categorized_transactions.csv").exists()
        assert (persona_dir / "step_results.json").exists()
        assert (persona_dir / "profile.json").exists()
        assert (persona_dir / "report_summary.md").exists()
        step_results = json.loads((persona_dir / "step_results.json").read_text())
        assert step_results
        assert {step["status"] for step in step_results} == {"PASS"}
        table_names = {path.name for path in (persona_dir / "tables").iterdir()}
        assert expected_tables.issubset(table_names)
