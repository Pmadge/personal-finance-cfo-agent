"""Tests for the stable report JSON contract used by the UI layer."""

import json

from modules.reports.report_json import (
    REPORT_JSON_SCHEMA_VERSION,
    build_report_json,
    write_report_json,
)
from modules.reports.pdf_report import complex_household_report_config


def _assert_json_safe(obj):
    """The contract must round-trip through json with no custom encoder."""
    text = json.dumps(obj)
    assert json.loads(text) == obj
    return text


def test_report_json_contract_default_persona(tmp_path):
    """Default report serializes to a stable, JSON-safe contract."""
    contract = build_report_json(output_dir=tmp_path / "charts")
    text = _assert_json_safe(contract)

    assert contract["schema_version"] == REPORT_JSON_SCHEMA_VERSION
    assert contract["engine"]["deterministic"] is True
    assert contract["engine"]["ai_generated"] is False
    assert contract["persona"]["sample_data_only"] is True

    # Headline carries the 10-second Home Dashboard read.
    headline = contract["headline"]
    for key in (
        "verdict",
        "net_cash_flow",
        "savings_rate",
        "emergency_runway_months",
        "net_worth",
        "risk_counts",
        "rent_vs_buy",
    ):
        assert key in headline
    assert set(headline["risk_counts"]) == {"high", "medium", "low"}

    # All report-reader sections are present.
    sections = contract["sections"]
    for key in (
        "summary",
        "cash_flow",
        "runway",
        "projection",
        "budget_vs_actual",
        "goals",
        "risk_register",
        "rent_vs_buy",
        "action_items",
        "self_checks",
    ):
        assert key in sections

    # Privacy posture is explicit and safe.
    privacy = contract["privacy"]
    assert privacy["mode"] == "sample"
    assert privacy["real_data_enabled"] is False
    assert privacy["local_only"] is True
    assert privacy["cloud_ai"] is False
    assert privacy["local_ai_enabled"] is False

    # No local filesystem path leaks into the contract.
    assert "/Users/" not in text
    assert "paulmadgett" not in text


def test_report_json_contract_complex_household_passes_self_checks(tmp_path):
    """The complex-household fixture must pass every self-check."""
    contract = build_report_json(
        output_dir=tmp_path / "charts",
        report_config=complex_household_report_config(),
    )
    _assert_json_safe(contract)

    assert contract["persona"]["name"] == "Complex Household"
    self_check = contract["self_check"]
    assert self_check["checks_total"] > 0
    assert self_check["all_passed"] is True
    assert self_check["checks_passed"] == self_check["checks_total"]

    # The action item owner follows the persona, not a hardcoded name.
    actions = contract["sections"]["action_items"]
    if actions:
        assert actions[0]["Owner"] == "Complex Household"


def test_write_report_json_creates_file(tmp_path):
    """write_report_json writes a parseable file to disk."""
    out_path = tmp_path / "nested" / "report.json"
    written = write_report_json(out_path, output_dir=tmp_path / "charts")

    assert written == out_path
    assert out_path.exists()
    loaded = json.loads(out_path.read_text())
    assert loaded["schema_version"] == REPORT_JSON_SCHEMA_VERSION
