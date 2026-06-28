# Personal Finance CFO Agent — Portfolio Summary

A local Python system that turns raw transaction data into a family office-style
monthly CFO reporting packet: categorized cash flow, budget variance analysis,
risk flags, forecasts, net worth, prioritized action items, charts, and narrative
commentary. It is not a budgeting app. It is an FP&A (Financial Planning and
Analysis) reporting system designed to explain what happened, why it matters,
what comes next, and what action to take.

All examples below use a fully fictional persona, "Alex Rivera." No real financial
data is used anywhere in this project.

## What it produces

A single run generates an 11-page monthly CFO report PDF, a 3-month trend summary,
and a set of analysis charts. Representative pages:

### Cover and executive summary
![Monthly CFO report cover](screenshots/report_01_cover.png)

![Executive summary with CFO commentary and budget variance notes](screenshots/report_02_executive_summary.png)

### Outcomes scorecard
This month vs last month on the metrics that matter (income, expenses, net cash
flow, savings rate), with the direction of travel - measuring success by outcomes,
not effort.

![Outcomes scorecard comparing this month to last month](screenshots/report_scorecard.png)

### Budget variance and prioritized action items
![Budget vs actual analysis](screenshots/report_04_budget_vs_actual.png)

![AI action items and the self-check model version log](screenshots/report_11_action_items.png)

### Cash runway and 12-month projection
How long liquid cash would last if income stopped (in months and weeks), an
essential-bills-only bare-bones runway, and a month-by-month projected ending-cash
trajectory for the next year.

![Cash runway metrics and a 12-month cash projection table](screenshots/report_cash_runway.png)

### What-if scenarios
Side-by-side impact of life changes (job loss, a raise, a move, cutting spending,
a big one-time purchase) on monthly net cash flow, runway, projected cash a year
out, and cash-out risk.

![What-if scenario comparison table](screenshots/report_scenarios.png)

### Goal tracker
Progress toward each personal goal (savings, debt payoff, net worth, savings
rate): how far along, how much remains, and whether the current pace keeps it on
schedule for the target date.

![Goal tracker showing progress and on-track status per goal](screenshots/report_goal_tracker.png)

### Risk register
A "what could go wrong" view rating six personal risks (emergency fund, income
concentration, debt load, cash flow, housing cost burden, insurance coverage) with
a finding and recommendation for each.

![Risk register rating six personal financial risks](screenshots/report_risk_register.png)

### Capital-event playbook (home purchase readiness)
A numbers-backed readiness verdict for a major money decision: down payment plus
closing costs vs cash on hand, estimated monthly mortgage payment (PITI) vs income,
whether buying preserves the emergency fund, and the specific gaps to close. Plus a
quick affordability check for any large one-time purchase.

![Home purchase readiness with verdict, metrics, and gaps](screenshots/report_capital_event.png)

## Analysis charts

| | |
|---|---|
| ![Spending by category](screenshots/chart_spending_by_category.png) | ![Monthly savings rate trend](screenshots/chart_monthly_savings_rate_trend.png) |
| ![Budget vs actual](screenshots/chart_budget_vs_actual.png) | ![Month over month spending](screenshots/chart_month_over_month_spending.png) |

## FP&A concepts demonstrated

- Budget vs actual variance analysis with root-cause driver, forward cash-flow
  impact, and a recommended corrective action per category.
- Rolling forecast scenarios (upside, base, downside) for expected cash flow,
  savings rate, and ending cash from a 3-month history.
- Separation of fixed obligations (rent, phone, gym, subscriptions, student loan)
  from discretionary recurring behavior.
- Recurring-charge detection with price-increase flags and projected next charge.
- Unusual-expense detection using a category-relative threshold (above 2x the
  category average and above a category minimum review floor).
- Net worth snapshot and a debt-payoff comparison (avalanche vs snowball style).
- Action-item prioritization with owner, due date, status, urgency, and estimated
  dollar impact.

## Key calculations

- Savings rate: `(Income - Total Expenses) / Income x 100`
- Budget variance: `Budget Amount - Actual Amount`
- Unusual expense: amount above `2x` the category 3-month average and above the
  category minimum review threshold
- Forecast scenarios: 30-day and 90-day cash-flow estimates from 3-month history

## Data quality and trustworthiness

The system is built to fail closed rather than report numbers it cannot defend:

- Fail-closed self-checks run before any report renders. They independently
  recompute the monthly totals a second way and refuse to continue unless the
  numbers reconcile to the source transactions.
- A schema contract verifies required columns, non-null values, and no duplicate
  transaction rows.
- An approved-category contract catches category drift before reports or
  commentary trust it.
- The personal-import path stamps every row with traceability fields
  (`source_file`, `source_row_number`, `import_batch_id`, optional
  `transaction_id`) and escapes spreadsheet-formula text so a malicious vendor
  name cannot execute when a CSV is opened in a spreadsheet app.

The self-check results are printed in the report itself (the Model Version Log on
the final page), so a reader can see the controls passed.

## Privacy and safety design

- Local-first by default: no cloud hosting, no external AI APIs, no bank-login
  integrations, no credential storage.
- Real personal data is never used. Private local folders (`data/personal/`,
  `data/processed/`, `outputs/personal/`, `config/personal_rules.*`) are
  Git-ignored, and a safety gate verifies this with Git itself before any future
  real-data workflow could run.
- Portfolio screenshots use only fictional Alex Rivera data.

## How to run and regenerate

```bash
cd Personal_Finance_CFO_Agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pytest                      # full test suite
python3 main.py                        # run the analysis pipeline
python3 scripts/generate_monthly_report.py   # regenerate the monthly CFO report
python3 scripts/generate_trend_report.py      # regenerate the 3-month trend summary
```

Generated PDFs and PNGs are intentionally not committed; they are regenerated on
demand by the scripts above. The screenshots in this summary live under
`docs/screenshots/` so the portfolio renders without running anything.

## Tech stack

Python, pandas (data and analytics), matplotlib (charts), reportlab (PDF), and
PyMuPDF (PDF rendering). Tested with pytest.

## Limitations

- Not investment, tax, accounting, or compliance advice.
- Does not connect to live accounts or real-time data.
- Forecasts use only a 3-month fictional history and are directional estimates.

## Status

Working, tested v1 (full suite passing). Demonstrates data quality control,
variance analysis, financial modeling, executive communication, and client-ready
PDF production. Next planned step is publishing as a standalone GitHub repository.
