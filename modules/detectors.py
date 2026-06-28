"""Detect recurring and unusual transactions for the CFO Agent."""

import re

import pandas as pd

from modules.config import FIXED_OBLIGATION_VENDORS, UNUSUAL_MINIMUM_THRESHOLDS


NON_EXPENSE_CATEGORIES = {"Income", "Savings Transfer"}


def _category_column(df):
    """Use the CFO category column when it exists."""
    if "assigned_category" in df.columns:
        return "assigned_category"
    return "raw_category"


def _expense_frame(df):
    """Return expense rows with clean date and positive spend amount columns."""
    working_df = df.copy()
    category_col = _category_column(working_df)

    working_df["date"] = pd.to_datetime(working_df["date"])
    working_df["spend_amount"] = working_df["amount"].abs()

    return working_df[
        (working_df["amount"] < 0)
        & (~working_df[category_col].isin(NON_EXPENSE_CATEGORIES))
    ].copy()


def _recurring_vendor_name(vendor):
    """Normalize vendor names so related recurring bills group together."""
    vendor = str(vendor).strip()
    vendor = re.sub(r"\s+-\s+.*$", "", vendor)
    return vendor


def _normalized_vendor(vendor):
    """Normalize a vendor for allowlist and suppression checks."""
    return _recurring_vendor_name(vendor).upper()


def _amounts_are_similar(amounts):
    """Check whether amounts are within 15% of their average."""
    average_amount = amounts.mean()
    if average_amount == 0:
        return False
    differences = (amounts - average_amount).abs() / average_amount
    return bool((differences <= 0.15).all())


def _has_monthly_interval(dates):
    """Check whether the charge timing looks monthly."""
    intervals = dates.sort_values().diff().dt.days.dropna()
    if intervals.empty:
        return False

    has_standard_monthly_gap = ((intervals >= 25) & (intervals <= 35)).any()
    has_monthly_average_cadence = 25 <= intervals.mean() <= 35
    return bool(has_standard_monthly_gap or has_monthly_average_cadence)


def _next_expected_date(dates):
    """Estimate the next charge date from the average historical interval."""
    sorted_dates = dates.sort_values()
    intervals = sorted_dates.diff().dt.days.dropna()
    if intervals.empty:
        return pd.NaT

    rounded_average_interval = round(intervals.mean())
    return sorted_dates.iloc[-1] + pd.Timedelta(days=rounded_average_interval)


def _price_increased(group):
    """Flag if the latest monthly charge is higher than the previous one."""
    sorted_group = group.sort_values("date")
    if len(sorted_group) < 2:
        return False

    previous_amount = sorted_group["spend_amount"].iloc[-2]
    latest_amount = sorted_group["spend_amount"].iloc[-1]
    return latest_amount > previous_amount


def detect_recurring(df):
    """Find recurring charges with similar amounts and monthly timing."""
    expenses = _expense_frame(df)
    expenses["recurring_vendor"] = expenses["vendor"].map(_recurring_vendor_name)

    recurring_rows = []
    for vendor, group in expenses.groupby("recurring_vendor"):
        if len(group) < 2:
            continue

        amounts = group["spend_amount"]
        dates = group["date"]
        if not _amounts_are_similar(amounts) or not _has_monthly_interval(dates):
            continue

        flag = "⚠️ Price increase detected" if _price_increased(group) else ""
        recurring_rows.append(
            {
                "Vendor": vendor,
                "Avg Monthly Amount": round(amounts.mean(), 2),
                "Occurrences": int(len(group)),
                "Next Expected Date": _next_expected_date(dates).date().isoformat(),
                "Flag": flag,
            }
        )

    return pd.DataFrame(
        recurring_rows,
        columns=[
            "Vendor",
            "Avg Monthly Amount",
            "Occurrences",
            "Next Expected Date",
            "Flag",
        ],
    )


def _flag_message(vendor, amount, category, category_average):
    """Build the exact CFO review message for unusual transactions."""
    multiple = amount / category_average
    return (
        f"{vendor} charge of ${amount:.2f} is {multiple:.1f}× your 3-month "
        f"{category} average of ${category_average:.2f}. Review this charge."
    )


def _flag_type(category):
    """Describe why a transaction deserves review."""
    if category == "Medical":
        return "Medical Exception"
    if category == "Transport":
        return "Transport Exception"
    if category == "Shopping":
        return "Large One-Time Charge"
    return "Large Category Exception"


def detect_unusual(df):
    """Flag transactions over 2x their category's 3-month average spend."""
    expenses = _expense_frame(df)
    category_col = _category_column(expenses)
    category_averages = expenses.groupby(category_col)["spend_amount"].mean()

    unusual_rows = []
    for _, row in expenses.iterrows():
        category = row[category_col]
        category_average = category_averages.loc[category]
        amount = row["spend_amount"]
        minimum_threshold = UNUSUAL_MINIMUM_THRESHOLDS.get(category, 75.00)
        normalized_vendor = _normalized_vendor(row["vendor"])

        if normalized_vendor in FIXED_OBLIGATION_VENDORS:
            continue

        if amount <= 2 * category_average or amount < minimum_threshold:
            continue

        unusual_rows.append(
            {
                "Transaction Date": row["date"].date().isoformat(),
                "Vendor": row["vendor"],
                "Amount": round(amount, 2),
                "Category Average": round(category_average, 2),
                "Flag Type": _flag_type(category),
                "Flag Message": _flag_message(
                    row["vendor"], amount, category, category_average
                ),
            }
        )

    return pd.DataFrame(
        unusual_rows,
        columns=[
            "Transaction Date",
            "Vendor",
            "Amount",
            "Category Average",
            "Flag Type",
            "Flag Message",
        ],
    )


def build_clothing_test_frame(df):
    """Add a fictional in-memory Month 2 clothing transaction for testing."""
    test_row = {
        "date": "2026-02-20",
        "vendor": "Test Clothing Retailer",
        "amount": -300.00,
        "raw_category": "clothing",
        "assigned_category": "Shopping",
        "classification_method": "test_in_memory",
    }
    return pd.concat([df, pd.DataFrame([test_row])], ignore_index=True)
