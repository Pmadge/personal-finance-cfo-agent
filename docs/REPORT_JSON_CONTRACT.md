# Report JSON Contract

The Personal Finance CFO Agent UI layer (Streamlit now, possibly React/Tauri
later) binds to a single stable JSON object produced by the deterministic Python
engine. The UI never recomputes financial numbers; it only renders verified
results.

- Module: `modules/reports/report_json.py`
- Generator script: `scripts/generate_report_json.py`
- Schema version: `1.0.0` (`REPORT_JSON_SCHEMA_VERSION`)

## Design rules

1. The engine calculates; the JSON only reports verified results.
2. No AI text is produced here. This contract is engine-verified data only.
3. No local filesystem paths are exposed. Source artifacts are referenced by
   basename only (privacy-first).
4. Every value is a native JSON type (no numpy/pandas scalars).
5. `schema_version` lets the UI guard against drift.

## How to generate

```bash
python3 scripts/generate_report_json.py
```

Outputs (Git-ignored, regenerate on demand):

```text
test_personas/starter_person/outputs/report.json      # simple starter-person report
test_personas/complex_household/outputs/report.json    # richer household report
```

## Top-level shape

```jsonc
{
  "schema_version": "1.0.0",
  "generated_at": "<ISO-8601 UTC>",
  "engine": {
    "model_version": "CFO Agent v1.1",
    "deterministic": true,
    "ai_generated": false,
    "note": "All numbers are calculated by the deterministic Python engine. No AI wrote these values."
  },
  "persona":  { "name": "...", "fictional_notice": "...", "sample_data_only": true },
  "period":   { "month": "2026-03", "label": "March 2026" },
  "privacy":  {
    "mode": "sample", "real_data_enabled": false, "local_only": true,
    "bank_login": false, "cloud_sync": false, "cloud_ai": false,
    "local_ai_enabled": false
  },
  "self_check": { "checks_passed": 11, "checks_total": 11, "all_passed": true },
  "headline": { /* the <10-second Home Dashboard read */ },
  "sections": { /* the full Monthly Report Reader data */ },
  "sources":  { "artifacts": ["report.json", "monthly_cfo_report.pdf"], "note": "..." }
}
```

## `headline` (Home Dashboard, 10-second read)

| Field | Type | Meaning |
|---|---|---|
| `verdict` | string | Engine-derived: `On track`, `On track, with risks to watch`, or `Attention needed`. Not AI. |
| `net_cash_flow` | number | Monthly net cash flow (USD). |
| `savings_rate` | number | Savings rate (percent). |
| `emergency_runway_months` | number\|null | Months of runway. |
| `runway_status` | string | Engine runway assessment label. |
| `net_worth` | number | Net worth (USD). |
| `risk_counts` | object | `{ high, medium, low }` integer counts. |
| `top_risk` | object\|null | Highest-severity risk row. |
| `top_goal` | object\|null | First goal row. |
| `next_action` | object\|null | Top-ranked action item. |
| `rent_vs_buy` | object | `{ recommendation, cheaper, horizon_years }`. |

## `sections` (Monthly Report Reader)

Each key maps to a UI section. Arrays are lists of record objects whose keys are
the engine's column names (kept verbatim so they always match the PDF).

| Section key | Type | Source |
|---|---|---|
| `summary` | object | income / expenses / net / savings rate |
| `cash_flow` | object | inflow / outflow / net / savings rate |
| `runway` | object | full cash-runway metrics |
| `projection` | array | 12-month cash projection rows |
| `budget_vs_actual` | array | budget variance rows |
| `cumulative_budget` | array | 3-month cumulative budget rows |
| `recurring_vendors` | array | recurring vendor rows |
| `unusual_expenses` | array | unusual expense flags |
| `upcoming_obligations` | array | upcoming obligations |
| `net_worth` | object | assets / liabilities / net worth / ratio |
| `debt_payoff` | array | avalanche vs snowball comparison |
| `goals` | array | goal tracker rows |
| `risk_register` | array | risk rows |
| `risk_overall` | string | overall risk label |
| `home_purchase_readiness` | object | home-purchase readiness metrics |
| `major_purchase` | object | major-purchase affordability |
| `rent_vs_buy` | object | rent-vs-buy 5-year comparison |
| `scorecard` | array | this-month vs last-month outcomes |
| `action_items` | array | prioritized action items |
| `forecast` | array | scenario forecast rows |
| `self_checks` | array | audit-log rows (`Check`, `Status`, `Detail`) |

## Stability guarantees

- Record keys mirror the engine's DataFrame column names. If those change, bump
  `schema_version` and update this doc.
- `self_check` excludes `INFO` audit rows (input file, row count, months
  covered); it counts only real `PASS`/`FAIL` checks.
- Both the default and portfolio-demo personas serialize cleanly with zero local
  path leakage and pass `json.loads` round-trip.
