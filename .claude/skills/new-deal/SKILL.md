---
name: new-deal
description: Use when someone wants to start a new LBO model, analyze a new deal, upload new financial data for a new company, or run a second LBO scenario. Kicks off a fully isolated deal pipeline with its own folder, teammate briefs, and agent team.
disable-model-invocation: true
argument-hint: [DealName] [entry_multiple] [tlb_pct]
---

## What This Skill Does

Creates a fully isolated deal workspace under `output/<DealName>/`, builds
the three teammate briefing MDs with all paths scoped to that deal, parses
the financial data the user provides, and spawns the LBO-team to run the
pipeline end-to-end.

Each deal is completely isolated — no files are shared with other deals.
Running `/new-deal WidgetCo` never touches `output/AcmeCorp/`.

**Data flow:**
```
/new-deal <DealName> [assumptions]
  → create output/<DealName>/
  → parse financial data → output/<DealName>/extracted-logic.json
  → write teammate briefs (all paths scoped to output/<DealName>/)
  → spawn LBO-team → teammates run pipeline
  → output/<DealName>/LBO_populated.xlsx + docs/qa-report-<DealName>.md
```

---

## Steps

### Step 1 — Parse arguments

`$ARGUMENTS` will be one of:
- `WidgetCo` — just a deal name, use all default assumptions
- `WidgetCo 6.0 0.50` — deal name + entry_multiple + tlb_pct_tev
- `WidgetCo 6.0` — deal name + entry_multiple only

Extract:
- `DEAL_NAME` = first token (required). Sanitize: alphanumeric + hyphens only, max 32 chars.
- `ENTRY_MULTIPLE` = second token as float, default `5.0`
- `TLB_PCT` = third token as float (0–1), default `0.45`

If `$ARGUMENTS` is empty, ask the user: "What is the deal name, and do you have a specific entry multiple in mind?"

### Step 2 — Check for existing deal folder

Check if `output/<DEAL_NAME>/` already exists.
- If it exists and contains `LBO_populated.xlsx`: warn the user —
  "output/<DEAL_NAME>/ already has a completed model. Use a different name
  or delete the folder to rerun." Stop.
