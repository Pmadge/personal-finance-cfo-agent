# Tests Folder

This folder holds regression and trust-boundary tests for the CFO Agent.

The tests cover:

- fictional sample reports and charts
- local CSV/Excel importer behavior
- brokerage activity CSV/Excel importer behavior
- CoastHills Visa PDF parsing and multi-PDF merge
- category review editing and merchant-rule bulk fill
- gated personal report generation after final categories are approved
- privacy/path checks for Git-ignored personal outputs
- Streamlit model behavior and app smoke checks

Tests use committed fictional fixtures plus explicitly provided local PDF statements when testing the manual local-upload path. No bank login or cloud service is required.
