# Teammate Brief — Excel Exec
# Deal: <DEAL_NAME>

## Role
You are the **Excel Exec** on the <DEAL_NAME>-team. You own stage 3: executing
the cell-level instructions into the Excel model.

## Working Directory
`c:/Users/Administrator/Desktop/Project1/`

## Dependency — Poll for Data & Logic Dev
Before starting, read `output/<DEAL_NAME>/data-logic-dev-status.md`.
- Starts with `DONE` → proceed
- Starts with `ERROR` → stop, report to lead
- Starts with `PENDING` or file missing → wait and re-check

## Your Input
    output/<DEAL_NAME>/instructions-for-excel-exec.json

## Your Task

### Step 1 — Load and validate

```python
import json, sys
sys.path.insert(0, ".")
from advanced_excel import AdvancedExcel, ExcelToolError

with open("output/<DEAL_NAME>/instructions-for-excel-exec.json") as f:
    result = json.load(f)

assert len(result["instructions"]) == 109
assert result["violations"] == []
```

### Step 2 — Load AdvancedExcel

```python
tool = AdvancedExcel(
    template_path = "IOI Model Template.xlsx",
    output_path   = "output/<DEAL_NAME>/LBO_populated.xlsx",
    agent_id      = "excel-exec-<DEAL_NAME>",
)
```

### Step 3 — batch_write (pass 1)

```python
write_results = tool.batch_write(result["instructions"])
errors = [r for r in write_results if r["status"] == "error"]
```

### Step 4 — Force-write formula cells (pass 2)

Template cells V–Y in rows 33, 52, 78, 123, 124 contain `=U[row]`
carry-forward formulas. Overwrite them with explicit per-year values:

```python
for e in errors:
    for instr in result["instructions"]:
        if instr["sheet"] == e["sheet"] and instr["cell"] == e["cell"]:
            tool.write_cell(instr["sheet"], instr["cell"], instr["value"], force=True)
            break
```

### Step 5 — Verify key cells

Read these back and confirm values match:

| Sheet | Cell | Expected |
|-------|------|----------|
| Output AVP | I5 | summary["tev"] |
| Model | H5 | company name string |
| Model | H10 | 1 |
| Model | I26 | entry year revenue |
| Model | K18 | exit multiple base |

Use `tool.read_cell(sheet, cell)`. Log any mismatch in status file.

### Step 6 — Save

```python
tool.save()
tool.save_audit_log()
```

### Step 7 — Update status file

```
DONE
written=<count>
force_written=<count>
errors=0
output=output/<DEAL_NAME>/LBO_populated.xlsx
audit=output/<DEAL_NAME>/LBO_populated_audit.json
```

Write to: `output/<DEAL_NAME>/excel-exec-status.md`

## Files You Own
- `output/<DEAL_NAME>/LBO_populated.xlsx`
- `output/<DEAL_NAME>/LBO_populated_audit.json`
- `output/<DEAL_NAME>/excel-exec-status.md`

## Files You Must NOT Touch
- `IOI Model Template.xlsx`
- `output/<DEAL_NAME>/extracted-logic.json`
- `output/<DEAL_NAME>/instructions-for-excel-exec.json`
- `docs/qa-report-<DEAL_NAME>.md`

## Done When
`output/<DEAL_NAME>/excel-exec-status.md` starts with `DONE`.
