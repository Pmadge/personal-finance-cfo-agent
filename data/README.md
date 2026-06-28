# Data Folder

This folder holds fictional Alex Rivera demo data and safe sample templates only.

Important rule: do not place real bank statements, credit card exports, account numbers, names, addresses, or any other real personal financial data in the Git-tracked sample files.

Current safe files:

- `alex_rivera_transactions.csv` - fictional raw demo input.
- `alex_rivera_transactions_categorized.csv` - regenerated fictional categorized demo output.
- `sample/personal_transactions_template.csv` - fake personal-style CSV template for testing the local importer.

The local importer writes source identity fields into normalized outputs: `source_file`, `source_row_number`, `import_batch_id`, and optional `transaction_id`.

The local workflow audit writes run receipts to `data/processed/workflow_audit.md` and `data/processed/workflow_audit.json`. These receipts record row counts, overrides, self-check status, and output paths without making processed personal data public. Audit output paths are restricted to Git-ignored local output folders by default, and personal-mode source paths are reduced to project-relative paths or basenames to avoid leaking private local folder names.

Future real personal files should go under `data/personal/` and processed outputs should go under `data/processed/`. Those folders are Git-ignored except for `.gitkeep` placeholders.
