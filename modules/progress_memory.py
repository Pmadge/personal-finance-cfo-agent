"""Local progress history for generated personal CFO reports."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from modules.analytics import monthly_summary
from modules.forecast import cash_runway
from modules.goals import track_goals
from modules.net_worth import net_worth_snapshot
from modules.personal_profile import load_personal_profile
from modules.risk import build_risk_register

SCHEMA_VERSION = "1.0.0"
NUMERIC_METRICS = [
    "net_cash_flow",
    "savings_rate",
    "net_worth",
    "emergency_runway_months",
    "debt_total",
    "high_risks",
]


def build_progress_snapshot(report_df, *, profile=None, report_path=None, run_timestamp=None) -> dict:
    """Return one deterministic progress snapshot from report-ready rows."""
    profile = profile or load_personal_profile()
    report_df = report_df.copy()
    report_df["date"] = pd.to_datetime(report_df["date"])
    period = report_df["date"].dt.to_period("M").astype(str).max()
    summary = monthly_summary(report_df, period)
    assets = profile["assets"]
    liabilities = profile["liabilities"]
    liquid_cash = float(assets.get("Checking", 0.0)) + float(assets.get("Savings", 0.0))
    net_worth = net_worth_snapshot(assets, liabilities)
    runway = cash_runway(report_df, liquid_cash)
    risks = build_risk_register(report_df, assets, liabilities, liquid_cash)
    goals = _goals_for_snapshot(profile, net_worth["Net Worth"], summary["Savings Rate"], summary["Net Cash Flow"], period)

    return {
        "run_timestamp": run_timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "period": period,
        "report_file": Path(report_path).name if report_path else "",
        "metrics": {
            "net_cash_flow": _round(summary["Net Cash Flow"]),
            "savings_rate": _round(summary["Savings Rate"]),
            "net_worth": _round(net_worth["Net Worth"]),
            "emergency_runway_months": _round(runway.get("Emergency Runway (months)")),
            "debt_total": _round(_debt_total(liabilities)),
            "high_risks": int(sum("High" in str(level) for level in risks["Level"])),
        },
        "goals": goals,
        # ponytail: no separate action-item engine exists for personal reports yet; wire it when reports produce actions.
        "action_items": [],
    }


def append_progress_snapshot(history_path, snapshot: dict) -> dict:
    """Append one snapshot to a local JSON manifest and return the manifest."""
    history_path = Path(history_path)
    if history_path.exists():
        manifest = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        manifest = {"schema_version": SCHEMA_VERSION, "snapshots": [], "latest_comparison": {}}
    manifest.setdefault("schema_version", SCHEMA_VERSION)
    manifest.setdefault("snapshots", []).append(snapshot)
    manifest["latest_comparison"] = _compare_latest(manifest["snapshots"])
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def _goals_for_snapshot(profile, net_worth_value, savings_rate, monthly_net, period) -> list[dict]:
    goals = [dict(goal) for goal in profile.get("goals", [])]
    for goal in goals:
        if goal.get("type") == "net_worth":
            goal["current_amount"] = net_worth_value
        elif goal.get("type") == "savings_rate":
            goal["current_amount"] = savings_rate
    if not goals:
        return []
    goal_df = track_goals(goals, as_of_date=f"{period}-28", default_monthly=monthly_net)
    return [
        {
            "goal": str(row["Goal"]),
            "status": str(row["Status"]),
            "progress_pct": _round(row["Progress (%)"]),
        }
        for _, row in goal_df.iterrows()
    ]


def _debt_total(liabilities: dict) -> float:
    total = 0.0
    for value in liabilities.values():
        total += float(value.get("balance", 0.0) if isinstance(value, dict) else value)
    return total


def _compare_latest(snapshots: list[dict]) -> dict:
    if len(snapshots) < 2:
        return {}
    previous = snapshots[-2].get("metrics", {})
    current = snapshots[-1].get("metrics", {})
    changes = {}
    for key in NUMERIC_METRICS:
        prior_value = previous.get(key)
        current_value = current.get(key)
        # Metrics can legitimately be None (e.g. runway with no recurring
        # expenses); a change against None is unknowable, not zero.
        if prior_value is None or current_value is None:
            changes[f"{key}_change"] = None
        else:
            changes[f"{key}_change"] = _round(float(current_value) - float(prior_value))
    return changes


def _round(value):
    if value is None:
        return None
    return round(float(value), 2)
