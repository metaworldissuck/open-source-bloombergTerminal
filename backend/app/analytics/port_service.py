from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime
from typing import Any

import numpy as np

from app.normalization.cn_microstructure import compute_settlement_date
from app.storage.duckdb_engine import DuckDBEngine


class PortService:
    """PORT (Multi-Currency Portfolio & Quantitative Risk Management) service."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def add_transaction(
        self,
        portfolio_id: str,
        instrument_id: str,
        side: str,
        quantity: float,
        price: float,
        trade_date: date | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        inst_rows = self.db.query_dicts(
            "SELECT base_currency, settlement_rule FROM dim_instruments WHERE instrument_id = ? LIMIT 1",
            [instrument_id],
        )
        if not inst_rows:
            raise ValueError(f"Unknown instrument_id: {instrument_id}")
        inst = inst_rows[0]
        td = trade_date or datetime.now(UTC).date()
        settle_dt = compute_settlement_date(td, inst["settlement_rule"])
        ccy = inst["base_currency"]

        fx_rows = self.db.query_dicts(
            "SELECT arg_max(rate, ts_utc) AS fx FROM fact_fx_rates WHERE base_ccy = ? AND quote_ccy = 'USD'",
            [ccy],
        )
        fx_to_usd = float(fx_rows[0]["fx"]) if fx_rows and fx_rows[0]["fx"] else 1.0
        tx_id = f"tx-{uuid.uuid4().hex[:10]}"
        ts = datetime(td.year, td.month, td.day, 12, 0, tzinfo=UTC)

        self.db.execute(
            "INSERT INTO fact_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                tx_id,
                portfolio_id,
                instrument_id,
                ts,
                settle_dt,
                side.upper(),
                float(quantity),
                float(price),
                ccy,
                fx_to_usd,
                round(float(quantity) * float(price) * 0.0005, 2),
                notes,
            ],
        )
        return {"tx_id": tx_id, "settlement_date": str(settle_dt), "currency": ccy}

    def get_portfolio_analytics(
        self, portfolio_id: str = "PORT_MAIN", base_currency: str = "USD"
    ) -> dict[str, Any]:
        base_ccy = base_currency.upper()
        p_rows = self.db.query_dicts(
            "SELECT * FROM dim_portfolios WHERE portfolio_id = ? LIMIT 1", [portfolio_id]
        )
        portfolio = p_rows[0] if p_rows else {
            "portfolio_id": portfolio_id,
            "name": "Global Multi-Asset Portfolio",
            "base_currency": base_ccy,
            "benchmark_instrument_id": "EQ:US:SPY",
        }

        query_quote = "USD" if base_ccy == "USDT" else base_ccy
        fx_rows = self.db.query_dicts(
            "SELECT base_ccy, arg_max(rate, ts_utc) AS fx_rate FROM fact_fx_rates WHERE quote_ccy = ? GROUP BY base_ccy",
            [query_quote],
        )
        fx_to_base = {r["base_ccy"]: float(r["fx_rate"]) for r in fx_rows}
        fx_to_base[base_ccy] = 1.0
        if base_ccy == "USDT":
            fx_to_base["USD"] = 1.0 / fx_to_base.get("USDT", 1.0)
        usd_to_base = fx_to_base.get("USD", 1.0)

        txs = self.db.query_dicts(
            """
            SELECT t.*, i.native_symbol, i.display_name, i.market, i.settlement_rule, i.base_currency AS inst_ccy
            FROM fact_transactions t
            JOIN dim_instruments i ON t.instrument_id = i.instrument_id
            WHERE t.portfolio_id = ?
            ORDER BY t.trade_ts_utc ASC
            """,
            [portfolio_id],
        )

        today = datetime.now(UTC).date()
        # Aggregate positions, realized P&L (average cost), and T+1 sellable quantities
        pos_map: dict[str, dict[str, Any]] = {}
        realized_pnl_base = 0.0

        for tx in txs:
            iid = tx["instrument_id"]
            side = tx["side"].upper()
            qty = float(tx["quantity"])
            px = float(tx["price"])
            ccy = tx["trade_currency"]
            # Convert stored fx_to_usd into requested base_currency at trade time
            fx_trade_to_base = float(tx["fx_to_base_at_trade"]) * usd_to_base
            settle_dt = tx["settlement_date"]
            if isinstance(settle_dt, datetime):
                settle_dt = settle_dt.date()

            p = pos_map.setdefault(
                iid,
                {
                    "instrument_id": iid,
                    "native_symbol": tx["native_symbol"],
                    "display_name": tx["display_name"],
                    "market": tx["market"],
                    "settlement_rule": tx["settlement_rule"],
                    "currency": ccy,
                    "quantity": 0.0,
                    "sellable_qty": 0.0,
                    "t1_locked_qty": 0.0,
                    "cost_native": 0.0,
                    "cost_base": 0.0,
                    "realized_pnl_base": 0.0,
                },
            )
            if side == "BUY":
                p["quantity"] += qty
                p["cost_native"] += qty * px
                p["cost_base"] += qty * px * fx_trade_to_base
                if tx["settlement_rule"] == "T+1_CN_STRICT" and settle_dt > today:
                    p["t1_locked_qty"] += qty
                else:
                    p["sellable_qty"] += qty
            elif side == "SELL" and p["quantity"] > 0:
                avg_cost_native = p["cost_native"] / p["quantity"]
                avg_cost_base = p["cost_base"] / p["quantity"]
                sold = min(qty, p["quantity"])
                rpnl = sold * (px * fx_trade_to_base - avg_cost_base)
                p["realized_pnl_base"] += rpnl
                realized_pnl_base += rpnl
                p["quantity"] -= sold
                p["sellable_qty"] = max(0.0, p["sellable_qty"] - sold)
                p["cost_native"] -= sold * avg_cost_native
                p["cost_base"] -= sold * avg_cost_base

        # Mark to market using latest prices & FX
        holdings: list[dict[str, Any]] = []
        total_mv_base = 0.0
        total_cost_base = 0.0
        total_unrealized_base = 0.0
        currency_exposure: dict[str, float] = {}
        market_exposure: dict[str, float] = {}

        for iid, p in pos_map.items():
            if p["quantity"] <= 1e-8:
                continue
            px_rows = self.db.query_dicts(
                "SELECT close FROM fact_ohlcv WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_utc DESC LIMIT 1",
                [iid],
            )
            last_px = float(px_rows[0]["close"]) if px_rows else 0.0
            curr_fx = fx_to_base.get(p["currency"], 1.0)
            avg_cost_native = p["cost_native"] / p["quantity"]
            mv_native = p["quantity"] * last_px
            mv_base = mv_native * curr_fx
            unrealized_base = mv_base - p["cost_base"]
            # Decompose asset return vs FX return
            asset_pnl_base = (mv_native - p["cost_native"]) * curr_fx
            fx_pnl_base = unrealized_base - asset_pnl_base

            total_mv_base += mv_base
            total_cost_base += p["cost_base"]
            total_unrealized_base += unrealized_base
            currency_exposure[p["currency"]] = currency_exposure.get(p["currency"], 0.0) + mv_base
            market_exposure[p["market"]] = market_exposure.get(p["market"], 0.0) + mv_base

            holdings.append(
                {
                    "instrument_id": iid,
                    "native_symbol": p["native_symbol"],
                    "display_name": p["display_name"],
                    "market": p["market"],
                    "currency": p["currency"],
                    "settlement_rule": p["settlement_rule"],
                    "quantity": round(p["quantity"], 4),
                    "sellable_qty": round(p["sellable_qty"], 4),
                    "t1_locked_qty": round(p["t1_locked_qty"], 4),
                    "avg_cost_native": round(avg_cost_native, 2),
                    "last_price_native": round(last_px, 2),
                    "market_value_native": round(mv_native, 2),
                    "market_value_base": round(mv_base, 2),
                    "cost_basis_base": round(p["cost_base"], 2),
                    "unrealized_pnl_base": round(unrealized_base, 2),
                    "unrealized_pnl_pct": round((unrealized_base / p["cost_base"] * 100.0), 2) if p["cost_base"] > 0 else 0.0,
                    "asset_pnl_base": round(asset_pnl_base, 2),
                    "fx_pnl_base": round(fx_pnl_base, 2),
                    "weight_pct": 0.0,
                }
            )

        for h in holdings:
            h["weight_pct"] = round((h["market_value_base"] / total_mv_base * 100.0), 2) if total_mv_base > 0 else 0.0
        holdings.sort(key=lambda x: x["market_value_base"], reverse=True)

        # Quantitative Risk Engine: Historical portfolio return series, Sharpe, Sortino, MaxDD, Beta, VaR, Correlation Matrix
        risk_metrics, equity_curve, corr_matrix = self._compute_risk_engine(
            holdings=holdings,
            benchmark_id=portfolio.get("benchmark_instrument_id") or "EQ:US:SPY",
            fx_to_base=fx_to_base,
            total_mv_base=total_mv_base,
        )

        return {
            "portfolio": {
                "portfolio_id": portfolio["portfolio_id"],
                "name": portfolio["name"],
                "base_currency": base_ccy,
                "benchmark_instrument_id": portfolio.get("benchmark_instrument_id") or "EQ:US:SPY",
            },
            "summary": {
                "total_market_value": round(total_mv_base, 2),
                "total_cost_basis": round(total_cost_base, 2),
                "unrealized_pnl": round(total_unrealized_base, 2),
                "unrealized_pnl_pct": round((total_unrealized_base / total_cost_base * 100.0), 2) if total_cost_base > 0 else 0.0,
                "realized_pnl": round(realized_pnl_base, 2),
                "currency_exposure": [
                    {
                        "currency": ccy,
                        "value_base": round(val, 2),
                        "weight_pct": round((val / total_mv_base * 100.0), 2) if total_mv_base > 0 else 0.0,
                    }
                    for ccy, val in sorted(currency_exposure.items(), key=lambda kv: kv[1], reverse=True)
                ],
                "market_exposure": [
                    {
                        "market": mkt,
                        "value_base": round(val, 2),
                        "weight_pct": round((val / total_mv_base * 100.0), 2) if total_mv_base > 0 else 0.0,
                    }
                    for mkt, val in sorted(market_exposure.items(), key=lambda kv: kv[1], reverse=True)
                ],
            },
            "holdings": holdings,
            "risk": risk_metrics,
            "equity_curve": equity_curve,
            "correlation_matrix": corr_matrix,
        }

    def _compute_risk_engine(
        self,
        holdings: list[dict[str, Any]],
        benchmark_id: str,
        fx_to_base: dict[str, float],
        total_mv_base: float,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        if not holdings or total_mv_base <= 0:
            return {}, [], {"symbols": [], "matrix": []}

        iids = [h["instrument_id"] for h in holdings]
        all_ids = list(dict.fromkeys([*iids, benchmark_id]))
        placeholders = ",".join(["?"] * len(all_ids))
        rows = self.db.query_dicts(
            f"""
            SELECT instrument_id, ts_utc::DATE AS dt, close
            FROM fact_ohlcv
            WHERE instrument_id IN ({placeholders}) AND timeframe = '1d'
            ORDER BY dt ASC
            """,
            all_ids,
        )

        # Align daily closes on common trading dates (forward-filling market holidays/weekends)
        date_set = sorted({str(r["dt"]) for r in rows})
        price_lookup: dict[str, dict[str, float]] = {iid: {} for iid in all_ids}
        for r in rows:
            price_lookup[r["instrument_id"]][str(r["dt"])] = float(r["close"])

        # Keep last 252 aligned dates
        dates = date_set[-252:]
        series_map: dict[str, np.ndarray] = {}
        for iid in all_ids:
            arr: list[float] = []
            last_v: float | None = None
            for d in dates:
                v = price_lookup[iid].get(d)
                if v is not None:
                    last_v = v
                if last_v is not None:
                    arr.append(last_v)
                else:
                    arr.append(np.nan)
            np_arr = np.array(arr, dtype=float)
            # Backfill leading NaNs with first valid observation
            valid_idx = np.where(~np.isnan(np_arr))[0]
            if len(valid_idx) > 0:
                np_arr[: valid_idx[0]] = np_arr[valid_idx[0]]
            series_map[iid] = np_arr

        # Compute daily returns matrix for holdings
        weights = np.array([h["weight_pct"] / 100.0 for h in holdings], dtype=float)
        if np.sum(weights) > 0:
            weights = weights / np.sum(weights)

        ret_cols: list[np.ndarray] = []
        for h in holdings:
            px = series_map[h["instrument_id"]]
            r = np.diff(px) / np.where(px[:-1] == 0, 1.0, px[:-1])
            ret_cols.append(r)

        ret_mat = np.vstack(ret_cols)  # shape (N_assets, T-1)
        port_rets = np.dot(weights, ret_mat)

        # Benchmark returns
        bm_px = series_map[benchmark_id]
        bm_rets = np.diff(bm_px) / np.where(bm_px[:-1] == 0, 1.0, bm_px[:-1])

        rf_daily = 0.042 / 252.0
        mean_daily = float(np.mean(port_rets))
        std_daily = float(np.std(port_rets, ddof=1)) if len(port_rets) > 1 else 0.0
        downside = port_rets[port_rets < rf_daily] - rf_daily
        downside_std = float(np.sqrt(np.mean(downside**2))) if len(downside) > 0 else 1e-9

        ann_return = ((1.0 + mean_daily) ** 252 - 1.0) * 100.0
        ann_vol = std_daily * math.sqrt(252.0) * 100.0
        sharpe = ((mean_daily - rf_daily) / std_daily * math.sqrt(252.0)) if std_daily > 1e-9 else 0.0
        sortino = ((mean_daily - rf_daily) / downside_std * math.sqrt(252.0)) if downside_std > 1e-9 else 0.0

        # Cumulative portfolio curve & Max Drawdown
        cum_curve = np.cumprod(1.0 + port_rets)
        running_peak = np.maximum.accumulate(cum_curve)
        drawdowns = (cum_curve - running_peak) / running_peak
        max_dd_pct = float(np.min(drawdowns) * 100.0) if len(drawdowns) else 0.0

        # Beta vs Benchmark
        bm_var = float(np.var(bm_rets, ddof=1)) if len(bm_rets) > 1 else 0.0
        cov_p_bm = float(np.cov(port_rets, bm_rets)[0, 1]) if len(port_rets) > 1 else 0.0
        beta = (cov_p_bm / bm_var) if bm_var > 1e-12 else 1.0

        # Value at Risk (1-day 95% and 99%, both Historical and Parametric)
        hist_var_95_pct = float(-np.percentile(port_rets, 5) * 100.0)
        hist_var_99_pct = float(-np.percentile(port_rets, 1) * 100.0)
        param_var_95_pct = float(-(mean_daily - 1.6449 * std_daily) * 100.0)
        param_var_99_pct = float(-(mean_daily - 2.3263 * std_daily) * 100.0)

        risk_metrics = {
            "annualized_return_pct": round(ann_return, 2),
            "annualized_volatility_pct": round(ann_vol, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "beta_vs_benchmark": round(beta, 2),
            "var_95_1d_pct": round(hist_var_95_pct, 2),
            "var_95_1d_value": round(total_mv_base * hist_var_95_pct / 100.0, 2),
            "var_99_1d_pct": round(hist_var_99_pct, 2),
            "var_99_1d_value": round(total_mv_base * hist_var_99_pct / 100.0, 2),
            "parametric_var_95_pct": round(param_var_95_pct, 2),
            "parametric_var_99_pct": round(param_var_99_pct, 2),
            "risk_free_rate_pct": 4.2,
        }

        equity_curve = [
            {
                "time": dates[i + 1],
                "indexed_value": round(float(cum_curve[i] * 100.0), 2),
                "drawdown_pct": round(float(drawdowns[i] * 100.0), 2),
            }
            for i in range(len(cum_curve))
        ]

        # Pairwise Correlation Matrix
        if len(holdings) >= 2:
            corr = np.corrcoef(ret_mat)
            corr_rows = [[round(float(val), 2) if not math.isnan(val) else 0.0 for val in row] for row in corr]
        else:
            corr_rows = [[1.0]]

        corr_matrix = {
            "symbols": [h["native_symbol"] for h in holdings],
            "instrument_ids": [h["instrument_id"] for h in holdings],
            "matrix": corr_rows,
        }
        return risk_metrics, equity_curve, corr_matrix
