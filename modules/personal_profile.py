"""Load a local personal financial profile for the personal report.

The personal report's pillar suite (runway, goals, scenarios, risk, capital
events) needs financial inputs beyond transactions: assets, liabilities, goals,
what-if scenarios, and a home target. This loader returns those from a local,
Git-ignored JSON file (`config/personal_profile.json`) when the user has created
one, and otherwise falls back to the fictional SAMPLE_PERSONAL_PROFILE so the demo
keeps working. The committed `config/personal_profile.example.json` documents the
expected shape.

Keeping the real profile local-only and Git-ignored follows the project's
privacy rules; nothing here enables real bank data or transaction import.
"""

import copy
import json
from pathlib import Path

from modules.config import SAMPLE_PERSONAL_PROFILE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "config" / "personal_profile.json"
REQUIRED_KEYS = ("assets", "liabilities", "goals", "scenarios", "home_target")


def load_personal_profile(path=None):
    """Return the local profile JSON when present and valid, else the sample profile.

    Raises ValueError if a profile file exists but is missing required keys, so a
    malformed profile fails clearly instead of producing a confusing report.
    """
    profile_path = Path(path) if path is not None else DEFAULT_PROFILE_PATH
    if not profile_path.exists():
        return copy.deepcopy(SAMPLE_PERSONAL_PROFILE)

    with open(profile_path, encoding="utf-8") as handle:
        profile = json.load(handle)

    missing = [key for key in REQUIRED_KEYS if key not in profile]
    if missing:
        raise ValueError(
            f"Personal profile {profile_path.name} is missing required keys: "
            f"{', '.join(missing)}"
        )

    # Optional fields get safe defaults so the report sections always render.
    profile.setdefault("monthly_debt_payment", 300.0)
    profile.setdefault("major_purchase", 0.0)
    return profile
