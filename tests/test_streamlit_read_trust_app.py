import copy
import json
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from modules.reports.pdf_report import portfolio_demo_report_config
from modules.reports.report_json import build_report_json

from modules.ui.report_reader import (
    ContractTrustError,
    build_category_review_model,
    build_home_dashboard_model,
    build_local_ai_memo_model,
    build_monthly_report_model,
    build_privacy_settings_model,
    build_stress_test_model,
    load_category_review_rows,
    load_report_contract,
    load_stress_test_summary,
)


def _sample_contract():
    return copy.deepcopy(_cached_sample_contract())


@lru_cache(maxsize=1)
def _cached_sample_contract():
    with TemporaryDirectory() as tmp_dir:
        return build_report_json(
            output_dir=Path(tmp_dir) / "charts",
            report_config=portfolio_demo_report_config(),
        )


def _category_review_rows():
    return [
        {
            "date": "2026-03-01",
            "vendor": "Acme Payroll",
            "amount": "8500.0",
            "raw_category": "income",
            "source_file": "personal_transactions_template.csv",
            "source_row_number": "2",
            "import_batch_id": "sample_batch",
            "transaction_id": "sample_txn_001",
            "suggested_category": "Income",
            "classification_method": "raw_category_map",
            "review_status": "auto_suggested",
            "final_category": "Income",
            "override_note": "",
        },
        {
            "date": "2026-03-02",
            "vendor": "Parkside Rent Portal",
            "amount": "-3200.0",
            "raw_category": "rent",
            "source_file": "personal_transactions_template.csv",
            "source_row_number": "3",
            "import_batch_id": "sample_batch",
            "transaction_id": "sample_txn_002",
            "suggested_category": "Housing",
            "classification_method": "raw_category_map",
            "review_status": "auto_suggested",
            "final_category": "Housing",
            "override_note": "",
        },
        {
            "date": "2026-03-03",
            "vendor": "Trader Joe's",
            "amount": "-125.5",
            "raw_category": "groceries",
            "source_file": "personal_transactions_template.csv",
            "source_row_number": "4",
            "import_batch_id": "sample_batch",
            "transaction_id": "sample_txn_003",
            "suggested_category": "Food & Dining",
            "classification_method": "raw_category_map",
            "review_status": "auto_suggested",
            "final_category": "Food & Dining",
            "override_note": "",
        },
        {
            "date": "2026-03-04",
            "vendor": "Chipotle",
            "amount": "-18.75",
            "raw_category": "dining",
            "source_file": "personal_transactions_template.csv",
            "source_row_number": "5",
            "import_batch_id": "sample_batch",
            "transaction_id": "sample_txn_004",
            "suggested_category": "Food & Dining",
            "classification_method": "raw_category_map",
            "review_status": "auto_suggested",
            "final_category": "Food & Dining",
            "override_note": "",
        },
    ]


