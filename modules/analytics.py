"""Financial analytics for the fictional Alex Rivera CFO Agent."""

import re

import pandas as pd

from modules.config import FIXED_OBLIGATION_CATEGORIES, FIXED_OBLIGATION_VENDORS
from modules.detectors import detect_recurring


CATEGORY_ALIASES = {
    "Food": "Food & Dining",
}


def _category_column(df):
    """Use the CFO category column when it exists."""
    if "assigned_category" in df.columns:
        return "assigned_category"
    return "raw_category"


def _prepare_dates(df):
    """Return a copy with date values ready for month filtering."""
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    return working_df


def _filter_month(df, month):
    """Filter rows to one YYYY-MM reporting month."""
    working_df = _prepare_dates(df)
    return working_df[working_df["date"].dt.to_period("M").astype(str) == month]


def _canonical_category(category):
    """Translate user-facing budget names to CFO category names."""
    return CATEGORY_ALIASES.get(category, category)


def _variance_driver(category, actual_amount, budget_amount):
    """Explain the main budget variance driver in CFO-ready language."""
    if actual_amount <= budget_amount:
        return "Actual spend stayed at or below budget."
    drivers = {
        "Food & Dining": "Dining frequency and grocery basket size exceeded plan.",
        "Transport": "Ride-share activity and one-time transport costs exceeded plan.",
        "Subscriptions": "Recurring bills and gym charges exceeded the subscription budget.",
        "Shopping": "Retail and household purchases exceeded the shopping allowance.",
        "Medical": "Health-related transactions drove spend above the baseline.",
        "Housing": "Housing spend exceeded the fixed rent assumption.",
        "Education": "Education or student-loan costs exceeded plan.",
    }
    return drivers.get(category, "Actual spend exceeded the category plan.")


def _forward_impact(category, variance_dollars):
    """Describe what the variance means if the pattern repeats."""
    if variance_dollars >= 0:
        return "No negative forward cash-flow impact if current behavior continues."
    overage = abs(variance_dollars)
    return (
        f"If repeated next month, {category} would reduce net cash flow by "
        f"${overage:,.2f} versus budget."
    )


def _recommended_action(category, budget_amount, actual_amount):
    """Create a concise category-level corrective action."""
    if actual_amount <= budget_amount:
        return f"Maintain {category} spend at or below the ${budget_amount:,.2f} plan."
    return f"Reset {category} spend to the ${budget_amount:,.2f} monthly plan."


def _income_mask(df):
    """Rows that count as real income: positive amounts categorized as Income.

    Defining income by category (not just by a positive sign) keeps refunds,
    reimbursements, and credits out of the income total. When the frame has not
    been categorized yet, fall back to the sign so older callers still work.
    """
    if "assigned_category" in df.columns:
        return (df["amount"] > 0) & (df["assigned_category"] == "Income")
    return df["amount"] > 0


def monthly_summary(df, month):
    """Return income, expenses, net cash flow, and savings rate for one month."""
    month_df = _filter_month(df, month)

    income_mask = _income_mask(month_df)
    income = float(month_df.loc[income_mask, "amount"].sum())
    # Everything that is not real income is spending. Positive amounts in
    # spending categories are refunds/credits that reduce the net expense.
    total_expenses = float(-month_df.loc[~income_mask, "amount"].sum())
    net_cash_flow = float(income - total_expenses)
    savings_rate = float((net_cash_flow / income * 100) if income else 0.0)

    return {
        "Income": round(income, 2),
        "Total Expenses": round(total_expenses, 2),
        "Net Cash Flow": round(net_cash_flow, 2),
        "Savings Rate": round(savings_rate, 2),
    }


