"""Read & Trust models for the local Streamlit app.

The UI layer is intentionally read-only. It loads the stable report JSON contract,
checks the trust gates, then formats values for display. It does not calculate
new financial numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA_VERSION = "1.0.0"
APPROVED_PRIVACY_FLAGS = {
    "mode": "sample",
    "real_data_enabled": False,
    "local_only": True,
    "bank_login": False,
    "cloud_sync": False,
    "cloud_ai": False,
    "local_ai_enabled": False,
}


class ContractTrustError(RuntimeError):
    """Raised when a report JSON should not be trusted by the UI."""


def load_report_contract(path: str | Path) -> dict[str, Any]:
    """Load and validate a CFO report JSON contract."""
    report_path = Path(path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    validate_report_contract(data)
    return data


def validate_report_contract(data: dict[str, Any]) -> None:
    """Fail closed unless the report is verified, sample-only, and local-only."""
    if data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ContractTrustError("Unsupported report JSON schema version.")

    engine = data.get("engine", {})
    if engine.get("deterministic") is not True or engine.get("ai_generated") is not False:
        raise ContractTrustError("engine verification flags are not trusted.")

    persona = data.get("persona", {})
    if persona.get("sample_data_only") is not True:
        raise ContractTrustError("persona is not marked sample-data-only.")

    if data.get("privacy") != APPROVED_PRIVACY_FLAGS:
        raise ContractTrustError("privacy flags are not in the approved local/sample state.")

    self_check = data.get("self_check", {})
    if self_check.get("all_passed") is not True:
        raise ContractTrustError("self-checks are not all passing.")

    artifacts = data.get("sources", {}).get("artifacts", [])
    if any(Path(str(artifact)).name != str(artifact) for artifact in artifacts):
        raise ContractTrustError("source artifacts must be basename-only.")


def build_home_dashboard_model(data: dict[str, Any]) -> dict[str, Any]:
    """Build the 10-second dashboard model from verified report JSON."""
    validate_report_contract(data)
    headline = data["headline"]
    persona = data["persona"]
    period = data["period"]

    return {
        "title": persona["name"],
        "period_label": period["label"],
        "verdict": headline["verdict"],
        "trust_badge": "Verified by engine",
        "sample_badge": "Sample data only",
        "metrics": [
            {"label": "Net cash flow", "value": _money(headline["net_cash_flow"])},
            {"label": "Savings rate", "value": _percent(headline["savings_rate"])},
            {"label": "Emergency runway", "value": _months(headline.get("emergency_runway_months"))},
            {"label": "Net worth", "value": _money(headline["net_worth"])},
        ],
        "runway_status": headline["runway_status"],
        "risk_counts": headline["risk_counts"],
        "top_risk": headline.get("top_risk"),
        "top_goal": headline.get("top_goal"),
        "next_action": (headline.get("next_action") or {}).get("Action Item", "No open action item."),
        "rent_vs_buy": headline["rent_vs_buy"],
        "source_artifacts": data.get("sources", {}).get("artifacts", []),
    }


def build_privacy_settings_model(data: dict[str, Any]) -> dict[str, Any]:
    """Build the trust/safety settings model from verified report JSON."""
    validate_report_contract(data)
    privacy = data["privacy"]
    self_check = data["self_check"]

    return {
        "mode": privacy["mode"],
        "settings": [
            {"label": "Real data", "status": "Locked off", "enabled": privacy["real_data_enabled"]},
            {"label": "Bank login", "status": "Not connected", "enabled": privacy["bank_login"]},
            {"label": "Cloud sync", "status": "Off", "enabled": privacy["cloud_sync"]},
            {"label": "Cloud AI", "status": "Off", "enabled": privacy["cloud_ai"]},
            {"label": "Local AI memo", "status": "Off by default", "enabled": privacy["local_ai_enabled"]},
        ],
        "engine_statement": "Numbers are calculated by the deterministic Python engine.",
        "ai_statement": "No AI-generated values are present in this report JSON.",
        "self_check": f"{self_check['checks_passed']}/{self_check['checks_total']} checks passed",
    }


MONTHLY_REPORT_SECTIONS = [
    ("Summary", "summary"),
    ("Budget vs Actual", "budget_vs_actual"),
    ("Goals", "goals"),
    ("Risk Register", "risk_register"),
    ("Action Items", "action_items"),
    ("Cash Runway", "runway"),
    ("Forecast", "forecast"),
    ("Net Worth", "net_worth"),
    ("Upcoming Obligations", "upcoming_obligations"),
    ("Unusual Expenses", "unusual_expenses"),
    ("12-Month Projection", "projection"),
    ("Recurring Vendors", "recurring_vendors"),
    ("Debt Payoff", "debt_payoff"),
    ("Scorecard", "scorecard"),
    ("Rent vs Buy", "rent_vs_buy"),
    ("Home Purchase Readiness", "home_purchase_readiness"),
]

RISK_COLORS = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
VARIANCE_COLORS = {"green": "🟢", "amber": "🟡", "red": "🔴"}


def build_monthly_report_model(data: dict[str, Any]) -> dict[str, Any]:
    """Build the Monthly Report Reader model from verified report JSON."""
    validate_report_contract(data)
    persona = data["persona"]
    period = data["period"]
    sections = data["sections"]
    self_check = data["self_check"]

    return {
        "title": persona["name"],
        "period_label": period["label"],
        "trust_badge": f"Verified by engine · {self_check['checks_passed']}/{self_check['checks_total']} checks passed",
        "sections": sections,
        "available_sections": [
            (label, key) for label, key in MONTHLY_REPORT_SECTIONS if key in sections
        ],
    }


def _money(value: float | int) -> str:
    sign = "-" if float(value) < 0 else ""
    return f"{sign}${abs(float(value)):,.2f}"


def _percent(value: float | int) -> str:
    return f"{float(value):.1f}%"


def _months(value: float | int | None) -> str:
    if value is None:
        return "Unknown"
    return f"{float(value):.1f} months"
