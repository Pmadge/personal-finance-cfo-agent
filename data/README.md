# Data Folder

This folder holds fictional demo data and safe sample templates only.

Important rule: do not place real bank statements, credit card exports, account numbers, names, addresses, or any other real personal financial data in the Git-tracked sample files.

Current safe files:

- `alex_rivera_transactions.csv` - fictional Alex Rivera data raw demo input.
- `alex_rivera_transactions_categorized.csv` - regenerated fictional categorized demo output.
- `portfolio_demo_morgan_patel_household.csv` - richer fictional household input used to regenerate the README/portfolio screenshots.
- `sample/personal_transactions_template.csv` - fake personal-style CSV template for testing the local importer.

The local importer writes source identity fields into normalized outputs: `source_file`, `source_row_number`, `import_batch_id`, and optional `transaction_id`.

The local workflow audit writes run receipts to `data/processed/workflow_audit.md` and `data/processed/workflow_audit.json`. These receipts record row counts, overrides, self-check status, and output paths without making processed personal data public. Audit output paths are restricted to Git-ignored local output folders by default, and personal-mode source paths are reduced to project-relative paths or basenames to avoid leaking private local folder names.

Real local uploads should go under `data/personal/` when saved as source files, and processed/reviewed outputs should go under `data/processed/`. Those folders are Git-ignored except for `.gitkeep` placeholders. The Streamlit upload flow currently writes normalized uploads and category-review CSVs into `data/processed/`.
