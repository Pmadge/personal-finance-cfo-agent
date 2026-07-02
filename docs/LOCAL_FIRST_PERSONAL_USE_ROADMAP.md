# Local-First Personal Use Roadmap

## Product direction

The long-term goal is a personal CFO product that Paul can run locally as a script workflow first, then as a small local app/interface. Personal financial data should stay on the Mac unless Paul explicitly chooses otherwise.

The default design should work without cloud accounts, hosted databases, external AI APIs, bank-login integrations, or automatic uploads.

## Privacy principles

1. **Local by default**: all processing happens locally unless explicitly approved.
2. **No credentials in the app**: no bank passwords, OAuth tokens, API keys, or brokerage credentials.
3. **Manual import first**: exported CSV files before any bank integration is even considered.
4. **Fictional committed assets**: repo data and screenshots stay fictional/sample-only; explicitly provided local uploads may be processed in Git-ignored folders.
5. **Clear private folders**: real inputs, processed data, local rules, and personal outputs stay in Git-ignored folders.
6. **No accidental sharing**: no portfolio screenshot or committed artifact may show real vendors, accounts, balances, or spending.
7. **User review before automation**: categories, assumptions, and report outputs should be reviewable before trusted.
8. **Deterministic engine owns the numbers**: AI may explain checked numbers later, but it must not invent them.

## Current architecture

```text
Personal_Finance_CFO_Agent/
  test_personas/                         # reusable fictional personas + full outputs
    starter_person/
    complex_household/
  data/
    sample/                               # safe templates and fake fixtures
    personal/                             # future real local inputs, Git-ignored
    processed/                            # reviewed/processed workflow outputs, Git-ignored
  config/
    personal_profile.example.json         # committed fictional template
    personal_profile.json                 # local private profile, Git-ignored
    personal_rules.csv                    # local category overrides, Git-ignored
  modules/
    importers/                            # fake/sample CSV import profiles
    reports/                              # PDF report builders
    *_self_checks / workflow audit logic   # deterministic trust gates
  outputs/
    personal/                             # local private or fake personal reports, Git-ignored
    stress_tests/                         # generated fictional stress outputs, Git-ignored
  scripts/
    setup_personal.py                     # one-command local profile setup
    monthly_close.py                      # safe sample monthly close
    generate_personal_report.py           # draft fake personal report
    stress_test_personas.py               # fictional population stress harness
  docs/
    PORTFOLIO_SUMMARY.md
    LOCAL_FIRST_PERSONAL_USE_ROADMAP.md
```

## Phase 1: Safe local demo product

Status: **complete**

- [x] Keep report source code out of `outputs/`.
- [x] Add repeatable dependency setup with `requirements.txt`.
- [x] Add tests that regenerate reports into temporary folders.
- [x] Add missing-category and incomplete-dataset guardrails.
- [x] Separate sample output paths from future personal output paths.
- [x] Add privacy warnings to the CLI and README.
- [x] Add backend data-contract checks, category-contract checks, and monthly math reconciliation self-checks.
- [x] Create a private GitHub repo.
- [x] Add GitHub Actions CI.
- [x] Keep generated PDFs/charts local or regenerated on demand.

## Phase 2: Manual personal CSV/Excel/PDF import foundation

Status: **local upload path active for approved manual files**

- [x] Create `data/personal/` and add it to `.gitignore`.
- [x] Create personal CSV templates using fake data only.
- [x] Build importer normalization into the internal schema:
  - `date`
  - `vendor`
  - `amount`
  - `raw_category`
- [x] Add source transaction identity:
  - `source_file`
  - `source_row_number`
  - `import_batch_id`
  - optional `transaction_id`
- [x] Add clear validation errors.
- [x] Add fake bank-export profile coverage.
- [x] Add tests with fake personal-style CSV fixtures only.
- [x] Add local Streamlit upload support for one CSV, one Excel workbook, one CoastHills Visa PDF, or multiple CoastHills Visa PDFs merged into one review file.
- [x] Reconcile the attached February-May 2026 PDF statement totals against parsed purchase rows.

Bank-login automation remains out of scope; manual local uploads are the approved path.

## Phase 3: Categorization review workflow

Status: **sample workflow complete**

- [x] Generate a review file showing suggested categories and low-confidence rows.
- [x] Preserve source identity fields in review output.
- [x] Allow manual category overrides using a local CSV file.
- [x] Keep local vendor/category rules Git-ignored.
- [x] Add tests for category overrides and unknown vendors.
- [x] Add duplicate checks for source IDs, source rows, and exact final-statement rows before report rendering.
- [x] Preserve transaction IDs so legitimate same-date/same-vendor/same-amount card charges are not blocked as duplicates.
- [x] Add merchant-rule bulk fill for common uploaded statement vendors.
- [ ] Promote repeat vendor overrides into a reusable local rules file if static merchant rules become too limited.

