"""Narrative writing helpers for the fictional starter-person CFO report."""


def _money(amount):
    """Format a number as a CFO-style dollar amount."""
    return f"${float(amount):,.2f}"


def _percent(amount):
    """Format a number as a percentage."""
    return f"{float(amount):.2f}%"


def executive_summary(month_data):
    """Create a 3-sentence executive summary with specific numbers."""
    summary = month_data["summary"]
    biggest_budget_miss = month_data["biggest_budget_miss"]
    upcoming_total = month_data["upcoming_total"]
    upcoming_count = month_data["upcoming_count"]
    month_label = month_data.get("month_label", "This month")

    return (
        f"{month_label} net cash flow was {_money(summary['Net Cash Flow'])}, with a "
        f"{_percent(summary['Savings Rate'])} savings rate. "
        f"{biggest_budget_miss['Category']} spending was "
        f"{_money(biggest_budget_miss['Actual Amount'])}, exceeding the "
        f"{_money(biggest_budget_miss['Budget Amount'])} budget by "
        f"{_money(abs(biggest_budget_miss['Variance ($)']))}. "
        f"Next month has {upcoming_count} projected recurring obligations totaling "
        f"{_money(upcoming_total)}."
    )


def cfo_commentary(month_data):
    """Create first-person commentary from the starter person's perspective."""
    biggest_budget_miss = month_data["biggest_budget_miss"]
    summary = month_data["summary"]
    upcoming_total = month_data["upcoming_total"]
    commitment = month_data.get("commitment")

    category = biggest_budget_miss["Category"]
    actual = biggest_budget_miss["Actual Amount"]
    budget = biggest_budget_miss["Budget Amount"]
    variance = abs(biggest_budget_miss["Variance ($)"])
    direction = "over" if biggest_budget_miss["Variance ($)"] < 0 else "under"
    commitment = commitment or (
        f"Next month I plan to cap {category} at {_money(budget)} to preserve at "
        f"least {_money(variance)} of cash flow."
    )

    return (
        f"This month I spent {_money(actual)} on {category}, which was {direction} "
        f"my {_money(budget)} budget by {_money(variance)}. "
        f"I still generated {_money(summary['Net Cash Flow'])} of net cash flow, "
        f"but the {_percent(summary['Savings Rate'])} savings rate could be stronger "
        f"if I controlled repeat food purchases. "
        f"I also have {_money(upcoming_total)} of recurring obligations coming due "
        "next month, so I need to make the first week tighter. "
        f"{commitment}"
    )


def evaluate_commentary(commentary):
    """Return a simple human-readability assessment for the generated commentary."""
    first_person_markers = [" I ", " my ", " I still ", " I also "]
    plain_language_markers = ["could be stronger", "need to", "plan to"]
    has_first_person = any(marker in f" {commentary} " for marker in first_person_markers)
    has_plain_language = any(marker in commentary for marker in plain_language_markers)
    has_commitment = "Next month I plan to " in commentary and commentary.endswith(".")

    if has_first_person and has_plain_language and has_commitment:
        return "PASS - The commentary sounds like a real person wrote it."

    return "FAIL - The commentary needs to sound more personal and actionable."
