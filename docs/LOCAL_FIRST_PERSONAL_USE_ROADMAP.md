# Local-First Personal Use Roadmap

## Product direction

The long-term goal is a personal CFO product that Paul can run locally as a script workflow first, then as a small local app/interface. Personal financial data should stay on the Mac unless Paul explicitly chooses otherwise.

The default design should work without cloud accounts, hosted databases, external AI APIs, bank-login integrations, or automatic uploads.

## Privacy principles

1. **Local by default**: all processing happens locally unless explicitly approved.
2. **No credentials in the app**: no bank passwords, OAuth tokens, API keys, or brokerage credentials.
3. **Manual import first**: exported CSV files before any bank integration is even considered.
4. **Fictional data until safety is ready**: current repo data and screenshots stay fictional/sample-only.
5. **Clear private folders**: real inputs, processed data, local rules, and personal outputs stay in Git-ignored folders.
6. **No accidental sharing**: no portfolio screenshot or committed artifact may show real vendors, accounts, balances, or spending.
7. **User review before automation**: categories, assumptions, and report outputs should be reviewable before trusted.
8. **Deterministic engine owns the numbers**: AI may explain checked numbers later, but it must not invent them.

## Current architecture

```text
Personal_Finance_CFO_Agent/
  data/
    alex_rivera_transactions.csv          # fictional demo input
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

## Phase 2: Manual personal CSV import foundation

Status: **sample/fake fixtures complete, real personal import still disabled**

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

Real personal import remains disabled until Paul explicitly approves a real-data safety gate.

## Phase 3: Categorization review workflow

Status: **sample workflow complete**

- [x] Generate a review file showing suggested categories and low-confidence rows.
- [x] Preserve source identity fields in review output.
- [x] Allow manual category overrides using a local CSV file.
- [x] Keep local vendor/category rules Git-ignored.
- [x] Add tests for category overrides and unknown vendors.
- [x] Add duplicate checks for source IDs, source rows, and exact final-statement rows before report rendering.
- [ ] Promote repeat vendor overrides into a reusable local rules flow.

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

- the fictional Alex Rivera board pack
- the draft personal report path using a local profile

Current verification:

```text
193 local tests passing
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

Status: **current recommended phase**

The engine is now broad enough. The next highest-value work is consolidation and presentation polish, not more analytical sections.

Recommended tasks:

- [x] Refresh stale README and portfolio roadmap language after the 4 merged PRs.
- [x] Add a one-page Executive Dashboard to the board pack and draft personal report.
- [x] Regenerate portfolio screenshot for the new Executive Dashboard.
- [ ] Final README visual review.
- [ ] Run public-release hardening scan:
  - tests
  - GitHub Actions
  - secret scan
  - absolute local path scan
  - staged-file check
  - private/generated path check
- [ ] Decide whether to make the GitHub repo public.
- [ ] Draft LinkedIn launch post.

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

Status: **planned, not implemented**

Recommended path:

1. Use Claude Design or sketch to create 2 to 3 UI concepts.
2. Pick the strongest product direction.
3. Build a Streamlit local prototype first.
4. Use the app as a wrapper around tested modules, not a replacement for the engine.
5. Later consider React/FastAPI/Tauri if the product direction justifies the extra architecture.

Target screens:

- Dashboard
- Reports
- Local AI memo
- Settings and privacy
- Category review
- Stress-test explorer
- Ask Local CFO later
- Goal planner later

## What stays demo-only for now

- Alex Rivera fictional sample reports
- Portfolio screenshots
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

Finish the consolidation/public-release polish pass:

1. Visually review the new Executive Dashboard output.
2. Refresh screenshots if the page looks good.
3. Run final release hardening.
4. Decide whether to publish the private repo publicly.
