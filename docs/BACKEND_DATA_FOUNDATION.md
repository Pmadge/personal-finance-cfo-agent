# Backend Data Foundation and Accuracy Controls

This project should treat the backend/data layer as the source of truth. Reports and any future AI layer should only use data that has passed local checks.

## Current backend layout

```text
Personal_Finance_CFO_Agent/
├── test_personas/
│   ├── starter_person/                           # simple fixture + full outputs
│   ├── complex_household/                        # richer fixture + full outputs
├── data/
│   ├── personal/                                 # Git-ignored real local inputs
│   ├── processed/                                # Git-ignored reviewed/processed upload outputs
│   └── sample/                                   # safe templates/fixtures
├── modules/
│   ├── validation.py                             # input validation and audit log
│   ├── self_checks.py                            # backend accuracy contracts
│   ├── categorizer.py                            # deterministic categorization pipeline
│   ├── analytics.py                              # monthly/budget/cash-flow math
│   ├── detectors.py                              # recurring and unusual transaction detection
│   ├── reports/                                  # PDF builders
│   ├── importers/                                # local CSV and Credit Union Visa PDF normalization
│   ├── ui/                                       # Streamlit trust/upload models
│   └── ...
├── outputs/
│   ├── personal/                                 # Git-ignored future real reports
│   └── sample/                                   # safe generated samples later
└── tests/                                        # regression, report, privacy, and self-check tests
```

## Core transaction contract

The categorized transaction table must include:

```text
date
vendor
amount
raw_category
assigned_category
classification_method
```

Current self-checks verify:

- required columns exist
- required columns have no nulls
- duplicate transaction rows are caught
- assigned categories stay inside the approved category list
- monthly income, expenses, net cash flow, and savings rate reconcile back to source transactions

## Current upload/report path

The Streamlit Upload Transactions screen now routes manual files through the same deterministic checks:

1. parse one CSV, one Credit Union Visa PDF, or multiple Credit Union Visa PDFs
2. normalize to the internal transaction schema
3. preview rows locally
4. build a category review CSV
5. optionally bulk-fill blanks with simple merchant keyword rules
6. require final approved categories before report generation
7. run personal report self-checks before writing PDF/charts under `outputs/personal/`

Real uploads are local-only and Git-ignored. Bank-login automation, cloud parsing, hosted databases, and cloud AI remain out of scope.

## Accuracy control philosophy

Use a layered approach:

1. **Input validation:** fail early on malformed CSVs.
2. **Data contract checks:** confirm the backend table shape is stable.
3. **Category-contract checks:** prevent AI or fallback logic from inventing new categories silently.
4. **Math reconciliation:** recompute key totals independently and compare them to reported values.
5. **Fail-closed gates:** report builders call self-checks before trusting data.
6. **Tests:** each new data behavior gets a regression test before implementation.

## AI safety rule

Any future AI commentary, categorization, or forecasting must consume checked data only. AI text should never become the source of truth for financial numbers. Numbers should come from deterministic calculations, then AI can explain them.

## Current verification command

```bash
.venv/bin/python -m py_compile main.py modules/*.py modules/reports/*.py scripts/*.py
.venv/bin/python -m pytest -q
.venv/bin/python main.py
.venv/bin/python scripts/generate_monthly_report.py
.venv/bin/python scripts/generate_trend_report.py
```

## Next backend/data improvements

- Build `modules/importers/` with fake personal-style CSV fixtures.
- Add a canonical internal schema object or typed record once the importer stabilizes.
- Add row-level error context for CSV cleanup.
- Add source-file hashes to the audit log so reports can prove which input file produced them.
- Add a generated audit artifact for every report run.
