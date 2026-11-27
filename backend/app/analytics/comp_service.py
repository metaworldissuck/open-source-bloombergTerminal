from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from app.storage.duckdb_engine import DuckDBEngine


class CompService:
    """COMP (Peer Comparison) service normalizing fundamentals & performance across markets and FX."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def compare(
        self,
        instrument_ids: list[str],
        base_currency: str = "USD",
        lookback_days: int = 180,
    ) -> dict[str, Any]:
        base_ccy = base_currency.upper()
        # Latest FX rates into requested base currency
        fx_rows = self.db.query_dicts(
            """
            SELECT base_ccy, arg_max(rate, ts_utc) AS fx_rate
            FROM fact_fx_rates
            WHERE quote_ccy = ?
            GROUP BY base_ccy
            """,
            [base_ccy],
        )
        fx_map = {r["base_ccy"]: float(r["fx_rate"]) for r in fx_rows}
        fx_map[base_ccy] = 1.0

        peers: list[dict[str, Any]] = []
        indexed_series: dict[str, list[dict[str, Any]]] = {}

        for iid in instrument_ids:
            inst_rows = self.db.query_dicts(
                "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [iid]
            )
            if not inst_rows:
                continue
            inst = inst_rows[0]
            meta = json.loads(inst["microstructure_meta"]) if isinstance(inst.get("microstructure_meta"), str) else (inst.get("microstructure_meta") or {})
            fx_mult = fx_map.get(inst["base_currency"], 1.0)

            bars = self.db.query_dicts(
                """
                SELECT ts_utc, close
                FROM fact_ohlcv
                WHERE instrument_id = ? AND timeframe = '1d'
                ORDER BY ts_utc DESC
                LIMIT ?
                """,
                [iid, lookback_days],
            )
            bars.reverse()
            if len(bars) < 2:
                continue

            closes = np.array([float(b["close"]) * fx_mult for b in bars], dtype=float)
            rets = np.diff(closes) / closes[:-1]
            ann_factor = 365.0 if inst["market"] == "CRYPTO" else 252.0
            ann_vol = float(np.std(rets) * math.sqrt(ann_factor) * 100.0) if len(rets) > 1 else 0.0
            total_ret = float((closes[-1] / closes[0] - 1.0) * 100.0)
            ret_30d = float((closes[-1] / closes[-min(22, len(closes))] - 1.0) * 100.0)

            # Max drawdown over lookback
            running_max = np.maximum.accumulate(closes)
            dd = (closes - running_max) / running_max
            max_dd = float(np.min(dd) * 100.0)

            indexed_series[iid] = [
                {"time": str(b["ts_utc"])[:10], "value": round(float(c / closes[0] * 100.0), 2)}
                for b, c in zip(bars, closes, strict=True)
            ]

            fin_rows = self.db.query_dicts(
                """
                SELECT metric_code, value, yoy_growth
                FROM fact_financials
                WHERE instrument_id = ? AND period_type = 'FY'
                QUALIFY ROW_NUMBER() OVER (PARTITION BY metric_code ORDER BY fiscal_end_date DESC) = 1
                """,
                [iid],
            )
            fin = {r["metric_code"]: float(r["value"]) for r in fin_rows}
            fin_yoy = {r["metric_code"]: r["yoy_growth"] for r in fin_rows}

            shares = float(
                meta.get("shares_outstanding")
                or meta.get("circulating_supply")
                or fin.get("shares_diluted")
                or 0.0
            )
            native_px = float(bars[-1]["close"])
            mcap_base = native_px * shares * fx_mult if shares > 0 else None
            rev_base = fin.get("revenue", 0.0) * fx_mult
            ebitda_base = fin.get("ebitda", 0.0) * fx_mult
            ni_base = fin.get("net_income", 0.0) * fx_mult
            debt_base = fin.get("total_debt", 0.0) * fx_mult
            cash_base = fin.get("cash_and_equiv", 0.0) * fx_mult
            ev_base = (mcap_base + debt_base - cash_base) if mcap_base else None

            peers.append(
                {
                    "instrument_id": iid,
                    "native_symbol": inst["native_symbol"],
                    "display_name": inst["display_name"],
                    "market": inst["market"],
                    "native_currency": inst["base_currency"],
                    "price_native": round(native_px, 2),
                    "price_base": round(native_px * fx_mult, 2),
                    "market_cap_base": mcap_base,
                    "revenue_base": rev_base,
                    "revenue_yoy_pct": round(float(fin_yoy["revenue"]) * 100.0, 2) if fin_yoy.get("revenue") is not None else None,
                    "pe": round(mcap_base / ni_base, 2) if (mcap_base and ni_base > 0) else None,
                    "ev_ebitda": round(ev_base / ebitda_base, 2) if (ev_base and ebitda_base > 0) else None,
                    "net_margin_pct": round((ni_base / rev_base) * 100.0, 2) if rev_base > 0 else None,
                    "return_period_pct": round(total_ret, 2),
                    "return_30d_pct": round(ret_30d, 2),
                    "ann_vol_pct": round(ann_vol, 2),
                    "max_drawdown_pct": round(max_dd, 2),
                }
            )

        return {
            "base_currency": base_ccy,
            "lookback_days": lookback_days,
            "peers": peers,
            "indexed_series": indexed_series,
        }
