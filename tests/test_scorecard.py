"""Tests for the outcomes scorecard."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.scorecard import ENGAGEMENT_SCOPE, outcomes_scorecard


def _two_month(jan, feb):
    """Build a frame with one income + one expense per month."""
    rows = []
    for month, (income, expense) in (("01", jan), ("02", feb)):
        rows += [
            {"date": f"2026-{month}-01", "vendor": "Payroll", "amount": income,
             "raw_category": "income", "assigned_category": "Income", "classification_method": "t"},
            {"date": f"2026-{month}-10", "vendor": "Spending", "amount": -expense,
             "raw_category": "shopping", "assigned_category": "Shopping", "classification_method": "t"},
        ]
    return pd.DataFrame(rows)


def _trend(scorecard, metric):
    return scorecard[scorecard["Metric"] == metric]["Trend"].iloc[0]


def test_scorecard_marks_improvement_when_spending_falls():
    # Jan: 3000 income, 2000 spend. Feb: 3000 income, 1500 spend (better).
    card = outcomes_scorecard(_two_month((3000, 2000), (3000, 1500)), "2026-02", "2026-01")
    assert _trend(card, "Total Expenses") == "🟢 Improved"   # expenses fell
    assert _trend(card, "Net Cash Flow") == "🟢 Improved"    # net rose
    assert _trend(card, "Savings Rate") == "🟢 Improved"


def test_scorecard_marks_worsening_when_spending_rises():
    card = outcomes_scorecard(_two_month((3000, 1500), (3000, 2200)), "2026-02", "2026-01")
    assert _trend(card, "Total Expenses") == "🔴 Worsened"   # expenses rose
    assert _trend(card, "Net Cash Flow") == "🔴 Worsened"


def test_scorecard_marks_flat_when_unchanged():
    card = outcomes_scorecard(_two_month((3000, 2000), (3000, 2000)), "2026-02", "2026-01")
    assert _trend(card, "Income") == "⚪ Flat"
    assert _trend(card, "Net Cash Flow") == "⚪ Flat"


def test_scorecard_reports_change_values():
    card = outcomes_scorecard(_two_month((3000, 2000), (3000, 1500)), "2026-02", "2026-01")
    expenses = card[card["Metric"] == "Total Expenses"].iloc[0]
    assert expenses["This Month"] == 1500.0
    assert expenses["Last Month"] == 2000.0
    assert expenses["Change"] == -500.0


def test_engagement_scope_is_defined():
    assert len(ENGAGEMENT_SCOPE) >= 5
