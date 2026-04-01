"""
run_lbo_pipeline.py
-------------------
Runs the full LBO pipeline:
  1. Load extracted-logic.json (already produced from management financials)
  2. Run LBOEngine to generate cell-level instructions
  3. Execute instructions into Excel via AdvancedExcel
  4. Save output and audit log
"""

import json
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lbo_engine import LBOEngine, LBOAssumptions, LBOEngineError
from advanced_excel import AdvancedExcel, ExcelToolError

# ── Step 1: Load parsed financial data ──────────────────────────────────────

with open("output/extracted-logic.json") as f:
    parsed = json.load(f)

print(f"[1/4] Loaded extracted-logic.json")
print(f"      Company : {parsed['metadata']['company_name']}")
print(f"      Units   : {parsed['metadata']['units']}")
print(f"      Hist yrs: {[p['year'] for p in parsed['historical']]}")
print(f"      Proj yrs: {[p['year'] for p in parsed['projected']]}")
print(f"      Warnings: {len(parsed['warnings'])}")
for w in parsed['warnings']:
    print(f"        ⚠  {w}")

# ── Step 2: Set LBO assumptions ──────────────────────────────────────────────

assumptions = LBOAssumptions(
    entry_multiple        = 5.0,       # 5× Adj EBITDA per deal terms
    tlb_pct_tev           = 0.45,      # TLB = 45% of TEV
    rcf_availability      = 5.0,       # $5M RCF facility (sized to company scale)
    rcf_draw_at_close     = 0.0,       # RCF undrawn at close
    seller_note_pct_tev   = 0.0,       # no seller note
    rolled_equity         = 0.0,       # no management rollover
    cash_floor            = 1.5,       # $1.5M minimum cash (sized to company)
    dividend_flag         = 1,         # pay dividends when FCF positive

    # Revenue / margin
    projection_years      = 5,         # 5-year model (2026-2030)
    rev_cagr              = 0.2397,    # 24% CAGR derived from management projections
    ebitda_margin_expansion_bps = 0,   # explicit projections provided — no expansion needed
    gross_margin_target   = 0.60,      # 60% gross margin → COGS 40%; leaves room for SGA at ~16%

    # Capex (service company — light capex)
    maint_capex_pct_rev   = 0.01,
    growth_capex_pct_rev  = 0.005,

    # Tax
    tax_rate              = 0.25,
    depreciable_life      = 5,

    # Debt pricing
    tlb_spread            = 0.055,     # SOFR + 5.5%
    tlb_amort_years       = 7,
    tlb_disc_paydown      = 1,         # sweep excess cash to TLB
    tlb_max_paydown       = 10.0,

    # Exit
    exit_multiple         = 5.0,       # base = entry
    exit_multiple_upside  = 6.0,
    exit_multiple_downside= 4.0,

    currency_units        = "millions",
    scenario              = 1,         # Base Case
)

print(f"\n[2/4] Running LBO engine (entry multiple: {assumptions.entry_multiple}×)")

# ── Step 3: Generate instructions ────────────────────────────────────────────

try:
    engine = LBOEngine(parsed, assumptions)
    result = engine.generate_instructions()
except LBOEngineError as e:
    print(f"\n❌ HARD STOP: {e}")
    sys.exit(1)

summary = result["summary"]
print(f"\n      Deal Summary:")
print(f"        Entry EBITDA : ${summary['entry_ebitda']:.2f}M")
print(f"        Entry Revenue: ${summary['entry_revenue']:.2f}M" if summary['entry_revenue'] else "        Entry Revenue: N/A")
print(f"        TEV          : ${summary['tev']:.2f}M")
print(f"        Total Debt   : ${summary['total_debt']:.2f}M")
print(f"        Equity       : ${summary['equity']:.2f}M ({summary['equity_pct_tev']:.1%} of TEV)")
print(f"        Leverage     : {summary['leverage_at_entry']:.1f}x")
print(f"        Exit Multiple: {summary['exit_multiple']}×")
print(f"        Y5 EBITDA    : ${summary['proj_ebitda_y5']:.2f}M" if summary['proj_ebitda_y5'] else "        Y5 EBITDA    : N/A")
print(f"        Implied EV   : ${summary['implied_exit_ev']:.2f}M" if summary['implied_exit_ev'] else "        Implied EV   : N/A")
print(f"        Instructions : {summary['instruction_count']}")