def _write_stress_run(run_dir: Path, *, failed: int = 0) -> Path:
    run_dir.mkdir(parents=True)
    status = "FAIL" if failed else "PASS"
    (run_dir / "summary.csv").write_text(
        "persona_id,display_name,status,failed_steps,step_count,transaction_count,life_stage,career,wealth_profile,spending_style,plan_type,accuracy_rate,misc_rate,income,expenses,net_cash_flow,savings_rate,net_worth,debt_to_asset_ratio,emergency_runway_months,risk_overall,high_risks\n"
        f"persona_001_late_career_professional_medical_heavy,Fictional Persona 001,{status},,24,36,late-career professional,consultant,high income high spend,medical-heavy,spending reset,91.67,8.33,9759.95,7209.56,2550.39,26.13,-741188.08,762.64,5.0,Attention needed,2\n",
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-28T16:37:39",
                "seed": 20260628,
                "persona_count": 1,
                "passed": 0 if failed else 1,
                "failed": failed,
                "coverage": {
                    "life_stages": ["late-career professional"],
                    "careers": ["consultant"],
                    "wealth_profiles": ["high income high spend"],
                    "spending_styles": ["medical-heavy"],
                    "plan_types": ["spending reset"],
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "README.md").write_text("Fictional/sample data only.\n", encoding="utf-8")
    return run_dir


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


def test_category_review_model_summarizes_read_only_review_rows():
    rows = _category_review_rows()
    model = build_category_review_model(_sample_contract(), rows)

    assert model["title"] == "Category Review"
    assert model["workbench_badge"] == "Workbench mode · read-only"
    assert model["status_counts"] == {
        "total_rows": 4,
        "needs_review": 0,
        "auto_suggested": 4,
        "manual_override": 0,
    }
    assert model["categories"] == ["Food & Dining", "Housing", "Income"]
    assert model["rows"][0]["source_file"] == "personal_transactions_template.csv"
    assert model["rows"][0]["source_row_number"] == "2"


def test_category_review_model_rejects_source_path_leak():
    rows = [
        {
            "date": "2026-04-01",
            "vendor": "Fake Payroll Deposit",
            "amount": "2500.0",
            "raw_category": "income",
            "source_file": "/Users/paulmadgett/private.csv",
            "source_row_number": "2",
            "import_batch_id": "import_fake",
            "transaction_id": "fake_txn_001",
            "suggested_category": "Income",
            "classification_method": "raw_category_map",
            "review_status": "auto_suggested",
            "final_category": "Income",
            "override_note": "",
        }
    ]

    with pytest.raises(ContractTrustError, match="source_file"):
        build_category_review_model(_sample_contract(), rows)


def test_category_review_loader_rejects_unapproved_local_paths(tmp_path):
    review_path = tmp_path / "category_review.csv"
    review_path.write_text("date,vendor,amount\n2026-03-01,Fake Vendor,-1\n", encoding="utf-8")

    with pytest.raises(ContractTrustError, match="approved sample artifact"):
        load_category_review_rows(review_path)


def test_stress_test_model_summarizes_verified_sample_run(tmp_path):
    run_dir = _write_stress_run(tmp_path / "review_smoke_12_personas")
    run = load_stress_test_summary(run_dir, approved_paths={run_dir})
    model = build_stress_test_model(run)

    assert model["title"] == "Stress Test Explorer"
    assert model["workbench_badge"] == "Workbench mode · read-only"
    assert model["run_name"] == "review_smoke_12_personas"
    assert model["metrics"] == [
        {"label": "Personas", "value": "1"},
        {"label": "Passed", "value": "1"},
        {"label": "Failed", "value": "0"},
        {"label": "Seed", "value": "20260628"},
    ]
    assert model["coverage_counts"]["life_stages"] == 1
    assert model["coverage_counts"]["wealth_profiles"] == 1
    assert len(model["persona_rows"]) == 1
    assert model["persona_rows"][0]["persona_id"] == "persona_001_late_career_professional_medical_heavy"
    assert model["source_artifacts"] == ["summary.csv", "summary.json", "README.md"]


def test_stress_test_loader_rejects_failed_sample_run(tmp_path):
    run_dir = _write_stress_run(tmp_path / "bad_run", failed=1)

    with pytest.raises(ContractTrustError, match="not fully passing"):
        load_stress_test_summary(run_dir, approved_paths={run_dir})


def test_stress_test_loader_rejects_unapproved_local_paths(tmp_path):
    run_dir = _write_stress_run(tmp_path / "unapproved_run")

    with pytest.raises(ContractTrustError, match="approved sample artifact"):
        load_stress_test_summary(run_dir)


def test_local_ai_memo_model_is_disabled_placeholder_with_verified_sources():
    model = build_local_ai_memo_model(_sample_contract())

    assert model["title"] == "Local AI Memo"
    assert model["enabled"] is False
    assert model["generation_status"] == "Disabled by default"
    assert model["memo_text"] is None
    assert model["local_only_statement"] == "No AI model was called. Cloud AI is off and there is no cloud fallback."
    assert model["number_source_statement"] == "Numbers remain owned by the deterministic Python engine."
    assert model["source_label"] == "Would be based on verified artifacts"
    assert model["verified_artifacts"] == [
        "report_2026-03.json",
        "portfolio_demo_morgan_patel_monthly_cfo_report_2026_03.pdf",
    ]


def test_local_ai_memo_model_rejects_enabled_ai_flag():
    contract = _sample_contract()
    contract["privacy"]["local_ai_enabled"] = True

    with pytest.raises(ContractTrustError, match="privacy flags"):
        build_local_ai_memo_model(contract)


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
