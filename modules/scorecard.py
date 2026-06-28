"""Outcomes scorecard and engagement summary for the personal CFO Agent.

The "service wrapper" pillar: measure success by outcomes, not effort, and make
the engagement scope and cadence explicit. The scorecard compares the report
month to the prior month on the metrics that matter and shows the direction of
travel, so progress (or slippage) is visible at a glance.
"""

import pandas as pd

from modules.analytics import monthly_summary

# (display label, monthly_summary key, higher_is_better)
SCORECARD_METRICS = [
    ("Income", "Income", True),
    ("Total Expenses", "Total Expenses", False),
    ("Net Cash Flow", "Net Cash Flow", True),
    ("Savings Rate", "Savings Rate", True),
]

ENGAGEMENT_SCOPE = [
    "Monthly close: categorized cash flow, budget vs actual, and a full CFO report.",
    "Cash runway and a rolling 12-month cash projection.",
    "What-if scenario planning for major decisions.",
    "A personal risk register reviewed every month.",
    "Goal tracking against your savings, debt, and net-worth targets.",
    "Capital-event readiness checks for home and large purchases.",
]
ENGAGEMENT_CADENCE = (
    "Cadence: a monthly close and report, a quarterly deep-dive review, and "
    "always-on guidance between cycles. Success is measured by your outcomes - "
    "savings rate, net worth, debt reduction, and goal progress - not hours billed."
)


def _trend(change, higher_is_better):
    """Direction of travel for a metric change."""
    if abs(change) < 0.005:
        return "⚪ Flat"
    improved = (change > 0) if higher_is_better else (change < 0)
    return "🟢 Improved" if improved else "🔴 Worsened"


def outcomes_scorecard(df, report_month, prior_month):
    """Compare the report month to the prior month across the key CFO metrics."""
    current = monthly_summary(df, report_month)
    prior = monthly_summary(df, prior_month)

    rows = []
    for label, key, higher_is_better in SCORECARD_METRICS:
        current_value = current[key]
        prior_value = prior[key]
        change = round(current_value - prior_value, 2)
        rows.append({
            "Metric": label,
            "This Month": current_value,
            "Last Month": prior_value,
            "Change": change,
            "Trend": _trend(change, higher_is_better),
        })
    return pd.DataFrame(rows, columns=["Metric", "This Month", "Last Month", "Change", "Trend"])