if result["violations"]:
    print(f"\n      ⚠  Violations ({len(result['violations'])}):")
    for v in result["violations"]:
        print(f"        {v}")

if result["warnings"]:
    print(f"\n      Engine warnings ({len(result['warnings'])}):")
    for w in result["warnings"]:
        print(f"        {w}")

# Save instructions to file for audit
with open("output/instructions-for-excel-exec.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
print(f"\n      Saved instructions to output/instructions-for-excel-exec.json")

# ── Step 4: Execute into Excel ───────────────────────────────────────────────

print(f"\n[3/4] Writing to Excel...")

tool = AdvancedExcel(
    template_path = "IOI Model Template.xlsx",
    output_path   = "output/LBO_populated.xlsx",
    agent_id      = "pipeline_runner",
)

write_results = tool.batch_write(result["instructions"])

# Tally first-pass results
ok      = [r for r in write_results if r["status"] == "ok"]
skipped = [r for r in write_results if r["status"] == "skipped"]
errors  = [r for r in write_results if r["status"] == "error"]

print(f"      Pass 1 — Written: {len(ok)}  Skipped: {len(skipped)}  Errors: {len(errors)}")

# Force-write any formula cells that need explicit per-year values
if errors:
    force_ok = 0
    for e in errors:
        sheet = e.get("sheet")
        cell  = e.get("cell")
        # Find matching instruction
        for instr in result["instructions"]:
            if instr["sheet"] == sheet and instr["cell"] == cell:
                tool.write_cell(sheet, cell, instr["value"], force=True)
                force_ok += 1
                break
    print(f"      Pass 2 — Force-wrote {force_ok} formula cells")

tool.save()
tool.save_audit_log()
print(f"\n[4/4] Saved output/LBO_populated.xlsx + audit log")

# Update status for QA
with open("output/data-logic-dev-status.md", "w") as f:
    f.write(f"""DONE: Pipeline complete

## Deal Summary
- Entry EBITDA  : ${summary['entry_ebitda']:.3f}M
- Entry Revenue : ${summary['entry_revenue']:.2f}M
- TEV           : ${summary['tev']:.2f}M  ({assumptions.entry_multiple}× EBITDA)
- TLB           : ${summary['total_debt']:.2f}M  ({assumptions.tlb_pct_tev:.0%} of TEV)
- Equity        : ${summary['equity']:.2f}M  ({summary['equity_pct_tev']:.1%} of TEV)
- Leverage      : {summary['leverage_at_entry']:.1f}x
- Exit multiple : {summary['exit_multiple']}× base / {assumptions.exit_multiple_upside}× upside / {assumptions.exit_multiple_downside}× downside
- Y5 EBITDA     : ${summary['proj_ebitda_y5']:.2f}M
- Implied EV    : ${summary['implied_exit_ev']:.2f}M

## Output Files
- output/LBO_populated.xlsx
- output/instructions-for-excel-exec.json
- output/LBO_populated_audit.json

## Warnings
{'  '.join(['- ' + w for w in result['warnings']]) if result['warnings'] else 'None'}

## Violations
{'  '.join(['- ' + v for v in result['violations']]) if result['violations'] else 'None'}

## Excel Write Results
- OK      : {len(ok)}
- Skipped : {len(skipped)}
- Errors  : {len(errors)}
""")

print(f"\n✅ Pipeline complete. Output: output/LBO_populated.xlsx")
