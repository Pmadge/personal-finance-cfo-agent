"""Streamlit Read & Trust app for the Personal Finance CFO Agent.

Run locally with:

    streamlit run streamlit_app.py

The app renders verified report JSON only. It does not connect to banks, use real
data, call AI, or calculate new financial numbers.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import pandas as pd

from modules.ui.report_reader import (
    RISK_COLORS,
    VARIANCE_COLORS,
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

DEFAULT_REPORT_JSON = Path("outputs/report_json/portfolio_demo_2026-03.json")
DEFAULT_CATEGORY_REVIEW = Path("data/processed/category_review.csv")
DEFAULT_STRESS_TEST_RUN = Path("outputs/stress_tests/review_smoke_12_personas")


st.set_page_config(page_title="Personal Finance CFO Agent", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")


def main() -> None:
    st.title("Personal Finance CFO Agent")
    st.caption("Local-first Read & Trust app over verified sample report JSON.")

    st.sidebar.caption("MVP v0.1 reads approved sample artifacts only.")
    report_path = DEFAULT_REPORT_JSON
    category_review_path = DEFAULT_CATEGORY_REVIEW
    stress_test_path = DEFAULT_STRESS_TEST_RUN
    page = st.sidebar.radio(
        "Screen",
        ["Home Dashboard", "Monthly Report", "Category Review", "Stress Test Explorer", "Local AI Memo", "Settings / Privacy"],
    )

    try:
        contract = load_report_contract(report_path)
    except (OSError, ValueError, ContractTrustError) as error:
        st.error(f"Report JSON is not trusted: {error}")
        return

    _privacy_banner()

    if page == "Home Dashboard":
        render_home_dashboard(build_home_dashboard_model(contract))
    elif page == "Monthly Report":
        render_monthly_report(build_monthly_report_model(contract))
    elif page == "Category Review":
        try:
            rows = load_category_review_rows(category_review_path)
        except (OSError, ValueError, ContractTrustError) as error:
            st.error(f"Category review CSV is not trusted: {error}")
            return
        render_category_review(build_category_review_model(contract, rows))
    elif page == "Stress Test Explorer":
        try:
            run = load_stress_test_summary(stress_test_path)
        except (OSError, ValueError, ContractTrustError) as error:
            st.error(f"Stress test run is not trusted: {error}")
            return
        render_stress_test_explorer(build_stress_test_model(run))
    elif page == "Local AI Memo":
        render_local_ai_memo(build_local_ai_memo_model(contract))
    else:
        render_privacy_settings(build_privacy_settings_model(contract))


def render_home_dashboard(model: dict) -> None:
    st.subheader(f"{model['title']} · {model['period_label']}")
    st.markdown(f"### {model['verdict']}")
    st.success(f"{model['trust_badge']} · {model['sample_badge']}")

    cols = st.columns(len(model["metrics"]))
    for column, metric in zip(cols, model["metrics"]):
        column.metric(metric["label"], metric["value"])

    left, right = st.columns(2)
    with left:
        st.markdown("#### What changed")
        st.write(model["next_action"])
        st.markdown("#### Runway")
        st.write(model["runway_status"])
    with right:
        st.markdown("#### Risk snapshot")
        st.json(model["risk_counts"])
        st.markdown("#### Rent vs buy")
        st.write(model["rent_vs_buy"]["recommendation"])

    st.markdown("#### Source artifacts")
    st.write(", ".join(model["source_artifacts"]))


def render_monthly_report(model: dict) -> None:
    st.subheader(f"{model['title']} · {model['period_label']}")
    st.caption(model["trust_badge"])

    available = model["available_sections"]
    section_labels = [label for label, _ in available]
    section_keys = {label: key for label, key in available}

    chosen = st.selectbox("Section", section_labels)
    key = section_keys[chosen]
    data = model["sections"][key]

    st.markdown(f"#### {chosen}")
    _render_section(key, data)


def render_category_review(model: dict) -> None:
    st.subheader(f"{model['title']} · {model['period_label']}")
    st.caption(f"{model['trust_badge']} · {model['workbench_badge']}")
    st.info("Read-only review surface. Suggestions only suggest; reports trust final reviewed categories.")

    counts = model["status_counts"]
    cols = st.columns(4)
    cols[0].metric("Rows", counts["total_rows"])
    cols[1].metric("Needs review", counts["needs_review"])
    cols[2].metric("Auto-suggested", counts["auto_suggested"])
    cols[3].metric("Manual overrides", counts["manual_override"])

    st.markdown("#### Approved categories present")
    st.write(", ".join(model["categories"]) or "No final categories yet.")

    st.markdown("#### Review workbench")
    st.dataframe(pd.DataFrame(model["rows"]), use_container_width=True, hide_index=True)


def render_stress_test_explorer(model: dict) -> None:
    st.subheader(f"{model['title']} · {model['run_name']}")
    st.caption(model["workbench_badge"])
    st.info("Read-only sample stress results. The deterministic engine generated all persona outputs.")

    cols = st.columns(len(model["metrics"]))
    for column, metric in zip(cols, model["metrics"]):
        column.metric(metric["label"], metric["value"])

    st.markdown("#### Coverage")
    st.dataframe(pd.DataFrame([model["coverage_counts"]]), use_container_width=True, hide_index=True)

    st.markdown("#### Persona grid")
    grid_columns = [
        "persona_id",
        "status",
        "life_stage",
        "wealth_profile",
        "spending_style",
        "net_cash_flow",
        "savings_rate",
        "emergency_runway_months",
        "high_risks",
    ]
    df = pd.DataFrame(model["persona_rows"])
    st.dataframe(df[[column for column in grid_columns if column in df.columns]], use_container_width=True, hide_index=True)

    st.markdown("#### Source artifacts")
    st.write(", ".join(model["source_artifacts"]))


def render_local_ai_memo(model: dict) -> None:
    st.subheader(model["title"])
    st.warning(model["generation_status"])
    st.write(model["local_only_statement"])
    st.write(model["number_source_statement"])

    st.markdown("#### Memo preview")
    st.info("Local AI memo is intentionally unavailable in MVP v0.1 until a local-only model path is explicitly approved.")

    st.markdown("#### Source label")
    st.caption(model["source_label"])
    st.write(", ".join(model["verified_artifacts"]))


def _render_section(key: str, data: object) -> None:
    if isinstance(data, list):
        if not data:
            st.info("No records for this period.")
            return
        df = pd.DataFrame(data)
        if key == "budget_vs_actual" and "Color Flag" in df.columns:
            df[""] = df["Color Flag"].map(lambda f: VARIANCE_COLORS.get(f, ""))
            cols = [""] + [c for c in df.columns if c not in ("Color Flag", "")]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        elif key == "risk_register" and "Level" in df.columns:
            df[""] = df["Level"].map(lambda lvl: RISK_COLORS.get(lvl, ""))
            cols = [""] + [c for c in df.columns if c != ""]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        elif key == "goals" and "Progress (%)" in df.columns:
            for _, row in df.iterrows():
                pct = float(row["Progress (%)"])
                st.markdown(f"**{row['Goal']}** — {row['Status']}")
                st.progress(min(pct / 100, 1.0))
                st.caption(f"Target: {row['Target']} · Current: {row['Current']} · Monthly needed: {row['Monthly Needed']}")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
    elif isinstance(data, dict):
        items = list(data.items())
        cols = st.columns(min(len(items), 3))
        for i, (label, value) in enumerate(items):
            cols[i % 3].metric(label, str(value))
    elif isinstance(data, str):
        st.info(data)


def render_privacy_settings(model: dict) -> None:
    st.subheader("Settings / Privacy")
    st.info(f"Mode: {model['mode']}")
    st.write(model["engine_statement"])
    st.write(model["ai_statement"])
    st.success(model["self_check"])

    for setting in model["settings"]:
        enabled = "Enabled" if setting["enabled"] else "Disabled"
        st.write(f"**{setting['label']}**: {setting['status']} ({enabled})")


def _privacy_banner() -> None:
    st.warning(
        "Sample mode active. Real data locked. Local-only. No bank login. "
        "No cloud sync. No cloud AI. Local AI memo off by default."
    )


if __name__ == "__main__":
    main()