def budget_vs_actual(df, month, budget_dict):
    """Compare monthly actual spend against a category budget."""
    month_df = _filter_month(df, month)
    category_col = _category_column(month_df)
    # Net spend per category: outflows minus any refunds/credits in that category.
    spend_df = month_df[~_income_mask(month_df)].copy()
    spend_df["net_spend"] = -spend_df["amount"]
    actuals = spend_df.groupby(category_col)["net_spend"].sum()

    rows = []
    for budget_category, budget_amount in budget_dict.items():
        category = _canonical_category(budget_category)
        actual_amount = float(actuals.get(category, 0.0))
        variance_dollars = budget_amount - actual_amount
        variance_percent = (
            (variance_dollars / budget_amount) * 100 if budget_amount else 0.0
        )

        if actual_amount <= budget_amount:
            color_flag = "🟢 under budget"
        elif actual_amount <= budget_amount * 1.10:
            color_flag = "🟡 within 10%"
        else:
            color_flag = "🔴 over budget"

        rows.append(
            {
                "Category": category,
                "Budget Amount": round(float(budget_amount), 2),
                "Actual Amount": round(actual_amount, 2),
                "Variance ($)": round(variance_dollars, 2),
                "Variance (%)": round(variance_percent, 2),
                "Color Flag": color_flag,
                "Variance Driver": _variance_driver(category, actual_amount, budget_amount),
                "Forward Impact": _forward_impact(category, variance_dollars),
                "Recommended Action": _recommended_action(
                    category, budget_amount, actual_amount
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "Category",
            "Budget Amount",
            "Actual Amount",
            "Variance ($)",
            "Variance (%)",
            "Color Flag",
            "Variance Driver",
            "Forward Impact",
            "Recommended Action",
        ],
    )


def cumulative_budget_vs_actual(df, budget_dict):
    """Compare all available months against cumulative category budgets."""
    working_df = _prepare_dates(df)
    months = sorted(working_df["date"].dt.to_period("M").astype(str).unique())
    month_count = len(months)
    category_col = _category_column(working_df)
    # Net spend per category: outflows minus any refunds/credits in that category.
    spend_df = working_df[~_income_mask(working_df)].copy()
    spend_df["net_spend"] = -spend_df["amount"]
    actuals = spend_df.groupby(category_col)["net_spend"].sum()

    rows = []
    for budget_category, monthly_budget in budget_dict.items():
        category = _canonical_category(budget_category)
        budget_amount = float(monthly_budget) * month_count
        actual_amount = float(actuals.get(category, 0.0))
        variance_dollars = budget_amount - actual_amount
        variance_percent = (
            (variance_dollars / budget_amount) * 100 if budget_amount else 0.0
        )
        rows.append(
            {
                "Category": category,
                "3-Month Budget": round(budget_amount, 2),
                "3-Month Actual": round(actual_amount, 2),
                "Variance ($)": round(variance_dollars, 2),
                "Variance (%)": round(variance_percent, 2),
            }
        )

    return pd.DataFrame(rows)


def mom_comparison(df):
    """Return month-over-month percent change for each expense category."""
    working_df = _prepare_dates(df)
    category_col = _category_column(working_df)
    expense_df = working_df[working_df["amount"] < 0].copy()
    expense_df["month"] = expense_df["date"].dt.to_period("M").astype(str)
    expense_df["spend_amount"] = expense_df["amount"].abs()

    monthly_spend = (
        expense_df.pivot_table(
            index=category_col,
            columns="month",
            values="spend_amount",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .round(2)
    )

    percent_change = monthly_spend.pct_change(axis=1).replace(
        [float("inf"), float("-inf")], pd.NA
    )
    percent_change = (percent_change * 100).round(2)

    rows = []
    months = list(monthly_spend.columns)
    for category in monthly_spend.index:
        row = {"Category": category}
        for month in months:
            row[f"{month} Spend"] = round(float(monthly_spend.loc[category, month]), 2)
            change_value = percent_change.loc[category, month]
            row[f"{month} MoM Change (%)"] = (
                None if pd.isna(change_value) else round(float(change_value), 2)
            )
        rows.append(row)

    return pd.DataFrame(rows)


def _recurring_vendor_name(vendor):
    """Match the recurring detector's vendor grouping."""
    vendor = str(vendor).strip()
    vendor = re.sub(r"\s+-\s+.*$", "", vendor)
    return vendor


def _normalized_recurring_vendor(vendor):
    """Normalize recurring vendors for fixed-obligation matching."""
    return _recurring_vendor_name(vendor).upper()


def _next_projected_date(group, latest_date):
    """Project the next recurring date after the report date."""
    sorted_dates = group["date"].sort_values()
    same_day_each_month = sorted_dates.dt.day.nunique() == 1

    if same_day_each_month:
        expected_date = sorted_dates.iloc[-1] + pd.DateOffset(months=1)
    else:
        intervals = sorted_dates.diff().dt.days.dropna()
        interval_days = round(intervals.mean()) if not intervals.empty else 30
        expected_date = sorted_dates.iloc[-1] + pd.Timedelta(days=interval_days)

    while expected_date <= latest_date:
        if same_day_each_month:
            expected_date = expected_date + pd.DateOffset(months=1)
        else:
            expected_date = expected_date + pd.Timedelta(days=interval_days)

    return expected_date


def upcoming_obligations(df):
    """Project recurring charges expected in the next 30 days."""
    working_df = _prepare_dates(df)
    latest_date = working_df["date"].max()
    window_start = latest_date + pd.Timedelta(days=1)
    window_end = latest_date + pd.Timedelta(days=30)

    recurring_df = detect_recurring(working_df)
    if recurring_df.empty:
        return pd.DataFrame(columns=["Vendor", "Expected Date", "Expected Amount"])

    recurring_df = recurring_df[
        recurring_df["Vendor"].map(_normalized_recurring_vendor).isin(
            FIXED_OBLIGATION_VENDORS
        )
    ].copy()
    if recurring_df.empty:
        return pd.DataFrame(columns=["Vendor", "Expected Date", "Expected Amount"])

    expense_df = working_df[working_df["amount"] < 0].copy()
    expense_df["recurring_vendor"] = expense_df["vendor"].map(_recurring_vendor_name)
    category_col = _category_column(expense_df)
    expense_df = expense_df[
        expense_df[category_col].isin(FIXED_OBLIGATION_CATEGORIES)
        | expense_df["recurring_vendor"].map(_normalized_recurring_vendor).isin(
            FIXED_OBLIGATION_VENDORS
        )
    ].copy()

    recurring_df["Expected Date"] = recurring_df["Vendor"].map(
        lambda vendor: _next_projected_date(
            expense_df[expense_df["recurring_vendor"] == vendor], latest_date
        )
    )
    upcoming_df = recurring_df[
        (recurring_df["Expected Date"] >= window_start)
        & (recurring_df["Expected Date"] <= window_end)
    ].copy()
    upcoming_df["Expected Date"] = upcoming_df["Expected Date"].dt.date.astype(str)
    upcoming_df["Expected Amount"] = upcoming_df["Avg Monthly Amount"]

    return upcoming_df[["Vendor", "Expected Date", "Expected Amount"]].reset_index(
        drop=True
    )
