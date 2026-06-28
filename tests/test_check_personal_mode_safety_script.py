"""Tests for the personal-mode safety check command."""

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "check_personal_mode_safety.py"


def test_check_personal_mode_safety_script_verifies_local_private_paths():
    """The safety check command should prove local private paths are Git-ignored."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Personal mode safety gate passed" in result.stdout
    assert "data/personal/example.csv" in result.stdout
    assert "outputs/personal/report.pdf" in result.stdout
    assert "This does not enable real-data import yet" in result.stdout
