"""
lbo_engine.py
-------------
Financial & Accounting Domain Expert — the "Brain" of the LBO multi-agent system.

Takes standardized JSON output from data_parser.parse_document() and generates
a structured list of Execution Instructions that advanced_excel.batch_write()
executes blindly.

Usage:
    from data_parser import parse_document
    from lbo_engine import LBOEngine, LBOAssumptions

    parsed = parse_document("CIM_AcmeCorp.pdf")

    assumptions = LBOAssumptions(
        entry_multiple=8.5,
        tlb_pct_tev=0.50,
        exit_multiple=9.0,
    )

    engine = LBOEngine(parsed, assumptions)
    result = engine.generate_instructions()

    # result["instructions"] → pass to advanced_excel.batch_write()
    # result["warnings"]     → data quality issues
    # result["violations"]   → guardrail breaches
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Cell Map — hard-coded from IOI Model Template.xlsx
# Keys are logical field names; values are (sheet, cell) tuples.
# ---------------------------------------------------------------------------

CELL_MAP: dict[str, tuple[str, str]] = {
    # ── General Assumptions ──────────────────────────────────────────────
    "company_name":         ("Model", "H5"),
    "circuit_breaker":      ("Model", "H6"),   # 1=on (use LBO mechanics), 0=off
    "last_fy_close":        ("Model", "H7"),   # datetime: last historical FY end
    "expected_close":       ("Model", "H8"),   # datetime: transaction close date
    "scenario":             ("Model", "H10"),  # 1=Base, 2=Mgmt, 3=Downside, 4=S.Q.
    "currency_units":       ("Model", "H11"),  # text: "millions"
    "cash_floor":           ("Model", "H15"),  # minimum cash balance
    "tax_rate":             ("Model", "H17"),  # decimal e.g. 0.25
    "depreciable_life":     ("Model", "H18"),  # years e.g. 7
    "dividend_flag":        ("Model", "M15"),  # 1=pay dividends, 0=no
    "earnout_2025":         ("Model", "H19"),  # 2025 earnout paid 2026
    "earnout_2026":         ("Model", "H20"),  # 2026 earnout paid 2027

    # ── Entry Valuation ───────────────────────────────────────────────────
    # TEV is the master input; lives in Output AVP and flows into Model!C11
    "entry_tev":            ("Output AVP", "I5"),
    "entry_gross_debt":     ("Model", "M9"),   # gross debt at entry (for offer value calc)
    "entry_cash":           ("Model", "M10"),  # cash at entry

    # ── Sources & Uses ────────────────────────────────────────────────────
    "rolled_equity":        ("Model", "C7"),   # management rollover equity $
    "seller_note_draw":     ("Model", "C8"),   # seller note drawn at close $
    "rcf_draw_at_close":    ("Model", "C9"),   # revolver drawn at close $
    "tlb_pct_tev":          ("Model", "D10"),  # TLB as % of TEV (decimal)

    # ── Income Statement — Historical (columns F G H I = 4 hist years) ───
    # Revenue: all revenue written to Business Line 1; lines 2-6 zeroed
    "rev_hist_bl1_y1":      ("Model", "F26"),  # entry_year - 3
    "rev_hist_bl1_y2":      ("Model", "G26"),  # entry_year - 2
    "rev_hist_bl1_y3":      ("Model", "H26"),  # entry_year - 1
    "rev_hist_bl1_y4":      ("Model", "I26"),  # entry_year
    "rev_hist_bl2_y1":      ("Model", "F27"),
    "rev_hist_bl2_y2":      ("Model", "G27"),
    "rev_hist_bl2_y3":      ("Model", "H27"),
    "rev_hist_bl2_y4":      ("Model", "I27"),
    "rev_hist_bl3_y1":      ("Model", "F28"),
    "rev_hist_bl3_y2":      ("Model", "G28"),
    "rev_hist_bl3_y3":      ("Model", "H28"),
    "rev_hist_bl3_y4":      ("Model", "I28"),
    "rev_hist_bl4_y1":      ("Model", "F29"),
    "rev_hist_bl4_y2":      ("Model", "G29"),
    "rev_hist_bl4_y3":      ("Model", "H29"),
    "rev_hist_bl4_y4":      ("Model", "I29"),
    "rev_hist_bl5_y1":      ("Model", "F30"),
    "rev_hist_bl5_y2":      ("Model", "G30"),
    "rev_hist_bl5_y3":      ("Model", "H30"),
    "rev_hist_bl5_y4":      ("Model", "I30"),
    "rev_hist_bl6_y1":      ("Model", "F31"),
    "rev_hist_bl6_y2":      ("Model", "G31"),
    "rev_hist_bl6_y3":      ("Model", "H31"),
    "rev_hist_bl6_y4":      ("Model", "I31"),

    # Revenue growth assumptions — Base Case (cols U-Z = proj years 1-6)
    "rev_growth_bl1_p1":    ("Model", "U33"),
    "rev_growth_bl1_p2":    ("Model", "V33"),
    "rev_growth_bl1_p3":    ("Model", "W33"),
    "rev_growth_bl1_p4":    ("Model", "X33"),
    "rev_growth_bl1_p5":    ("Model", "Y33"),
    "rev_growth_bl1_p6":    ("Model", "Z33"),

    # COGS 1 % of Revenue — Base Case (cols U-Z)
    "cogs1_pct_p1":         ("Model", "U52"),
    "cogs1_pct_p2":         ("Model", "V52"),
    "cogs1_pct_p3":         ("Model", "W52"),
    "cogs1_pct_p4":         ("Model", "X52"),
    "cogs1_pct_p5":         ("Model", "Y52"),
    "cogs1_pct_p6":         ("Model", "Z52"),

    # COGS 2-9 % of Revenue — zeroed (using single consolidated COGS line)
    "cogs2_pct_p1":         ("Model", "U53"),
    "cogs3_pct_p1":         ("Model", "U54"),
    "cogs4_pct_p1":         ("Model", "U55"),
    "cogs5_pct_p1":         ("Model", "U56"),
    "cogs6_pct_p1":         ("Model", "U57"),
    "cogs7_pct_p1":         ("Model", "U58"),
    "cogs8_pct_p1":         ("Model", "U59"),
    "cogs9_pct_p1":         ("Model", "U60"),

    # Historical COGS (all into COGS 1 row)
    "cogs_hist_y1":         ("Model", "F42"),
    "cogs_hist_y2":         ("Model", "G42"),
    "cogs_hist_y3":         ("Model", "H42"),
    "cogs_hist_y4":         ("Model", "I42"),

    # Historical SG&A (all into SG&A 1 row)
    "sga_hist_y1":          ("Model", "F65"),
    "sga_hist_y2":          ("Model", "G65"),
    "sga_hist_y3":          ("Model", "H65"),
    "sga_hist_y4":          ("Model", "I65"),

    # SG&A 1 growth rates — Base Case (cols U-Z)
    "sga1_growth_p1":       ("Model", "U78"),
    "sga1_growth_p2":       ("Model", "V78"),
    "sga1_growth_p3":       ("Model", "W78"),
    "sga1_growth_p4":       ("Model", "X78"),
    "sga1_growth_p5":       ("Model", "Y78"),
    "sga1_growth_p6":       ("Model", "Z78"),

    # EBITDA Adjustments (rows 98-107) — Adjustment 1 = reconciliation adj
    "adj1_hist_y1":         ("Model", "F98"),
    "adj1_hist_y2":         ("Model", "G98"),
    "adj1_hist_y3":         ("Model", "H98"),
    "adj1_hist_y4":         ("Model", "I98"),
    "adj1_include":         ("Model", "U98"),  # 1=include, 0=exclude

    # Capex % of Revenue — Base Case
    "maint_capex_pct_p1":   ("Model", "U123"),
    "maint_capex_pct_p2":   ("Model", "V123"),
    "maint_capex_pct_p3":   ("Model", "W123"),
    "maint_capex_pct_p4":   ("Model", "X123"),
    "maint_capex_pct_p5":   ("Model", "Y123"),
    "maint_capex_pct_p6":   ("Model", "Z123"),

    "growth_capex_pct_p1":  ("Model", "U124"),
    "growth_capex_pct_p2":  ("Model", "V124"),
    "growth_capex_pct_p3":  ("Model", "W124"),
    "growth_capex_pct_p4":  ("Model", "X124"),
    "growth_capex_pct_p5":  ("Model", "Y124"),
    "growth_capex_pct_p6":  ("Model", "Z124"),

    # ── Debt Schedule ─────────────────────────────────────────────────────
    "tlb_amort_years":      ("Model", "C209"),  # mandatory paydown schedule (years to full repay)
    "tlb_disc_paydown_flag":("Model", "C210"),  # 0=no discretionary, 1=full cash sweep
    "tlb_max_paydown":      ("Model", "E210"),  # max discretionary paydown per year
    "rcf_availability":     ("Model", "C221"),  # RCF facility size
    "seller_note_balance":  ("Model", "C230"),  # seller note initial balance
    "seller_note_paydown":  ("Model", "C231"),  # seller note paydown flag (0/1)
    "seller_note_rate":     ("Model", "J233"),  # seller note interest rate (decimal)
    "cash_interest_rate":   ("Model", "C204"),  # interest earned on cash (decimal)

    # TLB Pricing Grid (3-tier step-up)
    "tl_lev_floor":         ("Model", "B257"),  # leverage floor threshold
    "tl_spread_floor":      ("Model", "C257"),  # SOFR spread at floor
    "tl_undrawn_floor":     ("Model", "D257"),  # undrawn fee at floor
    "tl_lev_mid":           ("Model", "B258"),
    "tl_spread_mid":        ("Model", "C258"),
    "tl_undrawn_mid":       ("Model", "D258"),
    "tl_lev_ceiling":       ("Model", "B259"),
    "tl_spread_ceiling":    ("Model", "C259"),
    "tl_undrawn_ceiling":   ("Model", "D259"),

    # ── Exit & Returns ────────────────────────────────────────────────────
    "exit_multiple_base":   ("Model", "K18"),
    "exit_multiple_upside": ("Model", "L18"),
    "exit_multiple_down":   ("Model", "M18"),
}

# Historical year → Model column mapping (I = entry year, working backwards)
_HIST_COLS = ["F", "G", "H", "I"]   # index 0 = entry_year - 3, index 3 = entry_year
# Projection year → Model column (J = proj yr 1 ... O = proj yr 6)
_PROJ_COLS = ["J", "K", "L", "M", "N", "O"]
# Projection year → Base Case assumption column (U = proj yr 1 ... Z = proj yr 6)
_PROJ_ASSUMP_COLS = ["U", "V", "W", "X", "Y", "Z"]


# ---------------------------------------------------------------------------
# LBO Assumptions dataclass — defaults + full override support
# ---------------------------------------------------------------------------

@dataclass
class LBOAssumptions:
    """
    All LBO model assumptions with sensible defaults.
    Every field can be overridden by the caller.

    Monetary values should be in the same units as the parsed data (e.g. $ millions).
    Rates/percentages are decimals (0.25 = 25%).
    """

    # ── Deal Structure ────────────────────────────────────────────────────
    entry_multiple: float = 8.0           # EV / Entry EBITDA
    tlb_pct_tev: float = 0.45            # Term Loan B as % of TEV
    rcf_availability: float = 50.0       # Revolving Credit Facility size ($)
    rcf_draw_at_close: float = 0.0       # RCF drawn at close ($)
    seller_note_pct_tev: float = 0.0     # Seller note as % of TEV
    rolled_equity: float = 0.0           # Management rollover ($)
    cash_floor: float = 5.0              # Minimum cash balance ($)
    dividend_flag: int = 1               # 1 = pay dividends when cash positive

    # ── Transaction Dates ─────────────────────────────────────────────────
    expected_close: Optional[date] = None    # defaults to Dec 31 of entry year + 1
    scenario: int = 1                        # 1=Base, 2=Mgmt, 3=Downside, 4=S.Q.
    currency_units: str = "millions"

    # ── Revenue Forecast ──────────────────────────────────────────────────
    # If explicit projections provided in parsed data, those take priority.
    # Otherwise the engine uses CAGR method.
    rev_cagr: float = 0.05               # revenue CAGR for projection years
    projection_years: int = 5            # number of years to project (max 6)

    # ── Margin Assumptions ────────────────────────────────────────────────
    # If not set, engine derives from historical parsed data averages.
    gross_margin_target: Optional[float] = None    # e.g. 0.40 = 40%
    ebitda_margin_target: Optional[float] = None   # e.g. 0.17 = 17%
    ebitda_margin_expansion_bps: float = 0.0       # annual bps step-up (50 = +50bps/yr)

    # ── Capex ─────────────────────────────────────────────────────────────
    maint_capex_pct_rev: float = 0.02    # maintenance capex % of revenue
    growth_capex_pct_rev: float = 0.01   # growth capex % of revenue

    # ── Tax & Accounting ──────────────────────────────────────────────────
    tax_rate: float = 0.25
    depreciable_life: int = 7
    earnout_2025: float = 0.0
    earnout_2026: float = 0.0

    # ── Debt Pricing ──────────────────────────────────────────────────────
    tlb_spread: float = 0.05             # SOFR + spread (e.g. 0.05 = 5%)
    tlb_amort_years: int = 7             # years over which TLB amortizes
    tlb_disc_paydown: int = 0            # 1 = sweep excess cash, 0 = no
    tlb_max_paydown: float = 20.0        # max discretionary paydown / year
    rcf_drawn_spread: float = 0.04       # RCF drawn spread
    rcf_undrawn_fee: float = 0.004       # RCF commitment fee
    seller_note_rate: float = 0.10       # seller note PIK/cash rate
    seller_note_paydown: int = 0         # 1 = paydown when cash available
    cash_interest_rate: float = 0.0      # interest earned on cash

    # ── Exit ──────────────────────────────────────────────────────────────
    exit_multiple: float = 8.0           # base case exit EV/EBITDA
    exit_multiple_upside: Optional[float] = None   # defaults to exit_multiple + 1
    exit_multiple_downside: Optional[float] = None # defaults to exit_multiple - 1

    # ── Guardrail Limits ──────────────────────────────────────────────────
    max_leverage_hard: float = 8.0       # hard stop above this total debt/EBITDA
    max_leverage_soft: float = 7.0       # soft warning above this
    min_equity_pct_hard: float = 0.15    # hard stop if equity < this % of TEV
    min_equity_pct_soft: float = 0.25    # soft warning


# ---------------------------------------------------------------------------
# LBO Engine
# ---------------------------------------------------------------------------

class LBOEngineError(Exception):
    """Raised for hard guardrail violations."""


class LBOEngine:
    """
    Generates cell-level Execution Instructions for the LBO Excel model.

    Parameters
    ----------
    parsed_data : dict
        Output of data_parser.parse_document(). Must contain 'metadata',
        'historical', 'projected', and 'warnings' keys.
    assumptions : LBOAssumptions, optional
        Override any default assumption. If None, all defaults apply.
    cell_map_overrides : dict, optional
        Override specific cell mappings: {"entry_tev": ("Output AVP", "I5")}
    """

    def __init__(
        self,
        parsed_data: dict,
        assumptions: Optional[LBOAssumptions] = None,
        cell_map_overrides: Optional[dict] = None,
    ):
        self._raw = parsed_data
        self.assumptions = assumptions or LBOAssumptions()
        self._cell_map = {**CELL_MAP, **(cell_map_overrides or {})}

        self._instructions: list[dict] = []
        self._warnings: list[str] = []
        self._violations: list[str] = []

        # Resolve metadata
        meta = parsed_data.get("metadata", {})
        self.company_name: str = meta.get("company_name") or "Target Company"
        self.currency: str = meta.get("currency") or "USD"
        self.units: str = meta.get("units") or self.assumptions.currency_units

        # Build flat year→period lookup from parsed data
        self._hist: dict[int, dict] = {}
        self._proj: dict[int, dict] = {}
        for p in parsed_data.get("historical", []):
            yr = p.get("year")
            if yr:
                self._hist[int(yr)] = p
        for p in parsed_data.get("projected", []):
            yr = p.get("year")
            if yr:
                self._proj[int(yr)] = p

        # Determine entry year from parsed historical data or assumption
        hist_years = sorted(self._hist.keys())
        self._entry_year: int = hist_years[-1] if hist_years else datetime.now().year - 1
        self._hist_years: list[int] = hist_years  # up to 4 most recent
        self._proj_years: list[int] = sorted(self._proj.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_instructions(self) -> dict:
        """
        Run all LBO logic and return structured Execution Instructions.

        Returns
        -------
        dict with keys:
            instructions      — list of {sheet, cell, value, label} dicts
            assumptions_used  — the resolved assumptions dict
            warnings          — list of soft warning strings
            violations        — list of hard/soft guardrail breach strings
            summary           — high-level deal metrics
        """
        self._instructions = []
        self._warnings = list(self._raw.get("warnings", []))
        self._violations = []

        # Collect warnings from upstream parser
        self._collect_confidence_warnings()

        # Run accounting identity checks (soft warnings)
        self._check_accounting_identities()

        # Resolve all key financial figures from parsed data
        entry_ebitda = self._get_entry_ebitda()
        entry_revenue = self._get_val("revenue", self._entry_year)

        # Compute deal metrics
        tev = round(entry_ebitda * self.assumptions.entry_multiple, 2)
        tlb = round(tev * self.assumptions.tlb_pct_tev, 2)
        seller_note = round(tev * self.assumptions.seller_note_pct_tev, 2)
        total_debt = round(tlb + seller_note + self.assumptions.rcf_draw_at_close, 2)
        equity = round(tev - total_debt + self.assumptions.rolled_equity, 2)

        # ── Hard guardrail: leverage ──────────────────────────────────────
        if entry_ebitda and entry_ebitda > 0:
            leverage = total_debt / entry_ebitda
            if leverage > self.assumptions.max_leverage_hard:
                raise LBOEngineError(
                    f"HARD STOP: Total leverage {leverage:.1f}x exceeds hard ceiling "
                    f"{self.assumptions.max_leverage_hard:.1f}x. "
                    "Reduce debt tranches or increase EBITDA before proceeding."
                )
            if leverage > self.assumptions.max_leverage_soft:
                self._violations.append(
                    f"[SOFT] Leverage {leverage:.1f}x exceeds soft ceiling "
                    f"{self.assumptions.max_leverage_soft:.1f}x."
                )

        # ── Hard guardrail: minimum equity ───────────────────────────────
        equity_pct = equity / tev if tev else 0
        if equity_pct < self.assumptions.min_equity_pct_hard:
            raise LBOEngineError(
                f"HARD STOP: Equity contribution {equity_pct:.1%} is below the hard minimum "
                f"{self.assumptions.min_equity_pct_hard:.1%} of TEV. "
                "Reduce leverage or increase equity."
            )
        if equity_pct < self.assumptions.min_equity_pct_soft:
            self._violations.append(
                f"[SOFT] Equity {equity_pct:.1%} of TEV is below soft minimum "
                f"{self.assumptions.min_equity_pct_soft:.1%}."
            )

        # ── Build instruction sections ────────────────────────────────────
        self._build_general_assumptions()
        self._build_entry_valuation(tev)
        self._build_sources_uses(tev, tlb, seller_note)
        self._build_income_statement_historical()
        self._build_income_statement_projections(entry_revenue, entry_ebitda)
        self._build_debt_schedule(tlb, seller_note)
        self._build_exit_assumptions()

        # Summary metrics for the orchestrator
        proj_ebitda_y5 = self._get_proj_ebitda_y5(entry_ebitda)
        exit_ev = proj_ebitda_y5 * self.assumptions.exit_multiple if proj_ebitda_y5 else None
        summary = {
            "company": self.company_name,
            "entry_year": self._entry_year,
            "entry_ebitda": entry_ebitda,
            "entry_revenue": entry_revenue,
            "tev": tev,
            "entry_multiple": self.assumptions.entry_multiple,
            "total_debt": total_debt,
            "equity": equity,
            "leverage_at_entry": round(total_debt / entry_ebitda, 2) if entry_ebitda else None,
            "equity_pct_tev": round(equity_pct, 4),
            "exit_multiple": self.assumptions.exit_multiple,
            "proj_ebitda_y5": proj_ebitda_y5,
            "implied_exit_ev": exit_ev,
            "instruction_count": len(self._instructions),
        }

        return {
            "instructions": self._instructions,
            "assumptions_used": self.assumptions.__dict__,
            "warnings": self._warnings,
            "violations": self._violations,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_general_assumptions(self) -> None:
        a = self.assumptions
        entry_date = date(self._entry_year, 12, 31)
        close_date = a.expected_close or date(self._entry_year + 1, 12, 31)

        self._w("company_name",    self.company_name,        "Company name")
        self._w("circuit_breaker", 1,                        "Circuit breaker ON")
        self._w("last_fy_close",   entry_date,               "Last historical FY close")
        self._w("expected_close",  close_date,               "Expected transaction close")
        self._w("scenario",        a.scenario,               "Scenario selector (1=Base)")
        self._w("currency_units",  a.currency_units,         "Currency units")
        self._w("cash_floor",      a.cash_floor,             "Minimum cash balance")
        self._w("tax_rate",        a.tax_rate,               "Corporate tax rate")
        self._w("depreciable_life",a.depreciable_life,       "Depreciable life (years)")
        self._w("dividend_flag",   a.dividend_flag,          "Dividend flag")
        self._w("earnout_2025",    a.earnout_2025,           "Earnout 2025 paid 2026")
        self._w("earnout_2026",    a.earnout_2026,           "Earnout 2026 paid 2027")

    def _build_entry_valuation(self, tev: float) -> None:
        entry_gross_debt = self._get_val("total_debt", self._entry_year) or 0.0
        entry_cash = self._get_val("cash", self._entry_year) or 0.0
        self._w("entry_tev",      tev,              f"Entry TEV ({self.company_name})")
        self._w("entry_gross_debt", entry_gross_debt, "Entry gross debt (offer value calc)")
        self._w("entry_cash",     entry_cash,        "Entry cash (offer value calc)")

    def _build_sources_uses(self, tev: float, tlb: float, seller_note: float) -> None:
        a = self.assumptions
        self._w("rolled_equity",      a.rolled_equity,       "Management rollover equity")
        self._w("seller_note_draw",   seller_note,           "Seller note drawn at close")
        self._w("rcf_draw_at_close",  a.rcf_draw_at_close,   "RCF drawn at close")
        self._w("tlb_pct_tev",        a.tlb_pct_tev,         "Term Loan B as % of TEV")

    def _build_income_statement_historical(self) -> None:
        """
        Write historical revenue, COGS, SG&A, and EBITDA adjustments.
        Strategy: consolidate all revenue into Business Line 1; lines 2-6 = 0.
        COGS and SG&A are derived from parsed gross profit and EBITDA margins.
        """
        # The model supports 4 historical columns (F, G, H, I)
        # Map the 4 most recent historical years to those columns
        hist_years = sorted(self._hist_years)[-4:]
        # Pad left with None if fewer than 4 years of history
        padded = [None] * (4 - len(hist_years)) + hist_years

        col_keys = ["y1", "y2", "y3", "y4"]
        for i, yr in enumerate(padded):
            yk = col_keys[i]

            if yr is None:
                # No data for this historical column — zero it out
                self._w(f"rev_hist_bl1_{yk}",  0.0, f"Revenue BL1 (no data)")
                self._w(f"cogs_hist_{yk}",      0.0, f"COGS (no data)")
                self._w(f"sga_hist_{yk}",       0.0, f"SG&A (no data)")
                self._w(f"adj1_hist_{yk}",      0.0, f"EBITDA adj1 (no data)")
                # Zero out business lines 2-6 for this column
                for bl in range(2, 7):
                    self._w(f"rev_hist_bl{bl}_{yk}", 0.0, f"Revenue BL{bl} (consolidated)")
                continue

            rev       = self._get_val("revenue",      yr) or 0.0
            gp        = self._get_val("gross_profit",  yr)
            gm_pct    = self._get_val("gross_margin_pct", yr)
            ebitda    = self._get_val("ebitda",        yr) or 0.0
            adj_ebitda= self._get_val("ebitda",        yr) or 0.0  # use EBITDA as proxy

            # Derive COGS
            if gp is not None:
                cogs = rev - gp
            elif gm_pct is not None:
                cogs = rev * (1 - gm_pct / 100)
            else:
                cogs = rev * 0.60   # fallback: 60% COGS
                self._warnings.append(
                    f"[{yr}] Gross profit not found; defaulting COGS to 60% of revenue."
                )

            # Derive SG&A
            # OI = Revenue - COGS - SG&A → SG&A = Revenue - COGS - EBITDA
            # (assuming no other income adjustment in historical)
            sga = max(rev - cogs - ebitda, 0.0)

            # EBITDA adjustment = reported adj EBITDA - computed EBITDA
            # If the parsed data has distinct ebitda (reported) we can add adjustment
            adj1 = 0.0

            self._w(f"rev_hist_bl1_{yk}",  round(rev, 4),  f"Revenue {yr}")
            self._w(f"cogs_hist_{yk}",     round(cogs, 4), f"COGS {yr}")
            self._w(f"sga_hist_{yk}",      round(sga, 4),  f"SG&A {yr}")
            self._w(f"adj1_hist_{yk}",     round(adj1, 4), f"EBITDA adj1 {yr}")

            # Zero out business lines 2-6
            for bl in range(2, 7):
                self._w(f"rev_hist_bl{bl}_{yk}", 0.0, f"Revenue BL{bl} zeroed (consolidated)")

        # Include Adjustment 1 toggle
        self._w("adj1_include", 1, "Include EBITDA Adjustment 1")

    def _build_income_statement_projections(
        self, entry_revenue: Optional[float], entry_ebitda: Optional[float]
    ) -> None:
        """
        Write projection-year assumption inputs to Base Case columns (U-Z).
        Supports two modes:
          1. Explicit projections from parsed data → use those revenue/EBITDA values
          2. CAGR + margin expansion → derive growth rates and COGS/SG&A percentages
        """
        a = self.assumptions
        n_proj = min(a.projection_years, 6)

        # Determine entry EBITDA margin and gross margin
        entry_gm_pct    = self._get_val("gross_margin_pct", self._entry_year)
        entry_ebitda_pct= (entry_ebitda / entry_revenue * 100
                           if entry_ebitda and entry_revenue else None)

        base_gm_pct   = (entry_gm_pct or
                         (a.gross_margin_target * 100 if a.gross_margin_target else 40.0))
        base_ebm_pct  = (entry_ebitda_pct or
                         (a.ebitda_margin_target * 100 if a.ebitda_margin_target else 20.0))

        col_letters = _PROJ_ASSUMP_COLS[:n_proj]

        for i, col in enumerate(col_letters):
            proj_year = self._entry_year + 1 + i
            col_key = f"p{i+1}"

            # ── Revenue growth ──────────────────────────────────────────
            explicit_rev = self._get_val("revenue", proj_year, source="proj")
            prev_rev     = (self._get_val("revenue", proj_year - 1, source="proj")
                            or entry_revenue)

            if explicit_rev and prev_rev and prev_rev > 0:
                rev_growth = (explicit_rev / prev_rev) - 1
            else:
                rev_growth = a.rev_cagr

            self._w(f"rev_growth_bl1_{col_key}", round(rev_growth, 6),
                    f"Revenue growth BL1 proj yr {i+1} ({proj_year})")

            # ── COGS % of revenue ───────────────────────────────────────
            explicit_gm = self._get_val("gross_margin_pct", proj_year, source="proj")
            if explicit_gm is not None:
                cogs_pct = (100 - explicit_gm) / 100
            else:
                # Optionally apply margin expansion
                # EBITDA margin expansion allocates between COGS and opex;
                # keep COGS flat, let margin expansion flow through SG&A.
                cogs_pct = (100 - base_gm_pct) / 100

            self._w(f"cogs1_pct_{col_key}", round(cogs_pct, 6),
                    f"COGS1 % of rev proj yr {i+1} ({proj_year})")

            # Zero out COGS lines 2-9 for the first projection year only
            # (they default to 0.01 in template — override once)
            if i == 0:
                for j in range(2, 10):
                    cell_key = f"cogs{j}_pct_p1"
                    if cell_key in self._cell_map:
                        sheet, cell = self._cell_map[cell_key]
                        self._instructions.append({
                            "sheet": sheet, "cell": cell, "value": 0.0,
                            "label": f"COGS{j} % zeroed (consolidated into COGS1)"
                        })

            # ── SG&A growth rate ────────────────────────────────────────
            # Target EBITDA margin with annual step-up
            target_ebm = base_ebm_pct + (i * a.ebitda_margin_expansion_bps / 100)
            # target_opex% = (1 - gross_margin%) - target_EBITDA_margin%
            target_opex_pct = (cogs_pct) - (target_ebm / 100)  # will be negative if EBITDA > GP
            # Growth rate for SG&A to achieve target:
            # SG&A_t = SG&A_{t-1} * (1 + g)
            # Since we drive via absolute growth on the template, we use rev_growth as proxy
            sga_growth = rev_growth * 0.5  # SG&A grows at half revenue growth → margin expansion

            self._w(f"sga1_growth_{col_key}", round(sga_growth, 6),
                    f"SG&A1 growth proj yr {i+1} ({proj_year})")

            # ── Capex % of revenue ──────────────────────────────────────
            self._w(f"maint_capex_pct_{col_key}", a.maint_capex_pct_rev,
                    f"Maintenance capex % rev proj yr {i+1}")
            self._w(f"growth_capex_pct_{col_key}", a.growth_capex_pct_rev,
                    f"Growth capex % rev proj yr {i+1}")

    def _build_debt_schedule(self, tlb: float, seller_note: float) -> None:
        a = self.assumptions
        self._w("tlb_amort_years",       a.tlb_amort_years,       "TLB amortization (years)")
        self._w("tlb_disc_paydown_flag", a.tlb_disc_paydown,      "TLB discretionary paydown flag")
        self._w("tlb_max_paydown",       a.tlb_max_paydown,       "TLB max discretionary paydown")
        self._w("rcf_availability",      a.rcf_availability,      "RCF facility size")
        self._w("seller_note_balance",   seller_note,             "Seller note initial balance")
        self._w("seller_note_paydown",   a.seller_note_paydown,   "Seller note paydown flag")
        self._w("seller_note_rate",      a.seller_note_rate,      "Seller note interest rate")
        self._w("cash_interest_rate",    a.cash_interest_rate,    "Interest rate on cash")

        # TLB pricing grid — 3-tier step-up based on leverage
        self._w("tl_lev_floor",     1.0,             "TLB pricing grid: leverage floor")
        self._w("tl_spread_floor",  a.tlb_spread,    "TLB pricing grid: spread at floor")
        self._w("tl_undrawn_floor", a.rcf_undrawn_fee,"TLB undrawn fee at floor")
        self._w("tl_lev_mid",       1.0,             "TLB pricing grid: leverage mid")
        self._w("tl_spread_mid",    a.tlb_spread,    "TLB pricing grid: spread at mid")
        self._w("tl_undrawn_mid",   a.rcf_undrawn_fee,"TLB undrawn fee at mid")
        self._w("tl_lev_ceiling",   2.0,             "TLB pricing grid: leverage ceiling")
        self._w("tl_spread_ceiling",a.tlb_spread,    "TLB pricing grid: spread at ceiling")
        self._w("tl_undrawn_ceiling",a.rcf_undrawn_fee,"TLB undrawn fee at ceiling")

    def _build_exit_assumptions(self) -> None:
        a = self.assumptions
        exit_up   = a.exit_multiple_upside   or (a.exit_multiple + 1.0)
        exit_down = a.exit_multiple_downside or (a.exit_multiple - 1.0)
        self._w("exit_multiple_base",    a.exit_multiple, "Exit multiple (base case)")
        self._w("exit_multiple_upside",  exit_up,         "Exit multiple (upside)")
        self._w("exit_multiple_down",    exit_down,       "Exit multiple (downside)")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _collect_confidence_warnings(self) -> None:
        """Flag any not_found fields in the entry year that will affect model quality."""
        critical_fields = ["revenue", "ebitda", "total_debt", "cash"]
        period = self._hist.get(self._entry_year, {})
        for field_name in critical_fields:
            f = period.get(field_name, {})
            if isinstance(f, dict) and f.get("confidence") == "not_found":
                self._warnings.append(
                    f"[Entry year {self._entry_year}] '{field_name}' not found in parsed data. "
                    "Model will use zero or default — verify before execution."
                )

    def _check_accounting_identities(self) -> None:
        """Soft checks: EBIT = EBITDA - D&A, Net Debt = Debt - Cash."""
        for yr, period in self._hist.items():
            ebitda = self._get_val("ebitda", yr)
            da     = self._get_val("da",     yr)
            ebit   = self._get_val("ebit",   yr)
            debt   = self._get_val("total_debt", yr)
            cash   = self._get_val("cash",   yr)
            net_debt = self._get_val("net_debt", yr)

            if ebitda and da and ebit:
                computed_ebit = ebitda - da
                if abs(computed_ebit - ebit) > 1.0:
                    self._warnings.append(
                        f"[{yr}] Accounting identity: EBITDA ({ebitda}) - D&A ({da}) = "
                        f"{computed_ebit:.1f} ≠ stated EBIT ({ebit:.1f})."
                    )
            if debt is not None and cash is not None and net_debt is not None:
                computed_nd = debt - cash
                if abs(computed_nd - net_debt) > 1.0:
                    self._warnings.append(
                        f"[{yr}] Net Debt mismatch: {debt} - {cash} = {computed_nd:.1f} "
                        f"≠ stated {net_debt:.1f}."
                    )

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def _get_val(
        self,
        field_name: str,
        year: int,
        source: str = "hist",
    ) -> Optional[float]:
        """
        Safely extract a numeric value from parsed historical or projected data.
        Returns None if not found or confidence='not_found'.
        """
        store = self._hist if source == "hist" else self._proj
        period = store.get(year, {})
        field_data = period.get(field_name)
        if field_data is None:
            return None
        if isinstance(field_data, dict):
            if field_data.get("confidence") == "not_found":
                return None
            val = field_data.get("value")
        else:
            val = field_data
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return float(val)

    def _get_entry_ebitda(self) -> float:
        """Return Adj. EBITDA for the entry year. Raises if not found."""
        ebitda = self._get_val("ebitda", self._entry_year)
        if ebitda is None or ebitda <= 0:
            raise LBOEngineError(
                f"Entry year EBITDA for {self._entry_year} is missing or zero in parsed data. "
                "Cannot compute TEV or leverage. Check data_parser output."
            )
        return ebitda

    def _get_proj_ebitda_y5(self, entry_ebitda: float) -> Optional[float]:
        """Estimate Year 5 projected EBITDA for exit valuation summary."""
        # Try from parsed projections first
        yr5 = self._entry_year + 5
        val = self._get_val("ebitda", yr5, source="proj")
        if val:
            return val
        # Fall back to CAGR approximation
        a = self.assumptions
        gm_pct = self._get_val("gross_margin_pct", self._entry_year) or 40.0
        ebitda_pct = self._get_val("ebitda", self._entry_year) or 0.0
        entry_rev = self._get_val("revenue", self._entry_year) or 0.0
        if entry_rev and entry_ebitda:
            base_margin = entry_ebitda / entry_rev
            proj_rev = entry_rev * ((1 + a.rev_cagr) ** 5)
            proj_margin = base_margin + (5 * a.ebitda_margin_expansion_bps / 10000)
            return round(proj_rev * proj_margin, 2)
        return None

    # ------------------------------------------------------------------
    # Instruction writer
    # ------------------------------------------------------------------

    def _w(self, key: str, value: Any, label: str) -> None:
        """Look up cell from map and append an instruction."""
        if key not in self._cell_map:
            self._warnings.append(f"Cell map key '{key}' not found — instruction skipped.")
            return
        sheet, cell = self._cell_map[key]
        self._instructions.append({
            "sheet": sheet,
            "cell": cell,
            "value": value,
            "label": label,
        })