## Phase 4: Monthly close workflow

Status: **safe sample monthly close complete**

The current safe command is:

```bash
python3 scripts/monthly_close.py --sample
```

It normalizes fake personal-style transactions, generates category review files, creates or applies local override rules, and writes workflow audit receipts with source input SHA-256 hashes.

Current safeguards:

- [x] sample mode only accepts files under `data/sample/`
- [x] personal mode exits before processing real data
- [x] workflow audit paths are validated project-relative paths
- [x] self-check status defaults to `NOT_RUN` unless real checks ran
- [x] private paths are verified with Git itself
- [x] draft report generation runs deterministic self-checks before writing PDFs/charts
- [x] draft personal report writes under `outputs/personal/`

## Phase 5: CFO parity engine

Status: **v1 complete**

The project now contains seven CFO-style pillars:

1. Categorizer generalization
2. Goals tracker
3. Forecasting depth and cash runway
4. What-if scenarios
5. Risk register
6. Capital-event playbooks, including rent-vs-buy
7. Service wrapper and outcomes scorecard

These are wired into both:

- the fictional starter-person board pack
- the draft personal report path using a local profile

Current verification:

```text
236 local tests passing
GitHub Actions passing
100-persona stress harness available
value-invariant checks added to the stress harness
```

## Phase 6: Local profile and onboarding

Status: **v1 complete**

- [x] Add `config/personal_profile.example.json`.
- [x] Ignore `config/personal_profile.json`.
- [x] Load local profile when present, otherwise fallback to fictional sample profile.
- [x] Add `scripts/setup_personal.py` to create the local profile and verify private paths.
- [x] Add tests for the setup flow and profile loader.

This lets local assets, liabilities, goals, scenarios, home target, major purchase, and monthly debt payment be personalized without committing private values.

## Phase 7: Consolidation and public-release polish

Status: **complete except repo visibility**

The engine is now broad enough. The next highest-value work is consolidation and presentation polish, not more analytical sections.

Recommended tasks:

- [x] Refresh stale README and portfolio roadmap language after the 4 merged PRs.
- [x] Add a one-page Executive Dashboard to the board pack and draft personal report.
- [x] Regenerate portfolio screenshot for the new Executive Dashboard.
- [x] Final README visual review.
- [x] Run public-release hardening scan:
  - tests
  - GitHub Actions
  - secret scan
  - absolute local path scan
  - staged-file check
  - private/generated path check
- [x] Keep the GitHub repo private until the project is fully ready for public review.
- [x] Draft LinkedIn launch post.

## Phase 8: Optional local AI layer

Status: **planned, not implemented**

Goal: add a local-only explanatory layer that can generate CFO memos or Q&A from verified report artifacts.

Rules:

- disabled by default
- local endpoint only, such as llama.cpp or Ollama
- no cloud fallback
- deterministic engine remains source of truth
- AI sees compact checked outputs before raw transaction data
- AI outputs should cite which report artifacts they used

The first safe feature should be a local AI CFO memo from generated fake/sample report artifacts.

## Phase 9: Local app/interface

Status: **Streamlit local upload/report MVP active**

The app is a wrapper around tested modules and approved artifacts. It renders verified sample report JSON, sample category review CSV, and fictional stress-test summaries. It also supports a local Upload Transactions flow for explicitly selected files.

Current screens:

- Home Dashboard
- Upload Transactions with one CSV, one PDF, multi-PDF merge, category editing, merchant-rule bulk fill, and gated report generation
- Monthly Report
- Category Review
- Stress Test Explorer
- Local AI Memo placeholder, disabled by default
- Settings / Privacy

Deferred until the product direction justifies more architecture:

- React/FastAPI/Tauri
- Ask Local CFO
- Goal planner

## What stays demo-only for now

- starter-person fictional sample reports
- complex-household screenshots
- Public README examples
- Fake personal-style CSV fixtures
- Generated stress-test outputs

## What must stay private later

- real transaction CSVs
- categorized personal transaction files
- personal profile values
- vendor override rules based on real spending
- personal report PDFs
- screenshots showing real vendors, balances, accounts, or spending

## Next build task

Keep the repo private. Next, finish the remaining readiness pass: run the local app as an outside reviewer, capture any rough edges, and only revisit public visibility after that review is clean.
