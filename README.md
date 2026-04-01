# claude-lbo-pipeline

A multi-agent system built on [Claude Code](https://claude.ai/claude-code) that automatically populates an LBO (Leveraged Buyout) Excel model from raw financial documents — CIMs, management presentations, spreadsheets, or screenshots.

Upload financials, run one command, get a fully populated model with a QA report.

---

## How It Works

The pipeline is a 3-agent team that runs sequentially inside Claude Code's experimental agent-teams feature:

```
/new-deal WidgetCo 6.0 0.50
        │
        ▼
  [Lead Agent]
  Parses financials → builds extracted-logic.json
  Writes teammate briefs → spawns team
        │
        ├──▶ [Teammate 1: Data & Logic Dev]
        │    Validates JSON → runs LBOEngine → produces 109 cell instructions
        │
        ├──▶ [Teammate 2: Excel Exec]
        │    Polls for T1 DONE → batch_write → force-write formula cells → saves model
        │
        └──▶ [Teammate 3: QA]
             Polls for T2 DONE → runs 7 checks → writes QA report (PASS/FAIL)
```

Each deal runs in an isolated folder (`output/<DealName>/`) so multiple deals never interfere.

---

## Repository Layout

```
claude-lbo-pipeline/
├── IOI Model Template.xlsx          # YOUR template goes here (not included — see Quickstart)
├── advanced_excel.py                # Agent tool: read/write/format Excel cells
├── data_parser.py                   # Agent tool: parse financial docs → LBO JSON
├── lbo_engine.py                    # LBO Brain: JSON → 109 cell-level instructions
├── run_lbo_pipeline.py              # Single-file reference pipeline (no teammates)
│
├── agents/
│   ├── brief-data-logic-dev.md      # Teammate 1: validate JSON + run LBO engine
│   ├── brief-excel-exec.md          # Teammate 2: write 109 cells into Excel model
│   ├── brief-qa.md                  # Teammate 3: verify model + write QA report
│   └── assumptions-reference.md    # Full LBOAssumptions parameter reference
│
├── .claude/
│   ├── CLAUDE.md                    # Project config read by Claude Code
│   └── skills/
│       ├── new-deal/                # /new-deal skill — main entry point
│       │   └── SKILL.md
│       ├── advanced-excel/          # /advanced-excel skill
│       ├── data-parsing/            # /data-parsing skill
│       ├── financial-domain-expert/ # /financial-domain-expert skill
│       └── skill-builder/           # /skill-builder skill
│
├── docs/
│   └── agent-teams-reference.md    # How Claude Code agent teams work
│
└── output/                         # gitignored — deal workspaces created here
    └── <DealName>/
        ├── extracted-logic.json
        ├── instructions-for-excel-exec.json
        ├── LBO_populated.xlsx
        ├── LBO_populated_audit.json
        ├── data-logic-dev-status.md
        ├── excel-exec-status.md
        └── qa-status.md
```

---

## Requirements

- [Claude Code](https://claude.ai/claude-code) (CLI or desktop app)
- Python 3.10+
- `openpyxl` — Excel read/write
- `anthropic` — Claude API (used by `data_parser.py` for vision-based document parsing)

```bash
pip install openpyxl anthropic
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Enable the experimental agent-teams feature:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## Quickstart

### 1. Clone and open in Claude Code

```bash
git clone https://github.com/DeoxysDefense/claude-lbo-pipeline.git
cd claude-lbo-pipeline
claude .
```

### 2. Add your LBO model template

The Excel template is **not included** in this repo — you need to provide your own.

Place your `.xlsx` LBO model in the project root and name it exactly:

```
IOI Model Template.xlsx
```

The pipeline reads from this file as a base and writes a populated copy to `output/<DealName>/LBO_populated.xlsx` — the original is never modified.

> **Sheet names must match:** The model expects sheets named `Model`, `Output AVP`, `P&L (presentation)`, and `PB_CACHE`. If your template uses different sheet names, update the cell references in `lbo_engine.py` and `advanced_excel.py` accordingly.

### 3. Upload your financial documents

Drop CIM, management presentation, or screenshots into the chat. Supported formats: `.xlsx`, `.pdf`, `.pptx`, `.docx`, images.

### 3. Run the pipeline

```
/new-deal AcmeCorp 6.5 0.50
```

Arguments:
- `AcmeCorp` — deal name (used for folder and file naming)
- `6.5` — entry EV/EBITDA multiple (default: `5.0`)
- `0.50` — Term Loan B as % of TEV (default: `0.45`)

### 4. Get your outputs

```
output/AcmeCorp/LBO_populated.xlsx          ← populated model
output/AcmeCorp/LBO_populated_audit.json    ← full write audit log
docs/qa-report-AcmeCorp.md                 ← QA report (PASS/FAIL + 7 checks)
```

---

## Skills Reference

| Skill | Command | What it does |
|-------|---------|--------------|
| `new-deal` | `/new-deal [Name] [entry_multiple] [tlb_pct]` | Full pipeline: parse → engine → Excel → QA |
| `data-parsing` | `/data-parsing` | Parse a financial document to LBO JSON |
| `financial-domain-expert` | `/financial-domain-expert` | Run LBO engine on existing JSON |
| `advanced-excel` | `/advanced-excel` | Read/write/inspect the Excel model directly |
| `skill-builder` | `/skill-builder` | Build or audit Claude Code skills |

---

## LBO Engine — Key Assumptions

The engine (`lbo_engine.py`) takes a `LBOAssumptions` dataclass. All parameters have sensible defaults. Common overrides:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `entry_multiple` | `5.0` | EV / Entry EBITDA |
| `tlb_pct_tev` | `0.45` | Term Loan B as % of TEV |
| `gross_margin_target` | `0.60` | Gross margin (60% = 40% COGS) |
| `tax_rate` | `0.25` | Corporate tax rate |
| `exit_multiple` | `= entry` | Base case exit multiple |
| `projection_years` | `5` | Years to project (max 6) |

Full parameter reference: [`agents/assumptions-reference.md`](agents/assumptions-reference.md)

---

## Output Model Structure

The populated `LBO_populated.xlsx` contains:

- **Model sheet** — all 109 input cells written (assumptions, IS, debt schedule, returns)
- **Output AVP** — transaction summary (TEV, leverage, equity%, MOIC)
- **P&L (presentation)** — clean income statement for IC presentation

The engine enforces guardrails:
- Leverage > 7.0x → soft warning; > 8.0x → hard error
- Equity < 25% of TEV → soft warning; < 15% → hard error

---

## Agent Teams Architecture

Each teammate is a fully self-contained Claude Code agent spawned with its own briefing MD. Teammates communicate via status files:

```
data-logic-dev-status.md  →  PENDING / DONE / ERROR
excel-exec-status.md      →  PENDING / DONE / ERROR
qa-status.md              →  PENDING / DONE / ERROR
```

Teammates poll their dependency's status file before starting. If upstream is `ERROR`, the downstream teammate stops and reports to lead.

See [`docs/agent-teams-reference.md`](docs/agent-teams-reference.md) for the full architecture guide.

---

## License

MIT
