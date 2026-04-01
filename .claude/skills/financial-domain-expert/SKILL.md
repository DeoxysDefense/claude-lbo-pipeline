---
name: financial-domain-expert
description: Use when an AI agent needs to convert standardized parsed financial JSON into LBO Excel Execution Instructions. Applies entry valuation, Sources & Uses, income statement forecasting, debt schedule mechanics, and returns analysis. The brain between data parsing and Excel population.
disable-model-invocation: true
---

## What This Skill Does

The "Brain" of the LBO multi-agent system. Ingests standardized JSON from
`data_parser.parse_document()`, applies all LBO financial logic and accounting
rules, and outputs a list of cell-level **Execution Instructions** that
`advanced_excel.batch_write()` executes blindly.

**Data flow:**
```
data_parser → [parsed JSON] → LBOEngine → [instructions] → AdvancedExcel
```

## Setup

```python
from data_parser import parse_document
from lbo_engine import LBOEngine, LBOAssumptions, LBOEngineError

parsed = parse_document("CIM_AcmeCorp.pdf", agent_id="parser_agent")

assumptions = LBOAssumptions(
    entry_multiple=8.5,
    tlb_pct_tev=0.50,
    exit_multiple=9.0,
    rev_cagr=0.07,
    ebitda_margin_expansion_bps=50,
)

engine = LBOEngine(parsed, assumptions, agent_id="domain_agent")
result = engine.generate_instructions()
```

## LBOAssumptions — Full Reference

All fields have defaults. Override only what you need.

### Deal Structure
| Parameter | Default | Description |
|-----------|---------|-------------|
| `entry_multiple` | `8.0` | EV / Entry EBITDA |
| `tlb_pct_tev` | `0.45` | Term Loan B as % of TEV |
| `rcf_availability` | `50.0` | RCF facility size ($) |
| `rcf_draw_at_close` | `0.0` | RCF drawn at transaction close ($) |
| `seller_note_pct_tev` | `0.0` | Seller note as % of TEV |
| `rolled_equity` | `0.0` | Management rollover equity ($) |
| `cash_floor` | `5.0` | Minimum cash balance ($) |
| `dividend_flag` | `1` | 1=pay dividends when FCF positive |

### Revenue & Margins
| Parameter | Default | Description |
|-----------|---------|-------------|
| `rev_cagr` | `0.05` | Revenue CAGR for projection years |
| `projection_years` | `5` | Years to project (max 6) |
| `gross_margin_target` | `None` | Override gross margin (decimal: 0.40 = 40%) |
| `ebitda_margin_target` | `None` | Override EBITDA margin (decimal) |
| `ebitda_margin_expansion_bps` | `0.0` | Annual margin step-up in basis points |

### Capex
| Parameter | Default | Description |
|-----------|---------|-------------|
| `maint_capex_pct_rev` | `0.02` | Maintenance capex % of revenue |
| `growth_capex_pct_rev` | `0.01` | Growth capex % of revenue |

### Debt Pricing
| Parameter | Default | Description |
|-----------|---------|-------------|
| `tlb_spread` | `0.05` | TLB SOFR spread (e.g. 0.055 = SOFR+5.5%) |
| `tlb_amort_years` | `7` | Years over which TLB amortizes |
| `tlb_disc_paydown` | `0` | 1=sweep excess cash to TLB |
| `seller_note_rate` | `0.10` | Seller note cash/PIK rate |
| `cash_interest_rate` | `0.0` | Interest earned on cash |

### Exit
| Parameter | Default | Description |
|-----------|---------|-------------|
| `exit_multiple` | `8.0` | Base case exit EV/EBITDA |
| `exit_multiple_upside` | `entry + 1.0` | Upside exit multiple |
| `exit_multiple_downside` | `entry - 1.0` | Downside exit multiple |

### Guardrails
| Parameter | Default | Behaviour |
|-----------|---------|-----------|
| `max_leverage_hard` | `8.0x` | Hard stop — raises `LBOEngineError` |
| `max_leverage_soft` | `7.0x` | Soft warning — added to `violations[]` |
| `min_equity_pct_hard` | `15%` | Hard stop — raises `LBOEngineError` |
| `min_equity_pct_soft` | `25%` | Soft warning — added to `violations[]` |

## Output Schema

```python
result = engine.generate_instructions()

result["instructions"]    # list of cell-level write ops → pass to batch_write()
result["assumptions_used"]# dict of all resolved assumptions
result["warnings"]        # data quality issues (from parser + engine)
result["violations"]      # soft guardrail breaches
result["summary"]         # high-level deal metrics
```

### Instruction format (compatible with `advanced_excel.batch_write`)
```json
{
  "sheet": "Model",
  "cell": "H5",
  "value": "AcmeCorp",
  "label": "Company name"
}
```

### Summary dict
```python
{
  "company": "AcmeCorp",
  "entry_year": 2025,
  "entry_ebitda": 94.0,
  "entry_revenue": 520.0,
  "tev": 799.0,
  "entry_multiple": 8.5,
  "total_debt": 399.5,
  "equity": 399.5,
  "leverage_at_entry": 4.25,
  "equity_pct_tev": 0.50,
  "exit_multiple": 9.0,
  "proj_ebitda_y5": 150.1,
  "implied_exit_ev": 1350.6,
  "instruction_count": 109,
}
```

