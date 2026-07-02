# Modules Folder

This folder contains the reusable Python engine for the Personal Finance CFO Agent.

Key areas:

- `importers/` normalizes local CSV/Excel uploads and supported CoastHills Visa PDF statements.
- `ui/` builds Streamlit trust/upload models without becoming a separate calculation layer.
- `reports/` builds PDFs and charts from checked data.
- `self_checks.py` fails closed before reports trust malformed, duplicate, or unreviewed data.
- analytics, forecasting, risks, goals, scenarios, and detectors own the deterministic CFO math.

No module should call bank logins, cloud AI, or hosted databases by default.
