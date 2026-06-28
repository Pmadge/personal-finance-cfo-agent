# Local-First Personal Use Roadmap

## Product direction

The long-term goal is a personal CFO product that Paul can run locally, either as a simple script or a small local app, so personal financial data stays private.

This means the default design should work without cloud accounts, hosted databases, external AI APIs, bank-login integrations, or automatic uploads.

## Privacy principles

1. **Local by default** - all processing happens on Paul's Mac unless he explicitly chooses otherwise.
2. **No credentials in the app** - do not store bank passwords, OAuth tokens, API keys, or brokerage credentials.
3. **Manual import first** - use exported CSV files before considering bank integrations.
4. **Fictional data until safety is ready** - keep using Alex Rivera sample data until the personal-data workflow is designed and reviewed.
5. **Clear data folders** - separate sample data, personal local input data, generated reports, and backups.
6. **No accidental sharing** - real personal data should be ignored by Git and never included in portfolio screenshots.
7. **User review before automation** - the app should show categorization and assumptions before final reports are trusted.

## Recommended architecture

```text
Personal_Finance_CFO_Agent/
  data/
    sample/                  # fictional Alex Rivera data safe for GitHub/portfolio
    personal/                # real local data, ignored by Git
    processed/               # categorized local outputs, ignored if personal
  modules/
    importers/               # CSV loading and normalization
    categorization_review/   # review/override workflow
    reports/                 # PDF and report builders
  outputs/
    sample/                  # generated demo reports safe to show
    personal/                # private generated reports, ignored by Git
  scripts/
    run_sample_demo.py
    import_personal_csv.py
    monthly_close.py
    review_categories.py
    generate_workflow_audit.py
    generate_personal_report.py
  docs/
    LOCAL_FIRST_PERSONAL_USE_ROADMAP.md
```

## Phase 1: Safe local demo product

Goal: keep improving the current fictional-data project without risking personal data.

- [x] Keep report source code out of `outputs/`.
- [x] Add repeatable dependency setup with `requirements.txt`.
- [x] Add tests that regenerate reports into temporary folders.
- [x] Add missing-category and incomplete-dataset guardrails.
- [x] Separate sample output paths from future personal output paths.
- [x] Add a clear privacy warning to the CLI and README.
- [x] Add backend data-contract checks, category-contract checks, and monthly math reconciliation self-checks.

Definition of done:

- Sample demo runs fully offline.
- Tests pass from a local virtual environment.
- No real data is required.
- README clearly says what is safe and not safe.

## Phase 2: Manual personal CSV import

Current status: **fake/sample fixtures only**. The importer shape exists, but real personal import mode is still disabled.

Future goal: let Paul use exported CSV files locally without connecting bank accounts, after the safety gate, audit hashing, duplicate checks, and report self-check gate are complete.

- [x] Create `data/personal/` and add it to `.gitignore`.
- [x] Create a CSV import template for personal transactions.
- [x] Build an importer that normalizes columns into the app schema:
  - `date`
  - `vendor`
  - `amount`
  - `raw_category`
- [x] Add a source transaction identity layer before real personal data:
  - `source_file`
  - `source_row_number`
  - `import_batch_id`
  - optional `transaction_id`
- [x] Add validation errors that explain what is wrong in plain English.
- [x] Add tests with fake personal-style CSV fixtures only, never real data.

Definition of done for the future real-data layer:

- Paul can place a manually exported CSV in a local private folder.
- The app validates it and either produces a clean normalized file or explains what needs fixing.
- Real CSV files are ignored by Git.

Current sample-only done criteria:

- Fake personal-style fixtures import through the same deterministic schema.
- Standalone import sample mode rejects non-`data/sample/` inputs.
- Personal import mode exits before processing until explicitly approved.

## Phase 3: Categorization review workflow

Goal: avoid blindly trusting the model's categories.

- [x] Generate a review file showing uncategorized or low-confidence transactions.
- [x] Preserve source identity fields in the review file so corrections trace back to the original import row.
- [x] Allow manual category overrides using a local CSV file.
- [x] Keep a local Git-ignored rules file for manual vendor/category corrections.
- [x] Add tests for category overrides and unknown vendors.
- [ ] Promote repeat vendor overrides into a reusable local rules flow.

Definition of done:

- Paul can review and correct categories before reports are finalized.
- The app remembers local vendor rules without exposing them publicly.

## Phase 4: Monthly close workflow

Current status: **safe sample monthly close only**. The real-data flow below is a future target, not an enabled workflow.

Future goal: make the app useful as a repeatable monthly personal finance routine.

Suggested flow:

