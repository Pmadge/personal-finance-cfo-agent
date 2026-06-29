# Personal Finance CFO Agent

A local-first portfolio prototype that turns fictional transaction data into a family-office-style monthly CFO packet.

> **Fictional data only:** this project does not connect to bank accounts, does not use real personal financial data, and is not financial advice.

For a visual walkthrough with sample report screenshots, see the
[Portfolio Summary](docs/PORTFOLIO_SUMMARY.md).

## What This Project Does

The Personal Finance CFO Agent turns fictional transaction data into a family office-style monthly reporting packet. It analyzes cash flow, spending categories, budget variance, recurring vendors, fixed obligations, unusual expenses, forecasts, net worth, debt payoff options, stress scenarios, risk flags, goals, capital-event readiness, rent-vs-buy tradeoffs, and prioritized action items. This is not a budgeting app; it is a CFO/FP&A reporting system designed to explain what happened, why it matters, what comes next, and what action the fictional sample persona should take.

Current verification status:

```text
189 local tests passing
GitHub Actions passing
100-persona fictional stress harness available
Real personal data disabled until explicit safety approval
```

## What It Produces

- Monthly CFO Report PDF: `outputs/alex_rivera_monthly_cfo_report_2026_03.pdf`
- 3-Month Trend Summary PDF: `outputs/alex_rivera_3_month_trend_summary_2026_q1.pdf`
- Spending by Category donut chart: `outputs/spending_by_category.png`
- Monthly Savings Rate Trend chart: `outputs/monthly_savings_rate_trend.png`
- Budget vs. Actual chart: `outputs/budget_vs_actual.png`
- Month-over-Month Spending chart: `outputs/month_over_month_spending.png`

## How To Run It

Beginner-friendly setup with a local virtual environment:

```bash
git clone https://github.com/Pmadge/personal-finance-cfo-agent.git
cd personal-finance-cfo-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m py_compile main.py modules/*.py modules/reports/*.py modules/importers/*.py scripts/*.py
python3 -m pytest -q
python3 main.py
python3 scripts/generate_monthly_report.py
python3 scripts/generate_trend_report.py
python3 scripts/monthly_close.py --sample
python3 scripts/generate_personal_report.py
```

### Personalize the report (optional)

The personal report's pillar sections (cash runway, goals, scenarios, risk
register, home-purchase readiness) read a financial profile of assets,
liabilities, goals, what-if scenarios, and a home target. By default it uses a
built-in fictional sample. To set up your own local profile in one step:

```bash
python3 scripts/setup_personal.py
```

This creates a local `config/personal_profile.json` (from the example), confirms
your private files are Git-ignored, and prints the next commands. Edit it with
your numbers, then regenerate the report.

`config/personal_profile.json` is Git-ignored and stays local. If it is absent,
the report falls back to the fictional sample. Transaction data is still
sample/fictional until a real personal-data workflow is approved.

### Robustness stress test

To stress test the engine end to end across many fictional people with different
wealth levels, incomes, careers, life stages, goals, and spending habits, run:

```bash
python3 scripts/stress_test_personas.py
```

By default this generates 100 fictional personas and writes inspectable results
to `outputs/stress_tests/run_<timestamp>_100_personas/`. To reproduce the current
100-person run exactly, use:

```bash
python3 scripts/stress_test_personas.py --count 100 --seed 20260627 --output-dir outputs/stress_tests/run_100_personas_seed_20260627
```

Each run writes `summary.csv`, `summary.json`, a `README.md`, and one folder per
persona with `input_transactions.csv`, `categorized_transactions.csv`,
`profile.json`, `step_results.json`, `report_summary.md`, and detailed analysis
tables. The stress-test outputs are generated/local-only and ignored by Git.
Fictional data only.

The sample CSV is already included at:

```text
data/alex_rivera_transactions.csv
```

To use a different fictional dataset, replace that file with a CSV using the same schema below.

## Privacy-First Product Direction

Long term, this project should become a local-first personal CFO product that can run fully on Paul's Mac as either a script workflow or a small local app. The default design should not require cloud hosting, external AI APIs, hosted databases, or bank-login integrations.

Personal financial data should stay local. For now, the project should continue using fictional Alex Rivera data until a safe import/review/report workflow exists.

