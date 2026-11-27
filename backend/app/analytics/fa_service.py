from __future__ import annotations

import json
from typing import Any

from app.storage.duckdb_engine import DuckDBEngine

METRIC_LABELS: dict[str, tuple[str, str, str]] = {
    # metric_code -> (statement, display_label, unit_type)
    "revenue": ("IS", "Total Revenue / Protocol Fees", "currency"),
    "gross_profit": ("IS", "Gross Profit", "currency"),
    "ebitda": ("IS", "EBITDA", "currency"),
    "ebit": ("IS", "Operating Income (EBIT)", "currency"),
    "net_income": ("IS", "Net Income", "currency"),
    "eps_diluted": ("IS", "Diluted EPS", "per_share"),
    "total_assets": ("BS", "Total Assets", "currency"),
    "cash_and_equiv": ("BS", "Cash & Equivalents / TVL", "currency"),
    "total_debt": ("BS", "Total Debt", "currency"),
    "total_equity": ("BS", "Shareholders' Equity", "currency"),
    "shares_diluted": ("BS", "Diluted Shares / Supply", "shares"),
    "operating_cf": ("CF", "Operating Cash Flow", "currency"),
    "capex": ("CF", "Capital Expenditure", "currency"),
    "free_cash_flow": ("CF", "Free Cash Flow (FCF)", "currency"),
}


