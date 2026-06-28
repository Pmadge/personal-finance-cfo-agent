"""Chart generation for draft personal CFO reports.

These charts use only reviewed fake/sample data while personal mode is disabled.
"""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/personal_finance_cfo_agent_mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/personal_finance_cfo_agent_cache")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

DPI = 300


def _save_chart(fig, output_path):
    """Save a chart as a PNG and close the figure."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return output_path


def build_personal_insights(report_df):
    """Return simple CFO-style insights from report-ready transactions."""
    income = float(report_df.loc[report_df["amount"] > 0, "amount"].sum())
    expenses = float(-report_df.loc[report_df["amount"] < 0, "amount"].sum())
    net_cash_flow = income - expenses
    savings_rate = (net_cash_flow / income * 100) if income else 0.0

    spending = (
        report_df.assign(spend=report_df["amount"].where(report_df["amount"] < 0, 0).abs())
        .groupby("assigned_category", as_index=False)["spend"]
        .sum()
        .sort_values("spend", ascending=False)
    )
    expense_spending = spending[spending["spend"] > 0]
    if expense_spending.empty:
        largest_category = "None"
        largest_amount = 0.0
    else:
        largest = expense_spending.iloc[0]
        largest_category = str(largest["assigned_category"])
        largest_amount = float(largest["spend"])

    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net_cash_flow": round(net_cash_flow, 2),
        "savings_rate": round(savings_rate, 2),
        "largest_spending_category": largest_category,
        "largest_spending_amount": round(largest_amount, 2),
    }


def generate_spending_by_category_chart(report_df, output_path):
    """Create a horizontal bar chart of spending by reviewed category."""
    spending = (
        report_df.assign(spend=report_df["amount"].where(report_df["amount"] < 0, 0).abs())
        .groupby("assigned_category", as_index=False)["spend"]
        .sum()
    )
    spending = spending[spending["spend"] > 0].sort_values("spend", ascending=True)
    if spending.empty:
        import pandas as pd

        spending = pd.DataFrame([{"assigned_category": "No expenses", "spend": 0.0}])

    positions = list(range(len(spending)))
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(positions, spending["spend"], color="#2563eb")
    ax.set_yticks(positions, spending["assigned_category"])
    ax.set_title("Spending by Category", fontsize=14, pad=12)
    ax.set_xlabel("Spend ($)")
    ax.grid(axis="x", alpha=0.25)
    for position, (_, row) in zip(positions, spending.iterrows()):
        spend_value = float(row.to_dict()["spend"])
        ax.text(spend_value + 2, position, f"${spend_value:,.2f}", va="center", fontsize=9)
    return _save_chart(fig, output_path)


def generate_cash_flow_waterfall_chart(report_df, output_path):
    """Create a true income-to-net-cash-flow waterfall chart.

    A real waterfall shows how income is reduced by expenses to arrive at net
    cash flow: Income rises from zero, Expenses steps down from income to net,
    and Net Cash Flow is the final running total. Because expenses always equal
    income minus net, the expenses step bottom is the net value and its height
    is the expense total, which keeps the chart correct even when net is negative.
    """
    insights = build_personal_insights(report_df)
    income = insights["income"]
    expenses = insights["expenses"]
    net = insights["net_cash_flow"]

    labels = ["Income", "Expenses", "Net Cash Flow"]
    positions = range(len(labels))
    # (bottom, height) for each bar so the steps connect like a waterfall.
    bottoms = [0.0, net, 0.0]
    heights = [income, expenses, net]
    bar_colors = ["#16a34a", "#dc2626", "#2563eb" if net >= 0 else "#dc2626"]
    # Signed deltas for the on-bar labels: income adds, expenses subtract.
    deltas = [income, -expenses, net]

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.bar(positions, heights, bottom=bottoms, color=bar_colors)
    ax.axhline(0, color="#111827", linewidth=0.8)

    # Dashed connectors so the eye follows income down to net cash flow.
    ax.plot([0, 1], [income, income], color="#9ca3af", linewidth=0.8, linestyle="--")
    ax.plot([1, 2], [net, net], color="#9ca3af", linewidth=0.8, linestyle="--")

    ax.set_xticks(list(positions), labels)
    ax.set_title("Cash Flow Waterfall", fontsize=14, pad=12)
    ax.set_ylabel("Amount ($)")
    ax.grid(axis="y", alpha=0.25)

    tops = [bottom + height for bottom, height in zip(bottoms, heights)]
    for position, top, delta in zip(positions, tops, deltas):
        offset = 20 if delta >= 0 else -10
        money = f"${delta:,.2f}" if delta >= 0 else f"-${abs(delta):,.2f}"
        ax.text(position, top + offset, money, ha="center", fontsize=9)

    return _save_chart(fig, output_path)


def generate_personal_report_charts(report_df, charts_dir):
    """Generate all personal report chart PNGs and return their paths."""
    charts_dir = Path(charts_dir)
    return {
        "spending_by_category": generate_spending_by_category_chart(
            report_df,
            charts_dir / "personal_spending_by_category.png",
        ),
        "cash_flow_waterfall": generate_cash_flow_waterfall_chart(
            report_df,
            charts_dir / "personal_cash_flow_waterfall.png",
        ),
    }
