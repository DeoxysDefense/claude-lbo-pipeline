# LBO Assumptions Reference

Full list of overrideable parameters for `LBOAssumptions`.
All monetary values in USD millions. Rates are decimals (0.25 = 25%).

## Deal Structure

| Parameter | Default | Description |
|-----------|---------|-------------|
| `entry_multiple` | `5.0` | EV / Entry EBITDA |
| `tlb_pct_tev` | `0.45` | Term Loan B as % of TEV |
| `rcf_availability` | `5.0` | RCF facility size ($M) |
| `rcf_draw_at_close` | `0.0` | RCF drawn at transaction close ($M) |
| `seller_note_pct_tev` | `0.0` | Seller note as % of TEV |
| `rolled_equity` | `0.0` | Management rollover equity ($M) |
| `cash_floor` | `1.5` | Minimum cash balance ($M) |
| `dividend_flag` | `1` | 1=pay dividends when FCF positive |

## Revenue & Margins

| Parameter | Default | Description |
|-----------|---------|-------------|
| `projection_years` | `5` | Years to project (max 6) |
| `rev_cagr` | derived | Revenue CAGR — computed from explicit projections if available |
| `gross_margin_target` | `0.60` | Override gross margin (decimal: 0.60 = 60%) |
| `ebitda_margin_target` | `None` | Override EBITDA margin (decimal) |
| `ebitda_margin_expansion_bps` | `0` | Annual margin step-up in basis points |

## Capex

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maint_capex_pct_rev` | `0.01` | Maintenance capex % of revenue |
| `growth_capex_pct_rev` | `0.005` | Growth capex % of revenue |

## Tax & Accounting

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tax_rate` | `0.25` | Corporate tax rate |
| `depreciable_life` | `5` | Asset depreciable life (years) |
| `earnout_2025` | `0.0` | 2025 earnout paid 2026 ($M) |
| `earnout_2026` | `0.0` | 2026 earnout paid 2027 ($M) |

## Debt Pricing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tlb_spread` | `0.055` | TLB SOFR spread (e.g. 0.055 = SOFR+5.5%) |
| `tlb_amort_years` | `7` | Years over which TLB amortizes |
| `tlb_disc_paydown` | `1` | 1=sweep excess cash to TLB |
| `tlb_max_paydown` | `10.0` | Max discretionary paydown per year ($M) |
| `seller_note_rate` | `0.10` | Seller note cash/PIK rate |
| `cash_interest_rate` | `0.0` | Interest earned on cash balance |

## Exit

| Parameter | Default | Description |
|-----------|---------|-------------|
| `exit_multiple` | `= entry_multiple` | Base case exit EV/EBITDA |
| `exit_multiple_upside` | `exit + 1.0` | Upside exit multiple |
| `exit_multiple_downside` | `exit - 1.0` | Downside exit multiple |

## Guardrails (do not change unless instructed)

| Parameter | Default | Behaviour |
|-----------|---------|-----------|
| `max_leverage_hard` | `8.0x` | Hard stop — raises LBOEngineError |
| `max_leverage_soft` | `7.0x` | Soft warning — added to violations[] |
| `min_equity_pct_hard` | `15%` | Hard stop |
| `min_equity_pct_soft` | `25%` | Soft warning |

## Common Override Examples

```python
# Higher leverage deal
LBOAssumptions(entry_multiple=7.5, tlb_pct_tev=0.55)

# Seller note included
LBOAssumptions(entry_multiple=6.0, seller_note_pct_tev=0.10)

# Higher-growth company, explicit EBITDA margin target
LBOAssumptions(entry_multiple=8.0, ebitda_margin_target=0.25, ebitda_margin_expansion_bps=50)

# Conservative capex for asset-heavy business
LBOAssumptions(maint_capex_pct_rev=0.05, growth_capex_pct_rev=0.02)

# Different tax jurisdiction
LBOAssumptions(tax_rate=0.21)  # US federal rate
```
