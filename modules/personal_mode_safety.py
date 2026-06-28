"""Safety gates for future real personal-data mode.

This module does not enable real-data import. It only centralizes the checks that
must pass before a future personal workflow can write reports from private data.
"""

from pathlib import Path
import subprocess

from modules.workflow_audit import VALID_PRIVACY_STATUS, validate_safe_listed_output_path

PRIVATE_PATH_CHECKS = [
    "data/personal/example.csv",
    "data/processed/example.csv",
    "outputs/personal/report.pdf",
    "outputs/personal/charts/chart.png",
    "config/personal_rules.csv",
]


def assert_private_paths_gitignored(project_root):
    """Fail closed unless Git ignores every private local-data path."""
    project_root = Path(project_root)
    command = ["git", "check-ignore", *PRIVATE_PATH_CHECKS]
    result = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    ignored = set(result.stdout.splitlines())
    missing = [path for path in PRIVATE_PATH_CHECKS if path not in ignored]
    if missing:
        raise RuntimeError(
            "Private paths are not Git-ignored: " + ", ".join(missing)
        )
    return {"passed": True, "checked_paths": list(PRIVATE_PATH_CHECKS)}


def assert_personal_report_audit_ready(audit):
    """Fail closed unless an audit record is clean enough for future personal reports."""
    if audit.get("mode") != "personal":
        raise RuntimeError("mode must be personal before generating real personal reports")
    if audit.get("needs_review_count") != 0:
        raise RuntimeError("needs_review_count must be 0 before generating real personal reports")
    if audit.get("self_check_status") != "PASS":
        raise RuntimeError("self_check_status must be PASS before generating real personal reports")
    if audit.get("privacy_status") != VALID_PRIVACY_STATUS:
        raise RuntimeError(
            f"privacy_status must be {VALID_PRIVACY_STATUS} before generating real personal reports"
        )

    output_paths = audit.get("output_paths")
    if not isinstance(output_paths, list) or not output_paths:
        raise RuntimeError("output_paths must list at least one personal report output")
    if any(not validate_safe_listed_output_path(path) for path in output_paths):
        raise RuntimeError("output_paths must stay under outputs/personal")

    return True
