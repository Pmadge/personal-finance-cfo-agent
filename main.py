"""Entry point for the Personal Finance CFO Agent."""

from pathlib import Path

from modules.action_items import generate_action_items
from modules.analytics import (
    budget_vs_actual,
    cumulative_budget_vs_actual,
    mom_comparison,
    monthly_summary,
    upcoming_obligations,
)
from modules.categorizer import categorize_file
from modules.charts import generate_all_charts, validate_chart_specs
from modules.config import (
    ALEX_ASSETS,
    ALEX_BUDGET,
    ALEX_GOALS,
    ALEX_HOME_TARGET,
    ALEX_LIABILITIES,
    ALEX_MAJOR_PURCHASE,
    ALEX_SCENARIOS,
    APPROVED_CATEGORIES,
    MONTH_LABELS,
    REPORT_MONTH,
)
from modules.capital_events import home_purchase_readiness, major_purchase_check
from modules.goals import track_goals
from modules.risk import build_risk_register, risk_summary
from modules.scenarios import compare_scenarios
from modules.scorecard import ENGAGEMENT_CADENCE, outcomes_scorecard
from modules.detectors import (
    build_clothing_test_frame,
    detect_recurring,
    detect_unusual,
)
from modules.net_worth import debt_payoff_comparison, net_worth_snapshot
from modules.forecast import cash_runway, forecast_cash_flow, project_cash_flow
from modules.narrative import (
    cfo_commentary,
    evaluate_commentary,
    executive_summary,
)
from modules.self_checks import assert_pipeline_self_checks
from modules.validation import build_audit_log