## Sections Populated

| Section | Model cells | Logic |
|---------|-------------|-------|
| General Assumptions | H5–H20 | Company name, dates, tax rate, scenario |
| Entry Valuation | `Output AVP!I5`, `Model!M9–M10` | TEV = EBITDA × entry multiple; gross debt & cash from parsed data |
| Sources & Uses | C7–C10, D10 | Equity check, TLB %, seller note, RCF draw |
| Historical IS | F26–I31, F42–I42, F65–I65, F98–I98 | Revenue → BL1 (lines 2–6 zeroed); COGS derived from gross margin; SG&A derived from revenue − COGS − EBITDA |
| Projection Assumptions | U33–Z38, U52–Z60, U78–Z87, U123–Z124 | Revenue CAGR or explicit; COGS% from gross margin; SG&A growth at half rev growth; capex% of rev |
| Debt Schedule | C204–E210, C221, C230–C233, B257–D259 | TLB sizing, RCF facility, seller note, interest rates, pricing grid |
| Exit & Returns | K18, L18, M18 | Base/upside/downside exit multiples |

## Modelling Rules

**Revenue:** All historical revenue consolidated into Business Line 1 (rows 26–31). Lines 2–6 zeroed. Projection growth rate = CAGR from assumptions or implied from explicit projected values.

**COGS:** Derived from gross margin in parsed data. Written to COGS 1 as % of revenue. COGS 2–9 are zeroed.

**SG&A:** Derived as `Revenue − COGS − EBITDA` for historical years. Projection growth at `rev_cagr × 0.5` (slower than revenue → margin expansion).

**EBITDA Adjustments:** Adjustment 1 used for reconciliation (set to 0 unless parsed Adj. EBITDA differs from reported EBITDA).

**Debt sizing:** TLB = `tlb_pct_tev × TEV`. Seller note = `seller_note_pct_tev × TEV`. Equity = TEV − all debt + rolled equity.

**Exit EBITDA:** Year 5 from parsed projections if available; otherwise estimated via `entry_rev × (1+rev_cagr)^5 × (entry_margin + expansion)`.

## Guardrails

```python
# Hard stops — raise LBOEngineError before any instructions are generated
leverage > max_leverage_hard       → HARD STOP
equity_pct < min_equity_pct_hard  → HARD STOP

# Soft — generate instructions but add to violations[]
leverage > max_leverage_soft       → violations[]
equity_pct < min_equity_pct_soft  → violations[]

# Data quality — added to warnings[]
parsed field confidence='not_found' for critical fields (revenue, ebitda, debt, cash)
EBIT ≠ EBITDA − D&A               → warnings[]
Net Debt ≠ Debt − Cash            → warnings[]
```

## Error Handling

```python
from lbo_engine import LBOEngine, LBOAssumptions, LBOEngineError

try:
    result = engine.generate_instructions()
except LBOEngineError as e:
    # Hard guardrail breached — do not proceed to Excel population
    print(f"Aborted: {e}")
    # Retry with lower leverage or different assumptions
```

## Wiring It All Together

```python
from data_parser import parse_document
from lbo_engine import LBOEngine, LBOAssumptions, LBOEngineError
from advanced_excel import AdvancedExcel

# Step 1: Parse source document
parsed = parse_document("CIM_AcmeCorp.pdf", agent_id="parser")

# Step 2: Generate instructions
assumptions = LBOAssumptions(entry_multiple=8.5, tlb_pct_tev=0.50, exit_multiple=9.0)
engine = LBOEngine(parsed, assumptions)
result = engine.generate_instructions()

# Inspect warnings and violations before writing
if result["violations"]:
    print("Guardrail violations:", result["violations"])

# Step 3: Execute instructions into Excel
tool = AdvancedExcel("IOI Model Template.xlsx", "output/AcmeCorp_LBO.xlsx", agent_id="excel")
write_results = tool.batch_write(result["instructions"])

# Step 4: Check for write errors
errors = [r for r in write_results if r["status"] == "error"]
if errors:
    print("Write errors:", errors)

tool.save()
tool.save_audit_log()
```

## Cell Map Overrides

If your template differs from `IOI Model Template.xlsx`, override any cell mapping:

```python
engine = LBOEngine(parsed, assumptions, cell_map_overrides={
    "entry_tev": ("Valuation", "C5"),   # different sheet/cell
    "company_name": ("Cover", "B2"),
})
```

## Notes

- The engine never calls the Excel file directly. It only generates instructions.
- All monetary values must be in the same units as `parsed["metadata"]["units"]` (e.g. USD millions).
- The model scenario selector (`Model!H10`) is set to `1` (Base Case) by default. Change `assumptions.scenario` to switch.
- For multi-scenario analysis, run `generate_instructions()` once per scenario with different assumptions.
- Entry EBITDA missing or zero → `LBOEngineError` (cannot compute TEV without it).
