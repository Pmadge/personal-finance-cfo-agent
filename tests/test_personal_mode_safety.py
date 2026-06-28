"""Tests for the real-data safety gate before personal mode is enabled."""

from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_private_local_paths_are_git_ignored_by_git_itself():
    """The safety gate should prove private paths are ignored using Git, not string matching."""
    from modules.personal_mode_safety import assert_private_paths_gitignored

    result = assert_private_paths_gitignored(PROJECT_ROOT)

    assert result["passed"] is True
    assert set(result["checked_paths"]) == {
        "data/personal/example.csv",
        "data/processed/example.csv",
        "outputs/personal/report.pdf",
        "outputs/personal/charts/chart.png",
        "config/personal_rules.csv",
        "config/personal_profile.json",
    }


def test_private_gitignore_gate_fails_closed_when_a_path_is_not_ignored(tmp_path):
    """A repo that forgets one private rule should not pass personal-mode safety."""
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    subprocess.run(["git", "init"], cwd=fake_repo, check=True, capture_output=True, text=True)
    (fake_repo / ".gitignore").write_text("data/personal/*\n")

    from modules.personal_mode_safety import assert_private_paths_gitignored

    with pytest.raises(RuntimeError, match="Private paths are not Git-ignored"):
        assert_private_paths_gitignored(fake_repo)


def test_personal_report_audit_gate_requires_clean_review_and_passed_self_check():
    """Real personal reports should only unlock after review and self-checks are clean."""
    from modules.personal_mode_safety import assert_personal_report_audit_ready
    from modules.workflow_audit import VALID_PRIVACY_STATUS

    audit = {
        "mode": "personal",
        "needs_review_count": 0,
        "self_check_status": "PASS",
        "privacy_status": VALID_PRIVACY_STATUS,
        "output_paths": ["outputs/personal/2026-06/personal_cfo_report.pdf"],
    }

    assert_personal_report_audit_ready(audit)


@pytest.mark.parametrize(
    "field,value,expected_message",
    [
        ("mode", "sample", "mode must be personal"),
        ("needs_review_count", 1, "needs_review_count must be 0"),
        ("self_check_status", "NOT_RUN", "self_check_status must be PASS"),
        ("privacy_status", "unknown", "privacy_status must be local_only_gitignored_outputs"),
        ("output_paths", ["docs/private_report.pdf"], "output_paths must stay under outputs/personal"),
    ],
)
def test_personal_report_audit_gate_rejects_unsafe_audit_states(field, value, expected_message):
    """Any unsafe audit state should block future real personal report generation."""
    from modules.personal_mode_safety import assert_personal_report_audit_ready
    from modules.workflow_audit import VALID_PRIVACY_STATUS

    audit = {
        "mode": "personal",
        "needs_review_count": 0,
        "self_check_status": "PASS",
        "privacy_status": VALID_PRIVACY_STATUS,
        "output_paths": ["outputs/personal/2026-06/personal_cfo_report.pdf"],
    }
    audit[field] = value

    with pytest.raises(RuntimeError, match=expected_message):
        assert_personal_report_audit_ready(audit)