class FaService:
    """FA (Financial Analysis & Valuation) service with standardized IS/BS/CF and DCF engine."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def get_financials(self, instrument_id: str, period: str = "FY") -> dict[str, Any] | None:
        inst_rows = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [instrument_id]
        )
        if not inst_rows:
            return None
        inst = inst_rows[0]
        meta = json.loads(inst["microstructure_meta"]) if isinstance(inst.get("microstructure_meta"), str) else (inst.get("microstructure_meta") or {})

        if period.upper() == "Q":
            where_period = "period_type IN ('Q1','Q2','Q3','Q4')"
        else:
            where_period = "period_type = 'FY'"

        rows = self.db.query_dicts(
            f"""
            SELECT statement_type, period_type, fiscal_year, fiscal_end_date, filing_date,
                   accounting_standard, reporting_currency, metric_code, value, yoy_growth, qoq_growth
            FROM fact_financials
            WHERE instrument_id = ? AND {where_period}
            ORDER BY fiscal_end_date ASC
            """,
            [instrument_id],
        )

        # Latest price for multiples & DCF comparison
        px_rows = self.db.query_dicts(
            "SELECT close FROM fact_ohlcv WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_utc DESC LIMIT 1",
            [instrument_id],
        )
        spot_price = float(px_rows[0]["close"]) if px_rows else 0.0

        # Pivot periods
        period_keys: list[str] = []
        period_seen: set[str] = set()
        grid: dict[str, dict[str, dict[str, Any]]] = {}
        acct_std = rows[0]["accounting_standard"] if rows else "N/A"
        rep_ccy = rows[0]["reporting_currency"] if rows else inst["base_currency"]

        for r in rows:
            pkey = f"FY{r['fiscal_year']}" if r["period_type"] == "FY" else f"{r['period_type']} {r['fiscal_year']}"
            if pkey not in period_seen:
                period_seen.add(pkey)
                period_keys.append(pkey)
            mcode = r["metric_code"]
            grid.setdefault(mcode, {})[pkey] = {
                "value": float(r["value"]),
                "yoy_growth": float(r["yoy_growth"]) if r["yoy_growth"] is not None else None,
                "qoq_growth": float(r["qoq_growth"]) if r["qoq_growth"] is not None else None,
                "filing_date": str(r["filing_date"]),
            }

        statements: dict[str, list[dict[str, Any]]] = {"IS": [], "BS": [], "CF": []}
        for mcode, (stmt, label, unit) in METRIC_LABELS.items():
            if mcode not in grid:
                continue
            statements[stmt].append(
                {
                    "metric_code": mcode,
                    "label": label,
                    "unit": unit,
                    "periods": grid[mcode],
                }
            )

        # Compute valuation multiples from latest FY
        fy_rows = self.db.query_dicts(
            """
            SELECT metric_code, value
            FROM fact_financials
            WHERE instrument_id = ? AND period_type = 'FY'
            QUALIFY ROW_NUMBER() OVER (PARTITION BY metric_code ORDER BY fiscal_end_date DESC) = 1
            """,
            [instrument_id],
        )
        latest_fy = {r["metric_code"]: float(r["value"]) for r in fy_rows}
        shares = float(
            meta.get("shares_outstanding")
            or meta.get("circulating_supply")
            or latest_fy.get("shares_diluted")
            or 1.0
        )
        mcap = spot_price * shares
        debt = latest_fy.get("total_debt", 0.0)
        cash = latest_fy.get("cash_and_equiv", 0.0)
        ev = mcap + debt - cash
        rev = latest_fy.get("revenue", 0.0)
        gp = latest_fy.get("gross_profit", 0.0)
        ebitda = latest_fy.get("ebitda", 0.0)
        ni = latest_fy.get("net_income", 0.0)
        eq = latest_fy.get("total_equity", 0.0)
        fcf = latest_fy.get("free_cash_flow", 0.0)

        multiples = {
            "market_cap": mcap,
            "enterprise_value": ev,
            "pe": round(mcap / ni, 2) if ni > 0 else None,
            "ev_ebitda": round(ev / ebitda, 2) if ebitda > 0 else None,
            "pb": round(mcap / eq, 2) if eq > 0 else None,
            "ps": round(mcap / rev, 2) if rev > 0 else None,
            "fcf_yield_pct": round((fcf / mcap) * 100.0, 2) if mcap > 0 else None,
            "gross_margin_pct": round((gp / rev) * 100.0, 2) if rev > 0 else None,
            "ebitda_margin_pct": round((ebitda / rev) * 100.0, 2) if rev > 0 else None,
            "net_margin_pct": round((ni / rev) * 100.0, 2) if rev > 0 else None,
            "roe_pct": round((ni / eq) * 100.0, 2) if eq > 0 else None,
        }

        # Default DCF baseline parameters
        default_dcf = self.calculate_dcf(
            instrument_id=instrument_id,
            wacc=0.095 if inst["market"] != "CRYPTO" else 0.14,
            terminal_growth=0.03,
            fcf_growth_5y=0.12 if inst["native_symbol"] != "NVDA" else 0.22,
        )

        return {
            "instrument_id": instrument_id,
            "native_symbol": inst["native_symbol"],
            "display_name": inst["display_name"],
            "market": inst["market"],
            "accounting_standard": acct_std,
            "reporting_currency": rep_ccy,
            "period_mode": "Q" if period.upper() == "Q" else "FY",
            "periods": period_keys,
            "statements": statements,
            "multiples": multiples,
            "dcf_baseline": default_dcf,
        }

    def calculate_dcf(
        self,
        instrument_id: str,
        wacc: float = 0.095,
        terminal_growth: float = 0.03,
        fcf_growth_5y: float = 0.12,
        projection_years: int = 5,
    ) -> dict[str, Any]:
        """Intrinsic Value DCF model with 5x5 WACC vs. Terminal Growth sensitivity matrix."""
        if wacc <= terminal_growth + 0.005:
            wacc = terminal_growth + 0.01

        inst_rows = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [instrument_id]
        )
        if not inst_rows:
            raise ValueError(f"Unknown instrument {instrument_id}")
        inst = inst_rows[0]
        meta = json.loads(inst["microstructure_meta"]) if isinstance(inst.get("microstructure_meta"), str) else (inst.get("microstructure_meta") or {})

        px_rows = self.db.query_dicts(
            "SELECT close FROM fact_ohlcv WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_utc DESC LIMIT 1",
            [instrument_id],
        )
        spot_price = float(px_rows[0]["close"]) if px_rows else 0.0

        fy_rows = self.db.query_dicts(
            """
            SELECT metric_code, value
            FROM fact_financials
            WHERE instrument_id = ? AND period_type = 'FY'
            QUALIFY ROW_NUMBER() OVER (PARTITION BY metric_code ORDER BY fiscal_end_date DESC) = 1
            """,
            [instrument_id],
        )
        latest_fy = {r["metric_code"]: float(r["value"]) for r in fy_rows}
        base_fcf = latest_fy.get("free_cash_flow") or latest_fy.get("operating_cf") or 0.0
        cash = latest_fy.get("cash_and_equiv", 0.0)
        debt = latest_fy.get("total_debt", 0.0)
        shares = float(
            meta.get("shares_outstanding")
            or meta.get("circulating_supply")
            or latest_fy.get("shares_diluted")
            or 1.0
        )

        def _implied_px(r_wacc: float, r_tg: float) -> tuple[float, float, float, list[dict[str, float]]]:
            if r_wacc <= r_tg + 0.005:
                return 0.0, 0.0, 0.0, []
            proj: list[dict[str, float]] = []
            pv_sum = 0.0
            curr_fcf = base_fcf
            for yr in range(1, projection_years + 1):
                # Linearly fade growth slightly toward terminal rate over 5y
                yr_g = fcf_growth_5y - (fcf_growth_5y - r_tg) * ((yr - 1) / (projection_years * 1.8))
                curr_fcf = curr_fcf * (1.0 + yr_g)
                disc = (1.0 + r_wacc) ** yr
                pv = curr_fcf / disc
                pv_sum += pv
                proj.append(
                    {
                        "year": yr,
                        "growth_pct": round(yr_g * 100.0, 2),
                        "projected_fcf": round(curr_fcf, 2),
                        "pv_fcf": round(pv, 2),
                    }
                )
            tv = (curr_fcf * (1.0 + r_tg)) / (r_wacc - r_tg)
            pv_tv = tv / ((1.0 + r_wacc) ** projection_years)
            ev = pv_sum + pv_tv
            eq_val = ev + cash - debt
            per_share = eq_val / shares if shares > 0 else 0.0
            return ev, eq_val, per_share, proj

        ev, eq_val, implied_px, projections = _implied_px(wacc, terminal_growth)
        upside_pct = ((implied_px - spot_price) / spot_price * 100.0) if spot_price > 0 else 0.0

        # 5x5 Sensitivity Grid: WACC +/- 1.0%, +/- 0.5% vs Terminal Growth +/- 1.0%, +/- 0.5%
        wacc_axis = [round(max(0.04, wacc + d), 4) for d in (-0.015, -0.0075, 0.0, 0.0075, 0.015)]
        tg_axis = [round(max(0.005, terminal_growth + d), 4) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
        matrix: list[list[float | None]] = []
        for w in wacc_axis:
            row_vals: list[float | None] = []
            for tg in tg_axis:
                if w <= tg + 0.005:
                    row_vals.append(None)
                else:
                    _, _, px_cell, _ = _implied_px(w, tg)
                    row_vals.append(round(px_cell, 2))
            matrix.append(row_vals)

        return {
            "instrument_id": instrument_id,
            "currency": inst["base_currency"],
            "inputs": {
                "wacc": wacc,
                "terminal_growth": terminal_growth,
                "fcf_growth_5y": fcf_growth_5y,
                "base_fcf": base_fcf,
                "cash": cash,
                "total_debt": debt,
                "shares": shares,
            },
            "outputs": {
                "enterprise_value": round(ev, 2),
                "equity_value": round(eq_val, 2),
                "implied_share_price": round(implied_px, 2),
                "current_price": round(spot_price, 2),
                "upside_pct": round(upside_pct, 2),
            },
            "projections": projections,
            "sensitivity": {
                "wacc_axis": [round(w * 100.0, 2) for w in wacc_axis],
                "terminal_growth_axis": [round(tg * 100.0, 2) for tg in tg_axis],
                "implied_prices": matrix,
            },
        }
