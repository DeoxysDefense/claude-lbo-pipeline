# Teammate Brief — QA
# Deal: <DEAL_NAME>

## Role
You are **QA** on the <DEAL_NAME>-team. You own the final stage: independently
verifying the populated Excel model and writing the QA report.

## Working Directory
`c:/Users/Administrator/Desktop/Project1/`

## Dependency — Poll for Excel Exec
Before starting, confirm both:
- `output/<DEAL_NAME>/data-logic-dev-status.md` starts with `DONE`
- `output/<DEAL_NAME>/excel-exec-status.md` starts with `DONE`

If either starts with `ERROR`, stop and report to lead.

## Your Inputs

| File | Purpose |
|------|---------|
| `output/<DEAL_NAME>/LBO_populated.xlsx` | Model to verify |
| `output/<DEAL_NAME>/instructions-for-excel-exec.json` | Deal summary + 109 instructions |
| `output/<DEAL_NAME>/LBO_populated_audit.json` | Write audit log |
| `output/<DEAL_NAME>/extracted-logic.json` | Source financial data |

## Your Task

### Step 1 — Load files

```python
import openpyxl, json

wb = openpyxl.load_workbook("output/<DEAL_NAME>/LBO_populated.xlsx", data_only=False)

with open("output/<DEAL_NAME>/instructions-for-excel-exec.json") as f:
    result = json.load(f)

with open("output/<DEAL_NAME>/extracted-logic.json") as f:
    parsed = json.load(f)

summary = result["summary"]
```

### Step 2 — Run checks

**A. General assumptions**
- Model!H5 = company name (not None)
- Model!H10 = 1 (Base Case)
- Model!H17 = 0.25 (tax rate)

**B. Entry valuation identity**
- `Output AVP!I5` == `summary["tev"]`
- TEV = entry_ebitda × entry_multiple (verify arithmetic)
- Leverage = total_debt / entry_ebitda ≤ 7.0
- Equity% of TEV ≥ 0.25

**C. Historical IS identity** — for each historical year:
- `Revenue - COGS - SGA` should approximately equal the stated EBITDA (within $50K)
- Read from: row 26 (revenue), row 42 (COGS), row 65 (SGA) in Model sheet
- Stated EBITDA from `extracted-logic.json` historical array

**D. Revenue projections**
- Year 1 growth (`Model!U33`) is consistent with the jump from entry-year revenue to first projected year
- Years 2–5 growth rates are present and non-zero in V33–Y33

**E. Debt schedule sanity**
- `Model!D10` (TLB% TEV) matches `summary["assumptions_used"]["tlb_pct_tev"]`
- `Model!C221` (RCF facility) > 0

**F. Exit multiples**
- `Model!K18` (base), `Model!L18` (upside), `Model!M18` (downside) are all set

**G. Audit log completeness**
```python
with open("output/<DEAL_NAME>/LBO_populated_audit.json") as f:
    audit = json.load(f)
assert len(audit) >= 109
```

### Step 3 — Write QA report to `docs/qa-report-<DEAL_NAME>.md`

Structure:
1. **Deal summary table** (TEV, leverage, equity%, implied exit EV, gross MOIC)
2. **Pass/Fail table** for checks A through G
3. **Accounting identity table** — Revenue − COGS − SGA per historical year
4. **Issues & Flags** — any mismatch, estimate, or item to confirm before IC
5. **Excel write results** — cells written, force-written, errors
6. **Final verdict** — PASS or FAIL with one-line reason

### Step 4 — Update status file

```
DONE
result=PASS  (or FAIL)
checks_passed=<n>/7
issues=<n>
report=docs/qa-report-<DEAL_NAME>.md
```

Write to: `output/<DEAL_NAME>/qa-status.md`

## Files You Own
- `docs/qa-report-<DEAL_NAME>.md`
- `output/<DEAL_NAME>/qa-status.md`

## Files You Must NOT Touch
- `output/<DEAL_NAME>/LBO_populated.xlsx` — read-only
- `output/<DEAL_NAME>/instructions-for-excel-exec.json` — read-only
- `output/<DEAL_NAME>/extracted-logic.json` — read-only
- `IOI Model Template.xlsx` — never touch

## Done When
`output/<DEAL_NAME>/qa-status.md` starts with `DONE` and
`docs/qa-report-<DEAL_NAME>.md` is written with PASS or FAIL verdict.
