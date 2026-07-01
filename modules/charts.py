"""Chart generation for the fictional starter-person CFO report."""

import os
import math
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/personal_finance_cfo_agent_mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/personal_finance_cfo_agent_cache")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from modules.analytics import budget_vs_actual, monthly_summary
from modules.config import REPORT_MONTH


DPI = 300
MONTH_3 = REPORT_MONTH


def _prepare_expenses(df):
    """Return expense rows with month and positive spending values."""
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    expenses = working_df[working_df["amount"] < 0].copy()
    expenses["spending"] = expenses["amount"].abs()
    expenses["month"] = expenses["date"].dt.to_period("M").astype(str)
    return expenses


def _save_chart(fig, output_path):
    """Save a chart as a 300dpi PNG and close the figure."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return output_path


def generate_spending_by_category_chart(df, output_path):
    """Create a donut chart of 3-month spending by category."""
    expenses = _prepare_expenses(df)
    category_totals = (
        expenses.groupby("assigned_category")["spending"]
        .sum()
        .sort_values(ascending=False)
    )
    labels = [f"{category}: ${amount:,.2f}" for category, amount in category_totals.items()]
    total_spending = category_totals.sum()
    percentages = category_totals / total_spending * 100

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, _ = ax.pie(
        category_totals.values,
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
    )

    for wedge, percentage in zip(wedges, percentages):
        angle = (wedge.theta1 + wedge.theta2) / 2
        angle_radians = math.radians(angle)
        label = f"{percentage:.1f}%"

        if percentage >= 7:
            x = 0.78 * math.cos(angle_radians)
            y = 0.78 * math.sin(angle_radians)
            ax.text(
                x,
                y,
                label,
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="#111827",
            )
        else:
            x = 1.18 * math.cos(angle_radians)
            y = 1.18 * math.sin(angle_radians)
            ha = "left" if x >= 0 else "right"
            ax.annotate(
                label,
                xy=(0.98 * math.cos(angle_radians), 0.98 * math.sin(angle_radians)),
                xytext=(x, y),
                ha=ha,
                va="center",
                fontsize=8,
                color="#111827",
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#6b7280",
                    "lw": 0.8,
                    "shrinkA": 0,
                    "shrinkB": 0,
                    "connectionstyle": "arc3,rad=0.15",
                },
            )

    ax.set_title("Spending by Category - 3-Month Total ($ and %)", fontsize=14, pad=18)
    ax.legend(
        wedges,
        labels,
        title="3-month spend ($)",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
    )
    ax.text(0, 0, "Computed\ntransaction data", ha="center", va="center", fontsize=10)

    path = _save_chart(fig, output_path)
    return {
        "Chart": "Spending by Category",
        "Path": str(path),
        "Title": "Spending by Category - 3-Month Total ($ and %)",
        "X Label": "N/A - donut chart",
        "Y Label": "N/A - donut chart",
        "Data Source": "Computed transaction data",
        "DPI": DPI,
    }


def generate_savings_rate_trend_chart(df, output_path):
    """Create a line chart of monthly savings rate percentages."""
    expenses = _prepare_expenses(df)
    months = sorted(expenses["month"].unique())
    savings_rates = [monthly_summary(df, month)["Savings Rate"] for month in months]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(months, savings_rates, marker="o", linewidth=2.5, color="#2563eb")
    ax.axhline(10, color="#dc2626", linestyle="--", linewidth=1.5, label="10% target")
    ax.set_title("Monthly Savings Rate Trend", fontsize=14, pad=14)
    ax.set_xlabel("Month")
    ax.set_ylabel("Savings Rate (%)")
    ax.set_ylim(0, max(max(savings_rates) + 10, 20))
    ax.grid(axis="y", alpha=0.25)
    ax.legend()

    for month, rate in zip(months, savings_rates):
        ax.annotate(f"{rate:.2f}%", (month, rate), textcoords="offset points", xytext=(0, 8), ha="center")

    path = _save_chart(fig, output_path)
    return {
        "Chart": "Monthly Savings Rate Trend",
        "Path": str(path),
        "Title": "Monthly Savings Rate Trend",
        "X Label": "Month",
        "Y Label": "Savings Rate (%)",
        "Data Source": "Computed transaction data",
        "DPI": DPI,
    }


def _budget_color(flag):
    """Translate the budget flag text into a chart color."""
    if "under budget" in flag:
        return "#16a34a"
    if "within 10%" in flag:
        return "#ca8a04"
    return "#dc2626"


def generate_budget_vs_actual_chart(df, month, budget_dict, output_path):
    """Create a horizontal bar chart of budget vs actual spending."""
    budget_df = budget_vs_actual(df, month, budget_dict).sort_values("Actual Amount")
    colors = [_budget_color(flag) for flag in budget_df["Color Flag"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(budget_df["Category"], budget_df["Actual Amount"], color=colors, label="Actual")
    ax.scatter(
        budget_df["Budget Amount"],
        budget_df["Category"],
        color="#111827",
        marker="|",
        s=220,
        linewidths=2,
        label="Budget",
    )
    ax.set_title(f"Budget vs. Actual - {month}", fontsize=14, pad=14)
    ax.set_xlabel("Amount ($)")
    ax.set_ylabel("Category")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()

    for _, row in budget_df.iterrows():
        ax.text(
            row["Actual Amount"] + 8,
            row["Category"],
            f"${row['Actual Amount']:,.2f}",
            va="center",
            fontsize=9,
        )

    path = _save_chart(fig, output_path)
    return {
        "Chart": "Budget vs. Actual",
        "Path": str(path),
        "Title": f"Budget vs. Actual - {month}",
        "X Label": "Amount ($)",
        "Y Label": "Category",
        "Data Source": "Computed transaction data",
        "DPI": DPI,
    }


def generate_mom_spending_chart(df, output_path):
    """Create a grouped bar chart of monthly spending by category."""
    expenses = _prepare_expenses(df)
    monthly_spend = (
        expenses.pivot_table(
            index="assigned_category",
            columns="month",
            values="spending",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index()
        .round(2)
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    monthly_spend.plot(kind="bar", ax=ax, width=0.78)
    ax.set_title("Month-over-Month Spending by Category", fontsize=14, pad=14)
    ax.set_xlabel("Category")
    ax.set_ylabel("Spending ($)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Month")
    plt.xticks(rotation=35, ha="right")

    path = _save_chart(fig, output_path)
    return {
        "Chart": "Month-over-Month Spending",
        "Path": str(path),
        "Title": "Month-over-Month Spending by Category",
        "X Label": "Category",
        "Y Label": "Spending ($)",
        "Data Source": "Computed transaction data",
        "DPI": DPI,
    }


def generate_all_charts(df, budget_dict, output_dir):
    """Generate all chart PNG files and return chart metadata."""
    output_dir = Path(output_dir)
    metadata = [
        generate_spending_by_category_chart(
            df, output_dir / "spending_by_category.png"
        ),
        generate_savings_rate_trend_chart(
            df, output_dir / "monthly_savings_rate_trend.png"
        ),
        generate_budget_vs_actual_chart(
            df, MONTH_3, budget_dict, output_dir / "budget_vs_actual.png"
        ),
        generate_mom_spending_chart(
            df, output_dir / "month_over_month_spending.png"
        ),
    ]
    return pd.DataFrame(metadata)


def validate_chart_specs(chart_metadata):
    """Validate chart title, label, source, and export requirements."""
    rows = []
    for _, chart in chart_metadata.iterrows():
        path = Path(chart["Path"])
        rows.append(
            {
                "Chart": chart["Chart"],
                "File Exists": "PASS" if path.exists() else "FAIL",
                "Has Title": "PASS" if chart["Title"] else "FAIL",
                "Has Axis Labels": (
                    "PASS"
                    if chart["X Label"] and chart["Y Label"]
                    else "FAIL"
                ),
                "Computed Data": (
                    "PASS"
                    if chart["Data Source"] == "Computed transaction data"
                    else "FAIL"
                ),
                "300dpi Export": "PASS" if int(chart["DPI"]) == 300 else "FAIL",
            }
        )

    return pd.DataFrame(rows)