- If it exists but is empty or has only status files: proceed (it's a partial run).
- If it does not exist: create it with `mkdir`.

```bash
mkdir -p "output/<DEAL_NAME>"
```

### Step 3 — Get financial data from the user

If the user has already provided financial data (screenshots, PDF, Excel, or
pasted numbers) in this conversation — use that data directly to build the
extracted JSON in Step 4.

If no data has been provided yet, ask:
> "Please share the financial data for <DEAL_NAME>. You can upload screenshots,
> a PDF CIM, an Excel file, or paste the numbers directly. I need at minimum:
> - Historical revenue and Adj. EBITDA (2–4 years)
> - Projected revenue and Adj. EBITDA (3–5 years)
> - Any balance sheet data you have (debt, cash)"

Wait for the user's response before continuing.

### Step 4 — Build extracted-logic.json

Parse the financial data provided and write
`output/<DEAL_NAME>/extracted-logic.json`.

Follow the exact schema from `output/extracted-logic.json` (the reference file
for Deal 1 — read it to understand the format). Key rules:

- `metadata.company_name` = DEAL_NAME
- All monetary values in USD millions. If source data is in thousands, divide by 1000.
- Historical years: use FYE label from the data. The last actual year = entry year.
- Projected years: use as-provided. Interpolate any missing intermediate years
  using implied CAGR from the endpoints.
- Wrap every field as `{"value": <number or null>, "confidence": "high"|"medium"|"not_found"}`.
- If gross margin is not in source data, set `gross_margin_pct` to
  `{"value": null, "confidence": "not_found"}` — the engine will handle it.
- Write a `warnings` array noting any estimated or interpolated values.

After writing, read back the file and confirm:
- Entry year EBITDA > 0
- At least 2 historical years
- At least 3 projected years

### Step 5 — Write teammate briefs

Write three files under `output/<DEAL_NAME>/`:

**`output/<DEAL_NAME>/teammate-data-logic-dev.md`**

Use the template at `agents/brief-data-logic-dev.md`,
substituting every occurrence of `<DEAL_NAME>`, `<ENTRY_MULTIPLE>`,
and `<TLB_PCT>` with the resolved values.

**`output/<DEAL_NAME>/teammate-excel-exec.md`**

Use the template at `agents/brief-excel-exec.md`,
substituting `<DEAL_NAME>`.

**`output/<DEAL_NAME>/teammate-qa.md`**

Use the template at `agents/brief-qa.md`,
substituting `<DEAL_NAME>`.

### Step 6 — Initialize status files

Write these files so teammates can poll them:

```
output/<DEAL_NAME>/data-logic-dev-status.md  → "PENDING"
output/<DEAL_NAME>/excel-exec-status.md      → "PENDING"
output/<DEAL_NAME>/qa-status.md              → "PENDING"
```

### Step 7 — Spawn the LBO-team

Create an agent team called `<DEAL_NAME>-team` with 3 teammates using Sonnet.
Use `--teammate-mode in-process` (VS Code terminal).

**Teammate 1 — Data & Logic Dev**
Spawn with this prompt (fill in DEAL_NAME):
> "Read the full brief at `output/<DEAL_NAME>/teammate-data-logic-dev.md`
> and follow it exactly. Your working directory is
> `c:/Users/Administrator/Desktop/Project1/`. Start immediately."

**Teammate 2 — Excel Exec**
Spawn with this prompt:
> "Read the full brief at `output/<DEAL_NAME>/teammate-excel-exec.md`
> and follow it exactly. Your working directory is
> `c:/Users/Administrator/Desktop/Project1/`. Poll
> `output/<DEAL_NAME>/data-logic-dev-status.md` until it says DONE, then start."

**Teammate 3 — QA**
Spawn with this prompt:
> "Read the full brief at `output/<DEAL_NAME>/teammate-qa.md`
> and follow it exactly. Your working directory is
> `c:/Users/Administrator/Desktop/Project1/`. Poll both
> `output/<DEAL_NAME>/data-logic-dev-status.md` and
> `output/<DEAL_NAME>/excel-exec-status.md` until both say DONE, then start.
> Write your QA report to `docs/qa-report-<DEAL_NAME>.md`."

### Step 8 — Confirm to user

Report back:
```
Deal workspace created: output/<DEAL_NAME>/
Assumptions: entry_multiple=<X> | tlb_pct=<Y>
Team spawned: <DEAL_NAME>-team (3 teammates)

Files created:
  output/<DEAL_NAME>/extracted-logic.json
  output/<DEAL_NAME>/teammate-data-logic-dev.md
  output/<DEAL_NAME>/teammate-excel-exec.md
  output/<DEAL_NAME>/teammate-qa.md

Deliverables (when complete):
  output/<DEAL_NAME>/LBO_populated.xlsx
  docs/qa-report-<DEAL_NAME>.md
```

---

## Output Structure

```
output/
  <DEAL_NAME>/
    extracted-logic.json           ← financial data (JSON)
    instructions-for-excel-exec.json  ← cell-level instructions (written by teammate)
    LBO_populated.xlsx             ← populated model (written by teammate)
    LBO_populated_audit.json       ← write audit log
    teammate-data-logic-dev.md     ← spawn brief
    teammate-excel-exec.md         ← spawn brief
    teammate-qa.md                 ← spawn brief
    data-logic-dev-status.md       ← polling signal
    excel-exec-status.md           ← polling signal
    qa-status.md                   ← polling signal
docs/
  qa-report-<DEAL_NAME>.md         ← final QA report
```

---

## Notes

- Never write anything into an existing deal's folder without warning the user first.
- If the user provides a gross margin in the source data, write it into `gross_margin_pct`. If not, leave it `not_found` — do NOT default to 60%; the engine assumption `gross_margin_target` in the brief handles this.
- All monetary units in the extracted JSON must be USD millions. Convert from thousands if the source uses thousands.
- The entry year must be the last actual (non-projected) year in the data.
- If the user wants to run multiple deals at the same time, each gets its own `/new-deal` invocation and its own team — they run fully in parallel.
- For assumption overrides beyond `entry_multiple` and `tlb_pct`, the user can say so in natural language (e.g., "use 7-year model" or "no cash sweep") — incorporate those into the teammate-data-logic-dev.md brief's assumptions block.
- See `agents/assumptions-reference.md` for the full list of overrideable LBO assumptions and their defaults.