Important local-data rule: real transaction CSVs, processed personal files, local vendor rules, and personal reports belong only in Git-ignored local folders such as `data/personal/`, `data/processed/`, and `outputs/personal/`. Do not use real financial data in portfolio screenshots or committed sample artifacts.

Roadmap: `docs/LOCAL_FIRST_PERSONAL_USE_ROADMAP.md`
Backend/data foundation: `docs/BACKEND_DATA_FOUNDATION.md`

## Local AI Agent Workflow

This project now has project-scoped instructions for Claude Code, Codex, and Hermes:

```text
AGENTS.md
CLAUDE.md
.claude/skills/graphify/
.codex/skills/graphify/
.hermes/skills/graphify/
```

Those files add two workflow rules:

1. **Karpathy-style coding discipline:** think before coding, keep changes simple, make surgical edits, and verify with real commands.
2. **Graphify project map:** use `graphify-out/graph.json` to query the code graph before broad architecture searches.

This project keeps root `AGENTS.md` and `CLAUDE.md` in the repo so future AI coding sessions understand the project rules. Tool-specific local folders such as `.claude/`, `.codex/`, `.hermes/`, and `graphify-out/` are intentionally ignored because they can contain machine-specific hooks, caches, or generated graph files.

The first Graphify pilot was generated from the Python code in `modules/` only, so it avoids sample data, private data folders, processed CSVs, and private reports. The local graph output is ignored by Git unless you intentionally regenerate and review it for publication.

Useful local commands. If `graphify` is not found in a normal terminal, install it or add your local Python tools directory to `PATH` first:

```bash
graphify query "How does the personal workflow audit connect to the monthly close workflow?" --graph graphify-out/graph.json
graphify explain "build_personal_workflow_audit" --graph graphify-out/graph.json
graphify export callflow-html
```

Important: do not run Graphify on real personal financial data, credential files, bank exports, or private report outputs.

## Project Structure

```text
main.py                 # Runs the core analysis pipeline and prints CFO outputs
modules/                # Reusable analysis, forecasting, chart, and report logic
modules/importers/      # Local CSV import and normalization helpers
modules/reports/        # Source code for PDF report builders
data/                   # Fictional demo data plus safe sample templates
outputs/                # Generated PDFs, charts, and rendered review images
scripts/                # Beginner-friendly commands for generating reports/imports
requirements.txt        # Python packages needed for setup and testing
```

## Input Format

The input file must be a CSV with exactly these columns:

| Column | Expected Format | Example |
|---|---|---|
| `date` | `YYYY-MM-DD` | `2026-03-01` |
| `vendor` | Text merchant or income source | `Parkside Rent Portal` |
| `amount` | Number; income is positive, expenses are negative | `2400.00` or `-72.18` |
| `raw_category` | Text source category | `rent`, `dining`, `subscription` |

## Personal CSV Import Template

A fake personal-style import template is included at:

```text
data/sample/personal_transactions_template.csv
```

It uses these columns:

| Column | Meaning |
|---|---|
| `posted_date` | Bank/export posted date in `YYYY-MM-DD` format |
| `description` | Merchant, income source, or transaction description |
| `amount` | Positive for income, negative for expenses |
| `source_category` | Original category from the export or manual label |
| `source_account` | Optional account label, kept for review but not used in the internal schema yet |
| `notes` | Optional review notes |
| `transaction_id` | Optional bank/export transaction ID for traceability |

Run the local safety gate before any future real-data work:

```bash
python3 scripts/check_personal_mode_safety.py
```

This command verifies with Git itself that private local paths such as `data/personal/`, `data/processed/`, `outputs/personal/`, and `config/personal_rules.csv` are ignored. It does not enable real-data import yet.

Run the full safe fake personal workflow with one command:

```bash
python3 scripts/monthly_close.py --sample
```