1. Export transactions from bank/credit card portals manually.
2. Save CSVs into `data/personal/`.
3. Run local import and validation.
4. Review categories and overrides.
5. Generate a workflow audit artifact that records inputs, row counts, overrides, self-check status, and output paths.
6. Generate draft monthly CFO report.
7. Review assumptions and action items.
8. Save final report locally.

Potential script:

```bash
python3 scripts/monthly_close.py --sample
```

Definition of done for the current safe-script layer:

- One command can guide Paul through sample import, category review, override application, and workflow audit generation.
- The process is understandable without needing to inspect Python code.
- Intermediate workflow CSVs stay in `data/processed/`; private report outputs stay in `outputs/personal/`.
- Draft report generation is available through `python3 scripts/generate_personal_report.py` after the safe sample close has run.

## Phase 5: Local app option

Goal: create a small local interface only after the script workflow is trustworthy.

Good local app options:

- **Streamlit local app** - easiest dashboard-style interface, runs at `localhost`.
- **Tkinter desktop app** - fully local built-in Python UI, less polished but simple.
- **FastAPI local app** - useful if a browser interface is wanted, but more engineering overhead.

Recommended first app path:

1. Finish script workflow.
2. Add Streamlit only as a local wrapper around tested modules.
3. Do not add cloud hosting.
4. Do not add accounts or login until there is a real need.

## What stays demo-only for now

- Alex Rivera fictional sample reports.
- Portfolio screenshots.
- Public README examples.
- Any generated artifacts committed to Git.

## What must stay private later

- Paul's real transaction CSVs.
- Categorized personal transaction files.
- Vendor override rules based on Paul's real spending.
- Personal report PDFs.
- Any screenshots showing real vendors, accounts, balances, or spending.

## Next build task

Build the real-data safety gate before enabling personal mode:

- [x] Verify private local paths with Git itself, not `.gitignore` string matching.
- [x] Add a runnable safety check command: `python3 scripts/check_personal_mode_safety.py`.
- [x] Add an audit gate for future real personal reports: `mode=personal`, `needs_review_count=0`, `self_check_status=PASS`, correct privacy status, and output paths under `outputs/personal/`.
- [x] Keep this phase from importing or processing real financial data.
- [x] Review architecture/cleanup findings before expanding into real statement import.
- [x] Add standalone import guardrails so sample mode cannot process arbitrary or `data/personal/` inputs.
- [x] Add traversal/symlink regression tests for the standalone import guard.
- [x] Make audit path validators treat relative workflow paths as project-relative instead of current-working-directory-relative.
- [x] Record the source input file SHA-256 in workflow audit JSON and Markdown.
- [x] Add deterministic personal report pre-render self-checks before PDF/chart artifacts are written.
- [x] Add duplicate checks so repeated source transaction IDs, imported source rows, or exact final-statement rows fail before PDF/chart artifacts.
- [x] Build one fake bank-export importer profile using fake fixtures only.
- [ ] Decide the next sample-only importer/reporting extension after reviewing fake-bank profile results.

## Phase 6: Local AI coding-agent workflow

Goal: make Claude Code, Codex, and Hermes safer and more useful when working on this project.

- [x] Add project-local Graphify skills/instructions for Claude Code, Codex, and Hermes.
- [x] Add Karpathy-style coding-agent behavior rules to `AGENTS.md` and `CLAUDE.md`.
- [x] Run the first Graphify code-only pilot on `modules/` and generate `graphify-out/graph.json`.
- [x] Export the local call-flow HTML: `graphify-out/Personal_Finance_CFO_Agent-callflow.html`.
- [x] Keep `graphify-out/` ignored by Git until graph output privacy/reproducibility is reviewed.
- [ ] Decide whether Graphify outputs should be committed, regenerated on demand, or kept local-only.
- [ ] Decide whether future Graphify runs should include docs after an LLM backend is configured.

Keep real financial data in `data/personal/`, processed personal outputs in `data/processed/`, and private reports in `outputs/personal/`; all are Git-ignored.

Do not use Paul's real transaction files until the personal report adapter and draft report workflow are passing and reviewed.

## Future Git repo direction

Publishing this as a GitHub portfolio repo is a good eventual goal once the local product is cleaner. Before publishing:

- Keep only fictional/sample data in tracked files.
- Keep `data/personal/`, `data/processed/`, `outputs/personal/`, and personal rules ignored by Git.
- Add a clean project README with screenshots generated from fictional data only.
- Add setup, test, and report-generation commands that a reviewer can run from scratch.
- Decide whether generated sample PDFs/PNGs should be committed as portfolio evidence or regenerated on demand.
