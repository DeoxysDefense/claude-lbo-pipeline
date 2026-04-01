# Teammate Brief — Data & Logic Dev
# Deal: <DEAL_NAME>

## Role
You are the **Data & Logic Dev** on the <DEAL_NAME>-team. You own the first
two stages of the LBO pipeline: (1) validate the parsed financial JSON for
this deal, and (2) run the LBO engine to produce cell-level Excel instructions.

## Working Directory
`c:/Users/Administrator/Desktop/Project1/`

## Your Input
The parsed financial data for this deal is at:

    output/<DEAL_NAME>/extracted-logic.json

## Your Task

### Step 1 — Validate the input file
Read `output/<DEAL_NAME>/extracted-logic.json`. Confirm:
- At least 2 historical years present
- At least 3 projected years present
- Entry year EBITDA > 0
- `metadata.units` == "millions"

If any check fails, write `ERROR: <reason>` to
`output/<DEAL_NAME>/data-logic-dev-status.md` and stop.

### Step 2 — Run LBOEngine

```python
import json, sys
sys.path.insert(0, ".")
from lbo_engine import LBOEngine, LBOAssumptions, LBOEngineError

with open("output/<DEAL_NAME>/extracted-logic.json") as f:
    parsed = json.load(f)

assumptions = LBOAssumptions(
    entry_multiple              = <ENTRY_MULTIPLE>,
    tlb_pct_tev                 = <TLB_PCT>,
    rcf_availability            = 5.0,
    rcf_draw_at_close           = 0.0,
    seller_note_pct_tev         = 0.0,
    rolled_equity               = 0.0,
    cash_floor                  = 1.5,
    dividend_flag               = 1,
    projection_years            = 5,
    gross_margin_target         = 0.60,
    ebitda_margin_expansion_bps = 0,
    maint_capex_pct_rev         = 0.01,
    growth_capex_pct_rev        = 0.005,
    tax_rate                    = 0.25,
    depreciable_life            = 5,
    tlb_spread                  = 0.055,
    tlb_amort_years             = 7,
    tlb_disc_paydown            = 1,
    tlb_max_paydown             = 10.0,
    exit_multiple               = <ENTRY_MULTIPLE>,
    exit_multiple_upside        = <ENTRY_MULTIPLE_PLUS_ONE>,
    exit_multiple_downside      = <ENTRY_MULTIPLE_MINUS_ONE>,
    currency_units              = "millions",
    scenario                    = 1,
)

try:
    engine = LBOEngine(parsed, assumptions)
    result = engine.generate_instructions()
except LBOEngineError as e:
    with open("output/<DEAL_NAME>/data-logic-dev-status.md", "w") as f:
        f.write(f"ERROR: {e}")
    raise SystemExit(1)
```

### Step 3 — Validate result
Before writing outputs:
- `result["violations"]` must be empty
- `len(result["instructions"])` must be 109
- `result["summary"]["leverage_at_entry"]` must be ≤ 7.0
- `result["summary"]["equity_pct_tev"]` must be ≥ 0.25

If violations exist, still write the instructions file but include the
violations in the status file.

### Step 4 — Write outputs

```python
with open("output/<DEAL_NAME>/instructions-for-excel-exec.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
```

### Step 5 — Update status file

```
DONE
tev=<value>
leverage=<value>
equity_pct=<value>
instruction_count=109
violations=<NONE or list>
warnings_count=<n>
```

Write to: `output/<DEAL_NAME>/data-logic-dev-status.md`

## Files You Own
- `output/<DEAL_NAME>/instructions-for-excel-exec.json`
- `output/<DEAL_NAME>/data-logic-dev-status.md`

## Files You Must NOT Touch
- `IOI Model Template.xlsx`
- `output/<DEAL_NAME>/LBO_populated.xlsx`
- `docs/qa-report-<DEAL_NAME>.md`

## Done When
`output/<DEAL_NAME>/data-logic-dev-status.md` starts with `DONE`.