That command normalizes fake personal-style transactions, generates the category review, ensures the local Git-ignored override template exists, applies overrides, and writes the workflow audit receipt with the source input file SHA-256 hash. While personal mode is disabled, `--sample` only accepts input files under `data/sample/`; intermediate workflow CSVs stay under `data/processed/`; future private report outputs are listed only under `outputs/personal/`. After reviewing the audit, run `python3 scripts/generate_personal_report.py` to create the draft fake personal report at `outputs/personal/personal_cfo_report_draft.pdf`. The report script runs deterministic pre-render self-checks before writing any PDF or chart artifacts, including duplicate checks for source transaction IDs, imported source rows, and exact final-statement rows. The draft report includes a visual CFO snapshot, spending-by-category chart, and cash-flow waterfall chart under `outputs/personal/charts/`. The report script only accepts the default reviewed sample workflow file until personal mode is explicitly approved.

You can also run each step manually:

```bash
python3 scripts/import_personal_csv.py
python3 scripts/import_personal_csv.py --profile fake-bank --output data/processed/fake_bank_profile_normalized.csv
python3 scripts/generate_category_review.py
python3 scripts/apply_category_overrides.py --create-template
python3 scripts/apply_category_overrides.py
python3 scripts/generate_workflow_audit.py
python3 scripts/generate_personal_report.py
```

The one-command workflow runs the safe fake personal close from import through audit. The manual commands do the same work step by step: normalize fake personal-style transactions, optionally normalize the fake bank-export profile fixture, generate a category review CSV that preserves source identity fields and marks low-confidence rows for manual review, ensure a local Git-ignored override template exists at `config/personal_rules.csv`, apply corrections into `data/processed/category_review_applied.csv`, write local workflow receipts to `data/processed/workflow_audit.md` and `data/processed/workflow_audit.json`, and generate a draft fake personal report PDF under `outputs/personal/`. By default, the audit uses `self_check_status=NOT_RUN`; only pass `--self-check-status PASS` after a real self-check has run.

The normalized output includes source identity columns so each row can be traced back to the import file:

| Column | Meaning |
|---|---|
| `source_file` | Source file basename that produced the normalized row. The importer intentionally stores only the file name, not the full local path. |
| `source_row_number` | Original CSV row number, counting the header as row 1 |
| `import_batch_id` | Short deterministic ID based on the source file contents |
| `transaction_id` | Optional source transaction ID when the export provides one |

Do not put real transaction files into the project until the personal-data workflow is reviewed.

## Sample Persona

Alex Rivera is a fictional young professional with bi-weekly paycheck income, rent, groceries, dining, transportation, subscriptions, student loan payments, and occasional unusual charges. Fictional data is used so the project can demonstrate financial reporting logic without exposing real personal bank, credit card, or identity information. No real personal financial data should be added to this project.

## Key Calculations

- Savings rate: `(Income - Total Expenses) / Income x 100`
- Budget variance: `Budget Amount - Actual Amount`
- Unusual expense threshold: a transaction above `2x` category average and above the category minimum review threshold
- Fixed obligations: recurring rent, phone, gym, streaming subscriptions, and student loan payments only
- Forecast scenarios: 30-day and 90-day upside/base/downside cash-flow estimates from 3-month history

## FP&A Concepts Demonstrated

- Budget vs. actual variance analysis with root cause, forward impact, and recommended action.
- Rolling forecast scenarios for expected cash flow, savings rate, and ending cash.
- Separation of fixed obligations from discretionary recurring behavior.
- Action-item prioritization with owner, due date, status, urgency, and estimated dollar impact.
- Audit trail checks for row count, month coverage, schema validation, and fictional data labeling.

## Model Assumptions

- Report month is March 2026.
- The source dataset covers January-March 2026.
- Alex's monthly budget is fixed for this demo.
- Forecasts use the available 3-month history and are directional estimates, not financial advice.
- Net worth uses fictional sample balances: checking, savings, investments, student loan, car loan, and credit card.

## Limitations

- This project does not provide investment advice.
- This project does not calculate taxes.
- This project does not connect to live bank accounts, brokerage accounts, or real-time financial data.
- This project does not replace a regulated financial planning, accounting, or compliance system.
- The forecast is based on only 3 months of fictional history, so it should be read as a portfolio modeling example.

## Portfolio Context

This project demonstrates how raw transaction data can be transformed into a family office-style reporting packet with categorized cash flow, risk flags, charts, narrative commentary, forecast scenarios, and specific action items. It shows practical wealth management and FP&A reporting skills: data quality control, variance analysis, financial modeling, executive communication, and client-ready PDF production.
