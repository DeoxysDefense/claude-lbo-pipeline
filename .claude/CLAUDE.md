# Project Claude Configuration

## Project Overview

Multi-agent system that automatically populates an LBO Excel model
(`IOI Model Template.xlsx`) based on a strict set of rules.

## Skills

Custom skills are defined in `.claude/skills/[name]/SKILL.md`.

| Skill | Command | Purpose |
|-------|---------|---------|
| `skill-builder` | `/skill-builder` | Build, audit, and optimize Claude Code skills |
| `advanced-excel` | `/advanced-excel` | Agent tool for reading/writing/formatting the LBO Excel model |
| `data-parsing` | `/data-parsing` | Extract financial data from xlsx/pptx/pdf/docx/images into standardized LBO JSON |
| `financial-domain-expert` | `/financial-domain-expert` | Convert parsed JSON → LBO Execution Instructions (valuation, IS, debt schedule, returns) |
| `new-deal` | `/new-deal [DealName] [entry_multiple] [tlb_pct]` | Start a new isolated LBO deal pipeline — creates deal folder, parses financials, writes teammate briefs, spawns LBO-team |

## Key Files

| File | Purpose |
|------|---------|
| `IOI Model Template.xlsx` | Source LBO model template — **never modified directly** |
| `advanced_excel.py` | Python tool agents import to interact with the Excel file |
| `data_parser.py` | Python tool agents import to parse financial documents into LBO JSON schema |
| `lbo_engine.py` | LBO Brain — converts parsed JSON to cell-level Execution Instructions |
| `output/` | Working copies and audit logs produced by agents |

## Advanced Excel Tool — Quick Reference

```python
from advanced_excel import AdvancedExcel, ExcelToolError

tool = AdvancedExcel("IOI Model Template.xlsx", "output/LBO_populated.xlsx", agent_id="agent_name")

tool.read_cell("Model", "H5")
tool.write_cell("Model", "H5", "AcmeCorp")          # blocked if cell has formula
tool.write_formula("Model", "AK5", "=I109*1.1")
tool.batch_write([{"sheet": "Model", "cell": "H6", "value": 1}, ...])
tool.format_cell("Model", "I6", number_format='#,##0.0"x"', bold=True)
tool.save()
tool.save_audit_log()
```

Workbook sheets: `Model` (main inputs), `Output AVP`, `P&L (presentation)`, `PB_CACHE` (protected).

## Notes

- Agents must call `tool.save()` after writing to persist changes.
- Formula cells in `Model` are protected by default — use `write_formula()` or `force=True` to override.
- All operations are logged with timestamp, agent ID, sheet, cell, old/new value.
