import json
from pathlib import Path

import pytest

from modules.ui.report_reader import (
    ContractTrustError,
    build_home_dashboard_model,
    build_monthly_report_model,
    build_privacy_settings_model,
    load_report_contract,
)


def _sample_contract():
    return json.loads(Path("outputs/report_json/portfolio_demo_2026-03.json").read_text(encoding="utf-8"))


def test_load_report_contract_rejects_untrusted_flags(tmp_path):
    contract = _sample_contract()
    contract["privacy"]["cloud_ai"] = True
    path = tmp_path / "unsafe_report.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ContractTrustError, match="privacy flags"):
        load_report_contract(path)


def test_home_dashboard_model_is_read_only_engine_verified():
    model = build_home_dashboard_model(_sample_contract())

    assert model["title"] == "Morgan Patel Household"
    assert model["period_label"] == "March 2026"
    assert model["verdict"] == "On track"
    assert model["trust_badge"] == "Verified by engine"
    assert model["sample_badge"] == "Sample data only"
    assert model["metrics"] == [
        {"label": "Net cash flow", "value": "$1,354.60"},
        {"label": "Savings rate", "value": "6.3%"},
        {"label": "Emergency runway", "value": "3.6 months"},
        {"label": "Net worth", "value": "$150,300.00"},
    ]
    assert model["risk_counts"] == {"high": 0, "medium": 2, "low": 4}
    assert "Home Depot" in model["next_action"]
    assert model["source_artifacts"] == [
        "report_2026-03.json",
        "portfolio_demo_morgan_patel_monthly_cfo_report_2026_03.pdf",
    ]


def test_monthly_report_model_returns_all_key_sections():
    model = build_monthly_report_model(_sample_contract())

    assert model["title"] == "Morgan Patel Household"
    assert model["period_label"] == "March 2026"
    assert "Verified by engine" in model["trust_badge"]
    assert "11/11" in model["trust_badge"]

    section_keys = {key for _, key in model["available_sections"]}
    for required in ("budget_vs_actual", "goals", "risk_register", "action_items", "runway"):
        assert required in section_keys, f"missing section: {required}"


def test_monthly_report_model_sections_are_engine_verified():
    model = build_monthly_report_model(_sample_contract())
    sections = model["sections"]

    # budget_vs_actual rows have Color Flag from the engine
    assert all("Color Flag" in row for row in sections["budget_vs_actual"])
    # risk_register rows have Level
    assert all("Level" in row for row in sections["risk_register"])
    # goals rows have Progress (%)
    assert all("Progress (%)" in row for row in sections["goals"])


def test_privacy_settings_model_locks_unsafe_modes_off():
    model = build_privacy_settings_model(_sample_contract())

    assert model["mode"] == "sample"
    assert model["settings"] == [
        {"label": "Real data", "status": "Locked off", "enabled": False},
        {"label": "Bank login", "status": "Not connected", "enabled": False},
        {"label": "Cloud sync", "status": "Off", "enabled": False},
        {"label": "Cloud AI", "status": "Off", "enabled": False},
        {"label": "Local AI memo", "status": "Off by default", "enabled": False},
    ]
    assert model["engine_statement"] == "Numbers are calculated by the deterministic Python engine."
    assert model["ai_statement"] == "No AI-generated values are present in this report JSON."
    assert model["self_check"] == "11/11 checks passed"
