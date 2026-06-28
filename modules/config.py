"""Shared assumptions for the fictional Alex Rivera CFO Agent."""

MODEL_VERSION = "CFO Agent v1.1"
PERSONA_NAME = "Alex Rivera"
FICTIONAL_DATA_NOTICE = "fictional Alex Rivera data"

REPORT_MONTH = "2026-03"
REPORT_MONTH_LABEL = "March 2026"
TREND_MONTHS = ["2026-01", "2026-02", "2026-03"]
MONTH_LABELS = {
    "2026-01": "January",
    "2026-02": "February",
    "2026-03": "March",
}

APPROVED_CATEGORIES = [
    "Housing",
    "Food & Dining",
    "Transport",
    "Subscriptions",
    "Entertainment",
    "Income",
    "Medical",
    "Education",
    "Shopping",
    "Savings Transfer",
    "Misc",
]

ALEX_BUDGET = {
    "Housing": 900,
    "Food": 250,
    "Transport": 80,
    "Subscriptions": 40,
    "Entertainment": 60,
    "Shopping": 100,
    "Misc": 50,
}

ALEX_ASSETS = {
    "Checking": 1200,
    "Savings": 3400,
    "Investments": 0,
}

ALEX_LIABILITIES = {
    "Student Loan": {"balance": 18000, "interest_rate": 5.5},
    "Car Loan": {"balance": 6500, "interest_rate": 7.2},
    "Credit Card": {"balance": 0, "interest_rate": 0},
}

FIXED_OBLIGATION_CATEGORIES = {"Housing", "Subscriptions", "Education"}
FIXED_OBLIGATION_VENDORS = {
    "CITYFIT GYM",
    "FEDERAL STUDENT LOAN SERVICER",
    "HULU",
    "NETFLIX",
    "PARKSIDE RENT PORTAL",
    "SPOTIFY",
    "VERIZON WIRELESS",
}

UNUSUAL_MINIMUM_THRESHOLDS = {
    "Food & Dining": 100.00,
    "Transport": 100.00,
    "Subscriptions": 100.00,
    "Medical": 100.00,
    "Shopping": 150.00,
    "Housing": 500.00,
    "Education": 250.00,
    "Misc": 75.00,
    "Entertainment": 75.00,
}

FORECAST_SCENARIOS = {
    "Upside": {"variable_spend_change": -0.10, "unusual_charge": 0.00},
    "Base": {"variable_spend_change": 0.00, "unusual_charge": 0.00},
    "Downside": {"variable_spend_change": 0.10, "unusual_charge": 300.00},
}

SAVINGS_RATE_TARGET = 10.00

# Sample personal goals for the fictional persona. current_amount values for the
# net-worth and savings-rate goals are placeholders; main.py fills them from live
# computed numbers so the tracker reflects the actual report month.
ALEX_GOALS = [
    {
        "name": "Emergency Fund",
        "type": "savings",
        "target_amount": 6000.00,
        "current_amount": ALEX_ASSETS["Savings"],
        "target_date": "2026-12-31",
    },
    {
        "name": "Pay Off Car Loan",
        "type": "debt_payoff",
        "target_amount": 0.00,
        "current_amount": ALEX_LIABILITIES["Car Loan"]["balance"],
        "starting_amount": ALEX_LIABILITIES["Car Loan"]["balance"],
        "interest_rate": ALEX_LIABILITIES["Car Loan"]["interest_rate"],
        "monthly_contribution": 300.00,
        "target_date": "2028-12-31",
    },
    {
        "name": "Reach Positive Net Worth",
        "type": "net_worth",
        "target_amount": 0.00,
        "current_amount": -19900.00,
        "target_date": "2030-12-31",
    },
    {
        "name": "Hit 10% Savings Rate",
        "type": "savings_rate",
        "target_amount": SAVINGS_RATE_TARGET,
        "current_amount": 0.00,
    },
]

# Sample what-if scenarios for the fictional persona. Each flexes the baseline
# monthly picture; see modules/scenarios.py for the supported adjustment keys.
ALEX_SCENARIOS = [
    {"name": "Lose job (no income)", "monthly_income": 0.00},
    {"name": "Get a $500/mo raise", "monthly_income_change": 500.00},
    {"name": "Move (+$400/mo rent)", "monthly_expense_change": 400.00},
    {"name": "Cut variable spending 20%", "variable_spend_pct": -0.20},
    {"name": "$5,000 one-time purchase", "one_time_cost": 5000.00},
]

# Sample capital-event inputs for the fictional persona.
ALEX_HOME_TARGET = {
    "home_price": 350000.00,
    "down_payment_pct": 20.0,
    "mortgage_rate": 7.0,
    "term_years": 30,
}
ALEX_MAJOR_PURCHASE = 8000.00  # e.g. a used car bought from cash

# Fictional financial profile that feeds the full pillar suite into the draft
# PERSONAL report. These sample assets/liabilities/goals stand in until a real
# personal-data workflow is approved; they are intentionally a different persona
# from Alex so the personal report path is exercised on its own inputs.
SAMPLE_PERSONAL_PROFILE = {
    "assets": {"Checking": 3000.00, "Savings": 9000.00, "Investments": 12000.00},
    "liabilities": {
        "Credit Card": {"balance": 4000.00, "interest_rate": 21.0},
        "Student Loan": {"balance": 14000.00, "interest_rate": 5.5},
    },
    "monthly_debt_payment": 600.00,
    "goals": [
        {"name": "Emergency Fund", "type": "savings", "target_amount": 12000.00,
         "current_amount": 9000.00, "target_date": "2026-12-31"},
        {"name": "Pay Off Credit Card", "type": "debt_payoff", "target_amount": 0.00,
         "current_amount": 4000.00, "starting_amount": 4000.00, "interest_rate": 21.0,
         "monthly_contribution": 400.00, "target_date": "2027-06-30"},
        {"name": "Reach $50k Net Worth", "type": "net_worth", "target_amount": 50000.00,
         "current_amount": 0.00, "target_date": "2029-12-31"},
        {"name": "Hit 15% Savings Rate", "type": "savings_rate", "target_amount": 15.00,
         "current_amount": 0.00},
    ],
    "scenarios": [
        {"name": "Lose job (no income)", "monthly_income": 0.00},
        {"name": "Get a $400/mo raise", "monthly_income_change": 400.00},
        {"name": "Move (+$300/mo rent)", "monthly_expense_change": 300.00},
        {"name": "$3,000 one-time purchase", "one_time_cost": 3000.00},
    ],
    "home_target": {"home_price": 300000.00, "down_payment_pct": 10.0,
                    "mortgage_rate": 7.0, "term_years": 30},
    "major_purchase": 3000.00,
}
