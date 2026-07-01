"""Tests for the beginner-friendly personal setup command."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.setup_personal import EXAMPLE_PROFILE, ensure_local_profile, run_setup
import scripts.setup_personal as setup_personal


def test_creates_local_profile_from_example_when_absent(tmp_path):
    example = tmp_path / "example.json"
    example.write_text('{"assets": {}}')
    profile = tmp_path / "personal_profile.json"

    assert ensure_local_profile(example, profile) == "created"
    assert profile.exists()
    assert profile.read_text() == example.read_text()


def test_never_overwrites_an_existing_local_profile(tmp_path):
    example = tmp_path / "example.json"
    example.write_text('{"assets": {"Checking": 1.0}}')
    profile = tmp_path / "personal_profile.json"
    profile.write_text('{"mine": true}')

    assert ensure_local_profile(example, profile) == "exists"
    assert profile.read_text() == '{"mine": true}'  # unchanged


def test_run_setup_creates_profile_and_confirms_safety(tmp_path):
    # Real repo root for the Git-ignore safety gate; temp path for the profile so
    # the test never writes into the tracked config directory.
    profile = tmp_path / "personal_profile.json"
    result = run_setup(project_root=PROJECT_ROOT, example_path=EXAMPLE_PROFILE, profile_path=profile)

    assert result["profile_state"] == "created"
    assert result["private_paths_protected"] is True
    assert profile.exists()


def test_run_setup_checks_gitignore_before_creating_profile(tmp_path, monkeypatch):
    profile = tmp_path / "personal_profile.json"

    def fail_safety(_project_root):
        raise RuntimeError("not ignored")

    monkeypatch.setattr(setup_personal, "assert_private_paths_gitignored", fail_safety)

    try:
        run_setup(project_root=PROJECT_ROOT, example_path=EXAMPLE_PROFILE, profile_path=profile)
    except RuntimeError:
        pass

    assert not profile.exists()