def main():
    """Start the CFO Agent scaffold."""
    project_root = Path(__file__).parent
    input_path = project_root / "data" / "alex_rivera_transactions.csv"
    output_path = project_root / "data" / "alex_rivera_transactions_categorized.csv"
    charts_output_dir = project_root / "outputs"
    month_2 = "2026-02"
    month_3 = REPORT_MONTH
    alex_debts = [
        {
            "name": debt_name,
            "balance": debt_details["balance"],
            "interest_rate": debt_details["interest_rate"],
        }
        for debt_name, debt_details in ALEX_LIABILITIES.items()
    ]

    print("CFO Agent initialized")
    categorized_df, accuracy_rate = categorize_file(input_path, output_path)
    pipeline_self_checks = assert_pipeline_self_checks(
        categorized_df,
        report_month=REPORT_MONTH,
        approved_categories=APPROVED_CATEGORIES,
    )
    print(f"Pipeline self-checks passed: {len(pipeline_self_checks)} checks")
    print(f"Categorized output saved to: {output_path}")
    print(f"Accuracy rate: {accuracy_rate:.2f}%")
    print("\nAudit log:")
    print(build_audit_log(categorized_df, accuracy_rate, input_path, project_root).to_string(index=False))

    recurring_df = detect_recurring(categorized_df)
    unusual_df = detect_unusual(categorized_df)
    test_df = build_clothing_test_frame(categorized_df)
    test_unusual_df = detect_unusual(test_df)
    test_flag = test_unusual_df[
        test_unusual_df["Vendor"] == "Test Clothing Retailer"
    ]["Flag Message"].iloc[0]

    print("\nRecurring charges detected:")
    print(recurring_df.to_string(index=False))
    print("\nUnusual transactions detected:")
    print(unusual_df.to_string(index=False))
    print("\n$300 Month 2 clothing test flag:")
    print(test_flag)

    print(f"\nMonth 3 monthly summary ({month_3}):")
    month_3_summary = monthly_summary(categorized_df, month_3)
    month_3_budget = budget_vs_actual(categorized_df, month_3, ALEX_BUDGET)
    upcoming_df = upcoming_obligations(categorized_df)
    print(month_3_summary)
    print(f"\nMonth 3 budget vs actual ({month_3}):")
    print(month_3_budget.to_string(index=False))
    print("\nMonth-over-month category comparison:")
    print(mom_comparison(categorized_df).to_string(index=False))
    print("\nUpcoming obligations due in next 30 days:")
    print(upcoming_df.to_string(index=False))
    print("\n3-month cumulative budget vs actual:")
    print(cumulative_budget_vs_actual(categorized_df, ALEX_BUDGET).to_string(index=False))
    print("\nRolling forecast scenarios:")
    print(forecast_cash_flow(categorized_df).to_string(index=False))

    liquid_cash = ALEX_ASSETS["Checking"] + ALEX_ASSETS["Savings"]
    print("\nCash runway:")
    for label, value in cash_runway(categorized_df, liquid_cash).items():
        print(f"  {label}: {value}")
    print("\n12-month cash projection:")
    print(
        project_cash_flow(
            categorized_df, starting_cash=liquid_cash, months=12, start_month="2026-04"
        ).to_string(index=False)
    )

    print("\nWhat-if scenarios:")
    print(compare_scenarios(categorized_df, liquid_cash, ALEX_SCENARIOS).to_string(index=False))

    risk_register = build_risk_register(categorized_df, ALEX_ASSETS, ALEX_LIABILITIES, liquid_cash)
    _, risk_overall = risk_summary(risk_register)
    print("\nRisk register:")
    print(risk_register[["Risk", "Level", "Finding"]].to_string(index=False))
    print(f"Overall: {risk_overall}")

    home = home_purchase_readiness(categorized_df, ALEX_ASSETS, **ALEX_HOME_TARGET)
    print(f"\nCapital event - home purchase readiness: {home['verdict']}")
    print(f"  Home ${home['home_price']:,.0f} | cash needed ${home['cash_needed']:,.0f} | "
          f"payment ${home['monthly_payment_piti']:,.0f}/mo ({home['payment_to_income']}% of income)")
    for gap in home["gaps"]:
        print(f"  - {gap}")
    purchase = major_purchase_check(categorized_df, ALEX_ASSETS, ALEX_MAJOR_PURCHASE, liquid_cash=liquid_cash)
    print(f"Capital event - ${ALEX_MAJOR_PURCHASE:,.0f} purchase: {purchase['verdict']} - {purchase['note']}")

    print(f"\nOutcomes scorecard ({month_3} vs {month_2}):")
    print(outcomes_scorecard(categorized_df, month_3, month_2).to_string(index=False))
    print(f"\n{ENGAGEMENT_CADENCE}")

    net_worth = net_worth_snapshot(ALEX_ASSETS, ALEX_LIABILITIES)
    print("\nNet worth snapshot:")
    print(net_worth)
    print("\nDebt payoff comparison:")
    print(debt_payoff_comparison(alex_debts).to_string(index=False))

    # Goal tracker: fill the live net-worth and savings-rate values, then report
    # progress toward each personal goal for the report month.
    live_goals = [dict(goal) for goal in ALEX_GOALS]
    for goal in live_goals:
        if goal["type"] == "net_worth":
            goal["current_amount"] = net_worth["Net Worth"]
        elif goal["type"] == "savings_rate":
            goal["current_amount"] = month_3_summary["Savings Rate"]
    goal_tracker = track_goals(
        live_goals,
        as_of_date=f"{REPORT_MONTH}-28",
        default_monthly=month_3_summary["Net Cash Flow"],
    )
    print("\nGoal tracker:")
    print(goal_tracker.to_string(index=False))

    biggest_budget_miss = month_3_budget.sort_values("Variance ($)").iloc[0].to_dict()
    month_data = {
        "summary": month_3_summary,
        "biggest_budget_miss": biggest_budget_miss,
        "upcoming_total": upcoming_df["Expected Amount"].sum(),
        "upcoming_count": len(upcoming_df),
        "month_label": MONTH_LABELS[month_3],
    }
    alex_commentary = cfo_commentary(month_data)
    print("\nMonth 3 executive summary:")
    print(executive_summary(month_data))
    print("\nMonth 3 CFO commentary from Alex:")
    print(alex_commentary)
    print("\nCommentary human-sound evaluation:")
    print(evaluate_commentary(alex_commentary))

    print(f"\nMonth 2 prioritized action items ({month_2}):")
    print(generate_action_items(categorized_df, month_2, ALEX_BUDGET).to_string(index=False))

    chart_metadata = generate_all_charts(categorized_df, ALEX_BUDGET, charts_output_dir)
    print("\nGenerated chart files:")
    print(chart_metadata[["Chart", "Path"]].to_string(index=False))
    print("\nChart validation results:")
    print(validate_chart_specs(chart_metadata).to_string(index=False))


if __name__ == "__main__":
    main()
