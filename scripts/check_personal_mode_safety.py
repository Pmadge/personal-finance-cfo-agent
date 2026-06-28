"""Run local checks required before future personal mode work."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.personal_mode_safety import assert_private_paths_gitignored


def main():
    result = assert_private_paths_gitignored(PROJECT_ROOT)
    print("Personal mode safety gate passed.")
    print("Verified these local private paths are Git-ignored:")
    for path in result["checked_paths"]:
        print(f"- {path}")
    print("This does not enable real-data import yet.")


if __name__ == "__main__":
    main()
