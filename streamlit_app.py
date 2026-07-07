"""Streamlit Read & Trust app for the Personal Finance CFO Agent.

Run locally with:

    streamlit run streamlit_app.py

The app renders verified report JSON only. It does not connect to banks, use real
data, call AI, or calculate new financial numbers.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import streamlit as st

import pandas as pd

from modules.config import APPROVED_CATEGORIES
from modules.importers.personal_csv import parse_credit_union_visa_pdf, read_uploaded_tabular_file, write_uploaded_transactions
from modules.personal_profile import DEFAULT_PROFILE_PATH, build_onboarding_profile, write_personal_profile
from modules.ui.report_reader import (
    RISK_COLORS,
    VARIANCE_COLORS,
    ContractTrustError,
    apply_merchant_category_rules,
    build_category_review_model,
    build_home_dashboard_model,
    build_local_ai_memo_model,
    build_monthly_report_model,
    build_privacy_settings_model,
    build_progress_memory_model,
    build_stress_test_model,
    build_uploaded_category_review_model,
    build_uploaded_report_action_model,
    build_upload_preview_model,
    load_category_review_rows,
    load_progress_history,
    load_report_contract,
    load_stress_test_summary,
    save_uploaded_category_review_edits,
)

DEFAULT_REPORT_JSON = Path("test_personas/complex_household/outputs/report.json")
DEFAULT_CATEGORY_REVIEW = Path("data/processed/category_review.csv")
DEFAULT_STRESS_TEST_RUN = Path("outputs/stress_tests/review_smoke_12_personas")
DEFAULT_UPLOAD_NORMALIZED = Path("data/processed/uploaded_transactions_normalized.csv")
DEFAULT_UPLOAD_CATEGORY_REVIEW = Path("data/processed/uploaded_category_review.csv")
DEFAULT_UPLOAD_REPORT = Path("outputs/personal/uploaded_personal_cfo_report.pdf")
DEFAULT_UPLOAD_CHARTS = Path("outputs/personal/uploaded_charts")
DEFAULT_PROGRESS_HISTORY = Path("outputs/personal/progress_history.json")
DEFAULT_PERSONAL_PROFILE = DEFAULT_PROFILE_PATH
SAMPLE_REPORTS = {
    "Complex Household sample": Path("test_personas/complex_household/outputs/report.json"),
    "Starter Person sample": Path("test_personas/starter_person/outputs/report.json"),
}


st.set_page_config(page_title="Personal Finance CFO Agent", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")


def main() -> None:
    st.title("Personal Finance CFO Agent")
    st.caption("Local-first CFO workspace. Your numbers appear only after local setup, upload, review, and report generation.")

    st.sidebar.caption("Local-first MVP: private setup, local upload/review, optional sample reports.")
    report_path = DEFAULT_REPORT_JSON
    category_review_path = DEFAULT_CATEGORY_REVIEW
    stress_test_path = DEFAULT_STRESS_TEST_RUN
    screens = ["First Run Setup", "Home Dashboard", "Upload Transactions", "Monthly Report", "Category Review", "Example Reports", "Progress Memory", "Stress Test Explorer", "Local AI Memo", "Settings / Privacy"]
    requested_screen = st.query_params.get("screen", "")
    default_screen = "Home Dashboard" if DEFAULT_PERSONAL_PROFILE.exists() else "First Run Setup"
    page = st.sidebar.radio("Screen", screens, index=screens.index(requested_screen) if requested_screen in screens else screens.index(default_screen))

    _privacy_banner()

    if page == "First Run Setup":
        render_first_run_setup(DEFAULT_PERSONAL_PROFILE)
    elif page == "Home Dashboard":
        render_personal_report_placeholder("Home Dashboard")
    elif page == "Upload Transactions":
        render_upload_transactions()
    elif page == "Monthly Report":
        render_personal_report_placeholder("Monthly Report")
    elif page == "Category Review":
        render_personal_report_placeholder("Category Review")
    elif page == "Example Reports":
        render_example_reports()
    elif page == "Progress Memory":
        render_progress_memory()
    elif page == "Stress Test Explorer":
        try:
            run = load_stress_test_summary(stress_test_path)
        except (OSError, ValueError, ContractTrustError) as error:
            st.error(f"Stress test run is not trusted: {error}")
            return
        render_stress_test_explorer(build_stress_test_model(run))
    elif page == "Local AI Memo":
        contract = _load_trusted_report(report_path)
        if contract:
            render_local_ai_memo(build_local_ai_memo_model(contract))
    else:
        contract = _load_trusted_report(report_path)
        if contract:
            render_privacy_settings(build_privacy_settings_model(contract))


def render_first_run_setup(profile_path: Path) -> None:
    st.subheader("First Run Setup")
    st.info(
        "Start with your baseline before uploading transactions: goals, current balances, debt, "
        "and what you want the CFO reports to track. This saves only to a Git-ignored local file."
    )
    if profile_path.exists():
        st.success(f"Local profile already exists: {profile_path.relative_to(Path.cwd())}")
        st.caption("To change it, edit the local JSON file or remove it and run setup again. No cloud sync or AI is used.")
        return

    with st.form("first_run_profile"):
        household_name = st.text_input("What should we call this household/profile?", placeholder="Optional")
        current_state = st.text_area("Where are you now?", placeholder="Optional: school, work, debt payoff, emergency fund, buying a home, etc.")
        st.markdown("#### Current balances")
        assets_left, assets_mid, assets_right = st.columns(3)
        checking = assets_left.text_input("Checking", placeholder="Leave blank if unknown")
        savings = assets_mid.text_input("Savings", placeholder="Leave blank if unknown")
        investments = assets_right.text_input("Investments", placeholder="Leave blank if unknown")

        st.markdown("#### Debt")
        debt_left, debt_mid, debt_right = st.columns(3)
        credit_card_debt = debt_left.text_input("Credit card debt", placeholder="Leave blank if none/unknown")
        student_loan_debt = debt_mid.text_input("Student loan debt", placeholder="Leave blank if none/unknown")
        other_debt = debt_right.text_input("Other debt", placeholder="Leave blank if none/unknown")
        monthly_debt_payment = st.text_input("Monthly debt payment target", placeholder="Optional")

        st.markdown("#### Goals")
        primary_goal = st.text_input("Main goal", placeholder="Optional")
        goal_left, goal_mid, goal_right = st.columns(3)
        primary_goal_target = goal_left.text_input("Main goal target amount", placeholder="Optional")
        primary_goal_current = goal_mid.text_input("Main goal current amount", placeholder="Optional")
        emergency_fund_target = goal_right.text_input("Emergency fund target", placeholder="Optional")
        savings_rate_target = st.text_input("Savings-rate target (%)", placeholder="Optional")
        target_date = st.text_input("Target date", placeholder="Optional")

        st.markdown("#### Optional future planning")
        future_left, future_mid, future_right = st.columns(3)
        home_price = future_left.text_input("Future home price target", placeholder="Optional")
        major_purchase = future_mid.text_input("Major purchase to plan for", placeholder="Optional")
        down_payment_pct = future_right.text_input("Down payment target (%)", placeholder="Optional")

        submitted = st.form_submit_button("Save local baseline")

    if submitted:
        profile = build_onboarding_profile(
            household_name=household_name,
            current_state=current_state,
            checking=checking,
            savings=savings,
            investments=investments,
            credit_card_debt=credit_card_debt,
            student_loan_debt=student_loan_debt,
            other_debt=other_debt,
            monthly_debt_payment=monthly_debt_payment,
            primary_goal=primary_goal,
            primary_goal_target=primary_goal_target,
            primary_goal_current=primary_goal_current,
            emergency_fund_target=emergency_fund_target,
            savings_rate_target=savings_rate_target,
            target_date=target_date,
            home_price=home_price,
            major_purchase=major_purchase,
            down_payment_pct=down_payment_pct,
        )
        write_personal_profile(profile, profile_path)
        st.success(f"Saved local baseline to {profile_path.relative_to(Path.cwd())}")
        st.caption("Next: upload transactions, review categories, then generate reports from the saved review file.")


def _load_trusted_report(report_path: Path):
    try:
        return load_report_contract(report_path)
    except (OSError, ValueError, ContractTrustError) as error:
        st.error(f"Report JSON is not trusted: {error}")
        return None


def render_personal_report_placeholder(screen_name: str) -> None:
    st.subheader(screen_name)
    st.info(
        "No personal report numbers are shown yet. Start with First Run Setup, upload CSV/Excel/PDF statements, "
        "review final categories, then generate your local CFO report."
    )
    if DEFAULT_UPLOAD_CATEGORY_REVIEW.exists():
        _render_uploaded_report_action()
    else:
        st.caption("If you want to inspect fictional data, open Example Reports and choose a test persona.")


def render_example_reports() -> None:
    st.subheader("Example Reports")
    st.info("Fictional/sample personas only. These numbers are examples and are separate from your private setup.")
    selected = st.selectbox("Choose a test persona", list(SAMPLE_REPORTS))
    view = st.radio("View", ["Dashboard", "Monthly Report"], horizontal=True)
    contract = _load_trusted_report(SAMPLE_REPORTS[selected])
    if not contract:
        return
    if view == "Dashboard":
        render_home_dashboard(build_home_dashboard_model(contract))
    else:
        render_monthly_report(build_monthly_report_model(contract))


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
        st.markdown(_escape_streamlit_markdown(model["next_action"]))
        st.markdown("#### Runway")
        st.markdown(_escape_streamlit_markdown(model["runway_status"]))
    with right:
        st.markdown("#### Risk snapshot")
        risk_cols = st.columns(len(model["risk_metrics"]))
        for column, metric in zip(risk_cols, model["risk_metrics"]):
            column.metric(metric["label"], metric["value"])
        st.markdown("#### Rent vs buy")
        st.markdown(_escape_streamlit_markdown(model["rent_vs_buy"]["recommendation"]))

    st.markdown("#### Source artifacts")
    st.write(", ".join(model["source_artifacts"]))


def render_upload_transactions() -> None:
    st.subheader("Upload Transactions")
    st.info("Local upload flow. Files are not sent anywhere; reports require saved final categories first.")
    uploaded_files = st.file_uploader(
        "CSV, Excel, or PDF statement/transaction/brokerage history",
        type=["csv", "xlsx", "xlsm", "pdf"],
        accept_multiple_files=True,
    )
    if not uploaded_files:
        st.caption("Supported now: one bank/brokerage CSV or Excel workbook, one PDF, or multiple Credit Union Visa PDF statements.")
        _render_uploaded_report_action()
        return

    try:
        source_names = [uploaded.name for uploaded in uploaded_files]
        if len(uploaded_files) > 1:
            if any(not name.lower().endswith(".pdf") for name in source_names):
                raise ValueError("Multiple uploads currently supports PDF statements only; upload one CSV or Excel export at a time")
            raw = pd.concat(
                [
                    parse_credit_union_visa_pdf(uploaded.read(), source_file=uploaded.name)
                    for uploaded in uploaded_files
                ],
                ignore_index=True,
            )
            source_label = " + ".join(source_names)
        else:
            uploaded = uploaded_files[0]
            source_label = uploaded.name
            if uploaded.name.lower().endswith(".pdf"):
                raw = parse_credit_union_visa_pdf(uploaded.read(), source_file=uploaded.name)
            else:
                raw = read_uploaded_tabular_file(uploaded, source_file=uploaded.name)
        model = build_upload_preview_model(raw.to_dict("records"), source_file=source_label)
        review_model = build_uploaded_category_review_model(raw.to_dict("records"), source_file=source_label)
    except Exception as error:  # Streamlit boundary: show parser errors instead of crashing.
        st.error(f"Upload could not be parsed: {error}")
        return

    st.success(model["status"])
    cols = st.columns(3)
    cols[0].metric("Rows", model["row_count"])
    cols[1].metric("Profile", model["profile"])
    cols[2].metric("Report generation", "Locked")
    st.caption(f"Source file: {model['source_file']}")
    st.markdown("#### Normalized preview")
    st.dataframe(pd.DataFrame(model["preview_rows"]), width="stretch", hide_index=True)
    st.markdown("#### Category review")
    st.caption("Edit `final_category` where needed, then save the review CSV before generating a report.")
    review_rows = review_model["rows"]
    if st.button("Apply merchant rules to blank categories"):
        review_rows, changed = apply_merchant_category_rules(review_rows)
        st.success(f"Applied merchant rules to {changed} rows")
    review_df = pd.DataFrame(review_rows)
    edited_review = st.data_editor(
        review_df,
        width="stretch",
        hide_index=True,
        column_config={"final_category": st.column_config.SelectboxColumn("final_category", options=["", *APPROVED_CATEGORIES])},
        disabled=[column for column in review_df.columns if column not in {"final_category", "override_note"}],
    )
    if st.button("Save normalized transactions locally"):
        write_uploaded_transactions(raw, DEFAULT_UPLOAD_NORMALIZED, source_file=source_label)
        st.success(f"Saved to {DEFAULT_UPLOAD_NORMALIZED}")
    if st.button("Save category review CSV locally"):
        save_uploaded_category_review_edits(edited_review.to_dict("records"), DEFAULT_UPLOAD_CATEGORY_REVIEW)
        st.success(f"Saved to {DEFAULT_UPLOAD_CATEGORY_REVIEW}")
    _render_uploaded_report_action()


def _render_uploaded_report_action() -> None:
    st.markdown("#### Generate CFO report")
    action = build_uploaded_report_action_model(DEFAULT_UPLOAD_CATEGORY_REVIEW, DEFAULT_UPLOAD_REPORT)
    st.caption(action["reason"])
    if not action["can_generate"]:
        return
    if st.button("Generate CFO report from saved uploaded review"):
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_personal_report.py",
                    "--reviewed-input",
                    str(DEFAULT_UPLOAD_CATEGORY_REVIEW),
                    "--output",
                    str(DEFAULT_UPLOAD_REPORT),
                    "--charts-dir",
                    str(DEFAULT_UPLOAD_CHARTS),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            st.error(error.stderr or error.stdout or str(error))
            return
        st.success(f"Generated {DEFAULT_UPLOAD_REPORT}")
        st.code(result.stdout)


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
    st.dataframe(pd.DataFrame(model["rows"]), width="stretch", hide_index=True)


def render_progress_memory() -> None:
    st.subheader("Progress Memory")
    st.info("Read-only local history from generated personal reports. No AI summary is produced here.")
    if not DEFAULT_PROGRESS_HISTORY.exists():
        st.caption("No progress history yet. Generate a personal CFO report first.")
        return
    try:
        model = build_progress_memory_model(load_progress_history(DEFAULT_PROGRESS_HISTORY))
    except (OSError, ValueError, ContractTrustError) as error:
        st.error(f"Progress history is not trusted: {error}")
        return
    st.caption(f"{model['workbench_badge']} · latest: {model['latest_report']}")
    cols = st.columns(3)
    for index, metric in enumerate(model["metrics"]):
        cols[index % 3].metric(metric["label"], metric["value"], metric["delta"])
    st.markdown("#### Report history")
    st.dataframe(pd.DataFrame(model["history_rows"]), width="stretch", hide_index=True)


def render_stress_test_explorer(model: dict) -> None:
    st.subheader(f"{model['title']} · {model['run_name']}")
    st.caption(model["workbench_badge"])
    st.info("Read-only sample stress results. The deterministic engine generated all persona outputs.")

    cols = st.columns(len(model["metrics"]))
    for column, metric in zip(cols, model["metrics"]):
        column.metric(metric["label"], metric["value"])

    st.markdown("#### Coverage")
    st.dataframe(pd.DataFrame([model["coverage_counts"]]), width="stretch", hide_index=True)

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
    st.dataframe(df[[column for column in grid_columns if column in df.columns]], width="stretch", hide_index=True)

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
            st.dataframe(df[cols], width="stretch", hide_index=True)
        elif key == "risk_register" and "Level" in df.columns:
            df[""] = df["Level"].map(lambda lvl: RISK_COLORS.get(lvl, ""))
            cols = [""] + [c for c in df.columns if c != ""]
            st.dataframe(df[cols], width="stretch", hide_index=True)
        elif key == "goals" and "Progress (%)" in df.columns:
            for _, row in df.iterrows():
                pct = float(row["Progress (%)"])
                st.markdown(f"**{row['Goal']}** — {row['Status']}")
                st.progress(min(pct / 100, 1.0))
                st.caption(f"Target: {row['Target']} · Current: {row['Current']} · Monthly needed: {row['Monthly Needed']}")
        else:
            st.dataframe(df, width="stretch", hide_index=True)
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
        "Local upload/review active. Reports require saved final categories first. "
        "No bank login. No cloud sync. No cloud AI. Local AI memo off by default."
    )


def _escape_streamlit_markdown(text: object) -> str:
    """Render finance text literally instead of treating dollar pairs as Markdown math."""
    return str(text).replace("$", r"\$")


if __name__ == "__main__":
    main()
