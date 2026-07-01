"""Repo-facing test persona artifact layout checks."""

from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_tracked_persona_files_use_generic_folder_names():
    """Public sample file paths should be reusable, not named after one persona/date."""
    tracked = subprocess.check_output(["git", "ls-files"], cwd=PROJECT_ROOT, text=True).splitlines()
    data_and_report_paths = [
        path
        for path in tracked
        if path.startswith(("data/", "test_personas/", "outputs/"))
    ]

    forbidden = ("alex", "rivera", "morgan", "patel", "2026_03", "2026-q1", "2026_q1")
    offenders = [path for path in data_and_report_paths if any(token in path.lower() for token in forbidden)]

    assert offenders == []


def test_each_test_persona_has_full_run_outputs():
    """Each committed test persona should include inspectable local run artifacts."""
    personas_root = PROJECT_ROOT / "test_personas"
    persona_dirs = sorted(path for path in personas_root.iterdir() if path.is_dir())

    assert [path.name for path in persona_dirs] == ["complex_household", "starter_person"]
    for persona_dir in persona_dirs:
        assert (persona_dir / "transactions.csv").exists()
        assert (persona_dir / "transactions_categorized.csv").exists()
        assert (persona_dir / "outputs" / "monthly_cfo_report.pdf").exists()
        assert (persona_dir / "outputs" / "report.json").exists()

    assert (personas_root / "starter_person" / "outputs" / "three_month_trend_summary.pdf").exists()
