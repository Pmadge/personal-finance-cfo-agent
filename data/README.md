# Data Folder

This folder holds local workflow folders and safe sample templates.

Current tracked sample/persona fixtures live in [`../test_personas/`](../test_personas/):

- `starter_person/transactions.csv` - simple fictional starter-person input.
- `starter_person/transactions_categorized.csv` - regenerated categorized starter-person output.
- `complex_household/transactions.csv` - richer fictional household input used for the README/portfolio screenshots.
- each persona's `outputs/` folder - full local run artifacts for that persona.

`sample/personal_transactions_template.csv` remains here as a fake personal-style CSV template for testing the local importer.

The local importer writes source identity fields into normalized outputs: `source_file`, `source_row_number`, `import_batch_id`, and optional `transaction_id`.

The local workflow audit writes run receipts to `data/processed/workflow_audit.md` and `data/processed/workflow_audit.json`. These receipts record row counts, overrides, self-check status, and output paths without making processed personal data public. Audit output paths are restricted to Git-ignored local output folders by default, and personal-mode source paths are reduced to project-relative paths or basenames to avoid leaking private local folder names.

Real local uploads should go under `data/personal/` when saved as source files, and processed/reviewed outputs should go under `data/processed/`. Those folders are Git-ignored except for `.gitkeep` placeholders. The Streamlit upload flow currently writes normalized uploads and category-review CSVs into `data/processed/`.
