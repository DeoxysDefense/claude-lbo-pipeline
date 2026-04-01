---
name: advanced-excel
description: Use when an AI agent needs to read, write, or format cells in the LBO Excel model (IOI Model Template.xlsx). Covers single cell reads/writes, batch writes, formula writes, cell formatting, and audit log retrieval.
disable-model-invocation: true
---

## What This Skill Does

Provides AI agents with a Python interface to physically interact with the LBO
Excel model (`IOI Model Template.xlsx`). Agents never modify the template
directly — they work on a saved copy and every operation is recorded in an
audit log.

## Workbook Structure

| Sheet | Range | Purpose |
|-------|-------|---------|
| `Model` | A2:AU398 | **Main input sheet** — agents write here |
| `Output AVP` | B2:AF87 | Output / print sheet |
| `P&L (presentation)` | A2:S37 | Presentation income statement |
| `PB_CACHE` | A1 | Internal cache — **protected, never touch** |

## Setup

```python
from advanced_excel import AdvancedExcel

tool = AdvancedExcel(
    template_path="IOI Model Template.xlsx",   # source template (never modified)
    output_path="output/LBO_populated.xlsx",   # working copy
    agent_id="my_agent",                       # recorded in audit log
)
```

## Operations

### Read a cell
```python
value = tool.read_cell("Model", "H5")
# Returns the raw value or formula string
```

### Read a range
```python
rows = tool.read_range("Model", "B5:H20")
# Returns list of lists: rows[row_index][col_index]
```

### Write a value
```python
tool.write_cell("Model", "H5", "AcmeCorp")
tool.write_cell("Model", "H6", 1)

# Raises ExcelToolError if cell contains a formula.
# Use force=True to overwrite a formula cell with a hard value (use sparingly).
tool.write_cell("Model", "B2", "Override", force=True)
```

### Write a formula
```python
tool.write_formula("Model", "AK5", "=I109*1.1")
# Formula must start with '='.
```

### Batch write (preferred for multi-cell operations)
```python
results = tool.batch_write([
    {"sheet": "Model", "cell": "H5",   "value": "AcmeCorp"},
    {"sheet": "Model", "cell": "I6",   "value": 8.5},
    {"sheet": "Model", "cell": "J6",   "formula": "=I6*1.1"},
    {"sheet": "Model", "cell": "H6",   "value": 1, "force": False},
])
# Returns list of {"sheet", "cell", "status": "ok"|"error", "error": "..."}
# Failed operations do NOT stop the batch — check results for errors.
```

### Format a cell
```python
tool.format_cell(
    "Model", "I6",
    number_format='#,##0.0"x"',   # e.g. 8.5x
    bold=True,
    font_color="FF0000",           # hex, no '#'
    bg_color="FFFF00",
    horizontal_align="center",     # 'left'|'center'|'right'
    border_style="thin",           # 'thin'|'medium'|'thick'|'dashed'
    font_size=10,
    font_name="Calibri",
)
```

### Check if cell has a formula
```python
tool.is_formula_cell("Model", "B2")   # True
tool.is_formula_cell("Model", "H5")   # False
```

### Save the working copy
```python
out_path = tool.save()
# Always call save() when done. Outputs go to output_path, template untouched.
```

### Audit log
```python
log = tool.get_audit_log()           # list of dicts
json_str = tool.get_audit_log(as_json=True)
audit_file = tool.save_audit_log()   # writes _audit.json alongside output file
```

Each audit entry contains:
- `timestamp` (UTC ISO 8601)
- `agent_id`
- `operation` (read | read_range | write | write_formula | format | save)
- `sheet`, `cell`
- `old_value`, `new_value`

## Guardrails

| Guard | Behaviour |
|-------|-----------|
| Formula protection | `write_cell` raises `ExcelToolError` if the target cell holds a formula. Use `write_formula` or `force=True` to override intentionally. |
| Protected sheet | Writing to `PB_CACHE` always raises `ExcelToolError`. |
| Invalid cell address | Any invalid address (e.g. `"BADCELL!"`) raises `ExcelToolError` before any write. |
| Template untouched | The source template is never written to — agents always work on the output copy. |

## Error Handling

```python
from advanced_excel import AdvancedExcel, ExcelToolError

try:
    tool.write_cell("Model", "B2", "bad write")
except ExcelToolError as e:
    print(f"Blocked: {e}")
```

## Common Number Formats

| Format string | Example output |
|---------------|----------------|
| `'#,##0.0"x"'` | 8.5x |
| `'0.0%'` | 12.3% |
| `'$#,##0'` | $1,500,000 |
| `'#,##0.0'` | 1,500.0 |
| `'0.00'` | 3.14 |

## Notes

- Always call `tool.save()` at the end of a session or after significant changes.
- Use `batch_write` for multi-cell writes — it's more efficient and returns per-cell status.
- `read_range` returns formula strings (not computed values) because the file is loaded without `data_only=True`. To get computed values you would need a live Excel process (xlwings).
- The `Model` sheet is the primary target for agent writes. `Output AVP` and `P&L (presentation)` are mostly formula-driven and should rarely need direct writes.
