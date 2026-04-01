---
name: data-parsing
description: Use when an AI agent needs to extract financial data from an uploaded document (Excel, PowerPoint, PDF, Word, or image screenshot) and convert it into the standardized LBO JSON schema. Covers CIM decks, financial statements, data rooms, and any document containing income statement, balance sheet, or cash flow data.
disable-model-invocation: true
---

## What This Skill Does

Extracts financial data from uploaded documents and returns a strictly
standardized JSON schema that downstream LBO agents can consume directly.
Every numeric field is wrapped with a confidence flag. Missing fields are
`null` — never fabricated. A `warnings[]` array flags data integrity issues.

## Supported File Types

| Extension | Extraction method |
|-----------|------------------|
| `.xlsx` | `openpyxl` (deterministic) → Claude normalizes |
| `.pptx` | `python-pptx` text/table extraction → Claude normalizes; vision fallback for image-heavy slides |
| `.pdf` | `pdfplumber` text/table extraction → Claude normalizes; vision fallback for scanned pages |
| `.docx` | `python-docx` text/table extraction → Claude normalizes |
| `.png` `.jpg` `.jpeg` `.webp` | Claude vision directly |

## Setup

```python
from data_parser import parse_document

# ANTHROPIC_API_KEY must be set in environment (required for all non-xlsx types)
result = parse_document(
    "CIM_AcmeCorp.pdf",
    agent_id="extraction_agent",   # recorded in metadata
    api_key=None,                  # defaults to ANTHROPIC_API_KEY env var
)
```

## Output Schema

```json
{
  "metadata": {
    "company_name": "AcmeCorp",
    "fiscal_year_end": "12-31",
    "currency": "USD",
    "units": "millions",
    "source_file": "CIM_AcmeCorp.pdf",
    "extracted_at": "2026-03-31T10:00:00+00:00",
    "agent_id": "extraction_agent",
    "model": "claude-opus-4-6"
  },
  "historical": [
    {
      "year": 2023,
      "revenue":           { "value": 500.0,  "confidence": "high" },
      "gross_profit":      { "value": 200.0,  "confidence": "high" },
      "gross_margin_pct":  { "value": 40.0,   "confidence": "high" },
      "ebitda":            { "value": 85.0,   "confidence": "high" },
      "ebitda_margin_pct": { "value": 17.0,   "confidence": "high" },
      "da":                { "value": 20.0,   "confidence": "high" },
      "ebit":              { "value": 65.0,   "confidence": "high" },
      "net_income":        { "value": 40.0,   "confidence": "high" },
      "eps":               { "value": 2.50,   "confidence": "high" },
      "total_assets":      { "value": 800.0,  "confidence": "high" },
      "total_equity":      { "value": 300.0,  "confidence": "high" },
      "total_debt":        { "value": 250.0,  "confidence": "high" },
      "cash":              { "value": 50.0,   "confidence": "high" },
      "net_debt":          { "value": 200.0,  "confidence": "high" },
      "capex":             { "value": 30.0,   "confidence": "high" },
      "free_cash_flow":    { "value": 55.0,   "confidence": "high" }
    }
  ],
  "projected": [
    { "year": 2024, "revenue": { "value": 550.0, "confidence": "high" }, ... }
  ],
  "warnings": [
    "[historical 2022] EBITDA (200.0) exceeds Revenue (100.0) — likely a units mismatch."
  ],
  "raw_text": "... raw extracted text for debugging ..."
}
```

### Confidence levels

| Value | Meaning |
|-------|---------|
| `"high"` | Value found directly in the document |
| `"not_found"` | Field not present in document; `value` is `null` |

### Field conventions

- All monetary values in the `units` stated in `metadata` (e.g. USD millions)
- Percentages as plain numbers: `40.0` means 40.0%, **not** 0.40
- `capex` is always a positive absolute value
- `net_debt` = `total_debt` − `cash`
- `historical`: years labelled "actual", "A", or past calendar years
- `projected`: years labelled "estimate", "E", "forecast", "F", "budget", or future years

## Validation Warnings

The `warnings[]` array is populated automatically for:

| Check | Example warning |
|-------|----------------|
| EBITDA > Revenue | `EBITDA (200) exceeds Revenue (100)` |
| Gross Profit > Revenue | `Gross Profit (600) exceeds Revenue (500)` |
| EBIT > EBITDA | `EBIT (90) exceeds EBITDA (85)` — implies negative D&A |
| Net Income > EBITDA | `Net Income (100) exceeds EBITDA (85)` |
| Net Debt mismatch | `total_debt − cash ≠ stated net_debt` (tolerance ±1.0) |
| Margin mismatch | Computed EBITDA margin ≠ stated margin (tolerance ±2%) |
| Negative capex | `Capex is negative` |

Warnings do **not** abort extraction. Downstream agents decide how to handle them.

## Error Handling

```python
from data_parser import parse_document

try:
    result = parse_document("deck.pdf", agent_id="my_agent")
except FileNotFoundError as e:
    print(f"File missing: {e}")
except ValueError as e:
    print(f"Unsupported file or bad AI response: {e}")
except EnvironmentError as e:
    print(f"API key not set: {e}")
```

## CLI Usage

```bash
python data_parser.py CIM_AcmeCorp.pdf extraction_agent
```

Prints the full JSON result to stdout.

## Notes

- `ANTHROPIC_API_KEY` must be set for all non-.xlsx files. `.xlsx` parsing is fully deterministic.
- `raw_text` in the output contains the raw pre-AI text (for debugging extraction issues). Set to `null` for image/vision paths.
- For very large PDFs (50+ pages), consider splitting into sections before parsing to stay within token limits.
- The model used is `claude-opus-4-6` for maximum extraction accuracy on complex financial layouts.
- Never pass the LBO template (`IOI Model Template.xlsx`) to this parser — use `advanced_excel.py` for that.
