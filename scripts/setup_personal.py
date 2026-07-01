"""Beginner-friendly setup for your own local, private CFO profile.

One command to get started:

    python3 scripts/setup_personal.py

What it does, in plain English:
1. Confirms your private files are Git-ignored, so nothing personal can be
   committed by accident.
2. Creates a local `config/personal_profile.json` (copied from the committed
   example) if you do not have one yet. That file holds your assets, debts,
   goals, what-if scenarios, and a home target. It is Git-ignored and never
   leaves your Mac.
3. Prints exactly what to do next.

It does not connect to any bank, import real transactions, or write anything
outside the project's local config. Transaction data stays fictional/sample
until a real import workflow is explicitly approved.
"""

from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.personal_mode_safety import assert_private_paths_gitignored

EXAMPLE_PROFILE = PROJECT_ROOT / "config" / "personal_profile.example.json"
LOCAL_PROFILE = PROJECT_ROOT / "config" / "personal_profile.json"


def ensure_local_profile(example_path=EXAMPLE_PROFILE, profile_path=LOCAL_PROFILE):
    """Create the local profile from the example if it does not exist yet.

    Returns "created" or "exists". Never overwrites an existing local profile.
    """
    profile_path = Path(profile_path)
    if profile_path.exists():
        return "exists"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, profile_path)
    return "created"


def run_setup(project_root=PROJECT_ROOT, example_path=EXAMPLE_PROFILE, profile_path=LOCAL_PROFILE):
    """Run the setup steps and return a summary dict (no printing).

    Raises RuntimeError via the safety gate if any private path is not Git-ignored.
    """
    safety = assert_private_paths_gitignored(project_root)
    profile_state = ensure_local_profile(example_path, profile_path)
    try:
        display_path = str(Path(profile_path).relative_to(Path(project_root)))
    except ValueError:
        display_path = str(profile_path)
    return {
        "profile_state": profile_state,
        "profile_path": display_path,
        "private_paths_protected": bool(safety.get("passed", True)),
    }


def main():
    result = run_setup()
    print("Personal CFO setup")
    print("==================")
    if result["profile_state"] == "created":
        print(f"Created your local profile: {result['profile_path']}")
        print("  Replace the example numbers with your own assets, debts, goals, and scenarios.")
    else:
        print(f"Found your local profile: {result['profile_path']} (left unchanged).")
    print("Private files are Git-ignored: your profile and any personal data stay on this Mac only.")
    print("")
    print("Next steps:")
    print("  1. Edit config/personal_profile.json with your own numbers (it is local and private).")
    print("  2. Generate your report:")
    print("       python3 scripts/monthly_close.py --sample")
    print("       python3 scripts/generate_personal_report.py")
    print("  3. Open it: outputs/personal/personal_cfo_report_draft.pdf")
    print("")
    print("Reminder: transaction data is still fictional/sample until a real import workflow is approved.")


if __name__ == "__main__":
    main()
