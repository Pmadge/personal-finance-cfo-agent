"""Stable JSON contract for the Personal Finance CFO Agent UI layer.

The deterministic Python engine owns every number. This module serializes the
already-computed report data into a single stable JSON object that a UI (Streamlit
now, possibly React/Tauri later) can bind to without recomputing anything.

Design rules baked in here:
- The engine calculates; the JSON only reports verified results.
- No local filesystem paths leak into the JSON (privacy-first). Source artifacts
  are referenced by basename only.
- Every numeric value is a native Python type so the JSON is portable.
- A ``schema_version`` lets the UI guard against drift.
- AI text is never produced here; this contract is engine-verified data only.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from modules.config import MODEL_VERSION, REPORT_MONTH, REPORT_MONTH_LABEL
from modules.reports.pdf_report import collect_report_data, resolve_report_config

# Bump when the shape of the contract changes in a way the UI must handle.
REPORT_JSON_SCHEMA_VERSION = "1.0.0"


def _clean(value):
    """Convert pandas/numpy scalars into JSON-safe native Python values."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.ndarray,)):
        return [_clean(item) for item in value.tolist()]
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-safe records."""
    if df is None or len(df) == 0:
        return []
    return [{str(col): _clean(row[col]) for col in df.columns} for _, row in df.iterrows()]


def _clean_dict(data: dict) -> dict:
    """Return a JSON-safe copy of a flat dict of computed values."""
    return {str(key): _clean(val) for key, val in data.items()}


def build_report_json(output_dir=None, report_config=None) -> dict:
    """Build the stable report JSON contract from the deterministic engine.

    The numbers come straight from ``collect_report_data`` so the JSON can never
    disagree with the PDF or dashboard. Local paths are intentionally excluded.
    """
    report_config = resolve_report_config(report_config)
    data = collect_report_data(output_dir=output_dir, report_config=report_config)

    summary = data["summary"]
    runway = data["runway"]
    net_worth = data["net_worth"]
    goals = _records(data["goal_df"])
    risks = _records(data["risk_df"])
    actions = _records(data["action_df"])

    # Derive the headline numbers the Home Dashboard needs in <10 seconds.
    risk_levels = [str(r.get("Level", "")) for r in risks]
    risk_counts = {
        "high": sum(1 for level in risk_levels if "High" in level),
        "medium": sum(1 for level in risk_levels if "Medium" in level),
        "low": sum(1 for level in risk_levels if "Low" in level),
    }
    top_goal = goals[0] if goals else None
    top_action = actions[0] if actions else None
    # The top risk is the first High, else first Medium, else first listed.
    top_risk = next((r for r in risks if "High" in str(r.get("Level", ""))), None)
    if top_risk is None:
        top_risk = next((r for r in risks if "Medium" in str(r.get("Level", ""))), None)
    if top_risk is None and risks:
        top_risk = risks[0]

    audit_records = _records(data["audit_df"])
    # INFO rows are contextual (input file, row count, months covered), not checks.
    check_records = [row for row in audit_records
                     if str(row.get("Status", "")).strip().upper() != "INFO"]
    passed_checks = sum(1 for row in check_records
                        if str(row.get("Status", "")).strip().upper() in {"PASS", "OK", "GREEN"})
    total_checks = len(check_records)

    rent_buy = _clean_dict(data["rent_vs_buy"])
    home = _clean_dict(data["home_readiness"])

    contract = {
        "schema_version": REPORT_JSON_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": {
            "model_version": MODEL_VERSION,
            "deterministic": True,
            "ai_generated": False,
            "note": "All numbers are calculated by the deterministic Python engine. No AI wrote these values.",
        },
        "persona": {
            "name": report_config["persona_name"],
            "fictional_notice": report_config["fictional_notice"],
            "sample_data_only": True,
        },
        "period": {
            "month": REPORT_MONTH,
            "label": REPORT_MONTH_LABEL,
        },
        "privacy": {
            "mode": "sample",
            "real_data_enabled": False,
            "local_only": True,
            "bank_login": False,
            "cloud_sync": False,
            "cloud_ai": False,
            "local_ai_enabled": False,
        },
        "self_check": {
            "checks_passed": passed_checks,
            "checks_total": total_checks,
            "all_passed": total_checks > 0 and passed_checks == total_checks,
        },
        "headline": {
            "verdict": _verdict(summary, runway, risk_counts),
            "net_cash_flow": _clean(summary["Net Cash Flow"]),
            "savings_rate": _clean(summary["Savings Rate"]),
            "emergency_runway_months": _clean(runway.get("Emergency Runway (months)")),
            "runway_status": runway.get("Status"),
            "net_worth": _clean(net_worth["Net Worth"]),
            "risk_counts": risk_counts,
            "top_risk": top_risk,
            "top_goal": top_goal,
            "next_action": top_action,
            "rent_vs_buy": {
                "recommendation": rent_buy.get("recommendation"),
                "cheaper": rent_buy.get("cheaper"),
                "horizon_years": rent_buy.get("horizon_years"),
            },
        },
        "sections": {
            "summary": _clean_dict(summary),
            "cash_flow": {
                "income": _clean(summary["Income"]),
                "total_expenses": _clean(summary["Total Expenses"]),
                "net_cash_flow": _clean(summary["Net Cash Flow"]),
                "savings_rate": _clean(summary["Savings Rate"]),
            },
            "runway": _clean_dict(runway),
            "projection": _records(data["projection_df"]),
            "budget_vs_actual": _records(data["budget_df"]),
            "cumulative_budget": _records(data["cumulative_budget_df"]),
            "recurring_vendors": _records(data["recurring_df"]),
            "unusual_expenses": _records(data["unusual_df"]),
            "upcoming_obligations": _records(data["upcoming_df"]),
            "net_worth": _clean_dict(net_worth),
            "debt_payoff": _records(data["debt_df"]),
            "goals": goals,
            "risk_register": risks,
            "risk_overall": data["risk_overall"],
            "home_purchase_readiness": home,
            "major_purchase": _clean_dict(data["major_purchase"]),
            "rent_vs_buy": rent_buy,
            "scorecard": _records(data["scorecard_df"]),
            "action_items": actions,
            "forecast": _records(data["forecast_df"]),
            "self_checks": audit_records,
        },
        "sources": {
            "artifacts": [
                "report.json",
                Path(report_config["pdf_path"]).name,
            ],
            "note": "Source artifacts are referenced by basename only; no local paths are exposed.",
        },
    }
    return contract


def _verdict(summary: dict, runway: dict, risk_counts: dict) -> str:
    """Produce a short engine-derived verdict string (deterministic, not AI)."""
    net = float(summary["Net Cash Flow"])
    months = runway.get("Emergency Runway (months)")
    high = risk_counts["high"]
    if net <= 0:
        return "Attention needed"
    if high > 0 or (months is not None and float(months) < 3):
        return "On track, with risks to watch"
    return "On track"


def write_report_json(path, output_dir=None, report_config=None) -> Path:
    """Build the contract and write it to ``path`` as pretty JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    contract = build_report_json(output_dir=output_dir, report_config=report_config)
    path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    return path
