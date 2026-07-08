# User Guide

This guide walks you through using the Personal Finance CFO Agent as your own
monthly CFO, from first install to reading your third monthly report. It is
written for someone who has never used a terminal much. Every step says what to
type, what you should see, and what to do if something goes wrong.

Everything runs on your own computer. Nothing is uploaded anywhere, there is no
bank login, and no cloud AI is used.

## 1. One-time setup (about 10 minutes)

Open the Terminal app and paste these commands one at a time:

```bash
git clone https://github.com/Pmadge/personal-finance-cfo-agent.git
cd personal-finance-cfo-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

What each step does:

1. `git clone` downloads the project folder.
2. `cd` moves into it.
3. `python3 -m venv .venv` creates a private Python sandbox so nothing touches
   the rest of your computer.
4. `source .venv/bin/activate` turns the sandbox on. Your prompt should now
   start with `(.venv)`.
5. `pip install` downloads the libraries the app needs.

**Checkpoint:** run `python3 -m pytest -q`. After a minute or two you should
see a line ending in `passed`. If you do, everything installed correctly.

Common mistake: opening a new Terminal window later and forgetting to run
`source .venv/bin/activate` again. If a command says a package is missing,
activate the sandbox first.

## 2. Start the app

```bash
streamlit run streamlit_app.py
```

Your browser opens a local page (usually http://localhost:8501). This page is
served from your own machine only. The sidebar on the left lists the screens.

**Checkpoint:** you should see the First Run Setup screen the first time,
because no local profile exists yet.

## 3. First Run Setup (your baseline, about 15 minutes)

Answer the plain-English questions with your real numbers: checking, savings,
investments, debts, monthly debt payment, your main goal, emergency fund
target, and (optionally) a home purchase target.

When you save, the app writes one local file: `config/personal_profile.json`.
That file is ignored by Git, which means it can never be uploaded or committed
by accident. The app checks this for you.

**Checkpoint:** after saving, the sidebar default becomes Home Dashboard.
You can edit your numbers any time by returning to First Run Setup.

## 4. Your monthly close (the loop you repeat each month)

Once a month, when your statements are available:

### 4a. Export statements from your bank

Download one month of transactions from your bank or card website as CSV or
Excel. Credit-union Visa statement PDFs are also supported, including several
PDFs merged at once. Brokerage activity exports (CSV/Excel) work too.

### 4b. Upload

Go to **Upload Transactions**, choose the file(s), and the app shows a preview
of the normalized rows. Nothing is saved yet at this point.

### 4c. Review categories

Every row gets a suggested category. Rows the app is unsure about are marked
`needs_review` and left blank on purpose: you must choose their category. Use
the merchant-rule bulk fill for repeat vendors (set a vendor's category once,
apply it to all matching rows), then edit any remaining `final_category` cells
directly in the grid. Click save when done.

Common mistake: leaving a `needs_review` row blank. The report generator will
refuse to run until every row has a final category. This is deliberate: the
report never guesses.

### 4d. Generate your report

Click **Generate CFO report from saved uploaded review**. The app runs the
deterministic engine with fail-closed math checks (schema, categories,
duplicates, and income minus expenses reconciliation). If every check passes,
your PDF report is written to `outputs/personal/` on your machine.

**Checkpoint:** the app prints the report path. Open the PDF and spot-check a
few numbers against your bank app: income, total expenses, and net worth.

## 5. Reading your report

The report is organized like a CFO board pack:

- **Executive dashboard**: one page with net cash flow, savings rate, runway,
  top risk, top goal, and the single next action.
- **Cash runway**: how many months your liquid cash covers if income stopped.
- **12-month projection**: where your cash is heading at current habits.
- **What-if scenarios**: job loss, a raise, a move, a big purchase.
- **Goal tracker**: progress and on-track status for each goal you set.
- **Risk register**: six personal risks rated Low, Medium, or High.
- **Capital events**: home purchase readiness, big-purchase check, rent vs buy.
- **Outcomes scorecard**: this month versus last month, improved or worsened.

Every number ties back to a transaction row or your profile. Nothing is
AI-generated.

## 6. Progress Memory (months 2 and 3)

Each generated report also appends a snapshot to a local history file. The
**Progress Memory** screen shows report-to-report changes: net cash flow,
savings rate, net worth, runway, debt, and risk count. After your second close
you will see deltas; after the third you will see the trend.

## 7. Trying it without real data

The **Example Reports** screen renders fully fictional sample households, so
you can explore every screen before uploading anything real.

## 8. Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| "Rows still marked needs_review" | Some rows have no final category | Go back to Category Review, fill every blank, save again |
| "Unsupported upload columns" | The file's columns were not recognized | Compare your file's headers to the supported formats in the README Input Format section |
| "Could not find a full MM/DD/YYYY (or MM/DD/YY) date in the PDF" | The statement PDF has no readable date with a year | Use the CSV export from your bank instead, and report the statement format as a bug |
| "Duplicate source transaction IDs" | The same bank transaction ID appears twice | You probably uploaded the same file or month twice; re-upload one clean month |
| "Unsafe personal output path" | Something tried to write outside the private folders | Use the default paths; this guard protects your data |
| A number looks wrong in the report | Possibly a categorization or parsing bug | Check the row's category in Category Review first; if the category is right and the number is still wrong, file a bug with the row (redact the vendor if you like) |
| `ModuleNotFoundError` when starting | The Python sandbox is not active | Run `source .venv/bin/activate` and try again |

## 9. Privacy rules the app enforces for you

- Your profile, uploads, review files, reports, and history live only in
  Git-ignored local folders (`config/`, `data/personal/`, `data/processed/`,
  `outputs/personal/`).
- A safety gate verifies those ignore rules with Git itself before personal
  reports are generated.
- Never move real statements into `data/sample/` or `test_personas/`; those
  folders are committed and public.

## 10. The rhythm

That is the whole product: a 15-minute setup once, then a 20-minute close each
month. Upload, review, generate, read, act on the one next action, repeat.
