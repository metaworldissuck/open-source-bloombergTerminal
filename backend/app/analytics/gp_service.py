from __future__ import annotations

import math
from typing import Any

import numpy as np
import polars as pl

from app.storage.duckdb_engine import DuckDBEngine


class GpService:
    """GP (Graph Price) service: Polars technical indicators, Volume Profile, and Event Overlays."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def get_chart_data(
        self,
        instrument_id: str,
        range_code: str = "1Y",
        timeframe: str = "1d",
    ) -> dict[str, Any] | None:
        inst_rows = self.db.query_dicts(
            "SELECT instrument_id, native_symbol, display_name, display_name_local, market, base_currency, price_limit_pct "
            "FROM dim_instruments WHERE instrument_id = ? LIMIT 1",
            [instrument_id],
        )
        if not inst_rows:
            return None
        inst = inst_rows[0]

        df = self.db.query_polars(
            """
            SELECT ts_utc, open, high, low, close, volume, turnover_value, vwap
            FROM fact_ohlcv
            WHERE instrument_id = ? AND timeframe = '1d'
            ORDER BY ts_utc ASC
            """,
            [instrument_id],
        )
        if df.is_empty():
            return None

        # Resample to weekly if requested
        if timeframe.lower() in ("1w", "1wk"):
            df = (
                df.group_by_dynamic("ts_utc", every="1w")
                .agg(
                    [
                        pl.col("open").first(),
                        pl.col("high").max(),
                        pl.col("low").min(),
                        pl.col("close").last(),
                        pl.col("volume").sum(),
                        pl.col("turnover_value").sum(),
                        pl.col("vwap").mean(),
                    ]
                )
                .sort("ts_utc")
            )

        # Compute technical indicators in Polars over full series before range slicing
        delta = pl.col("close").diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0.0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0)

        df = df.with_columns(
            [
                pl.col("close").rolling_mean(20).alias("sma20"),
                pl.col("close").rolling_mean(50).alias("sma50"),
                pl.col("close").ewm_mean(span=12, adjust=False).alias("ema12"),
                pl.col("close").ewm_mean(span=26, adjust=False).alias("ema26"),
                pl.col("close").rolling_std(20).alias("std20"),
                gain.ewm_mean(alpha=1.0 / 14.0, adjust=False).alias("avg_gain"),
                loss.ewm_mean(alpha=1.0 / 14.0, adjust=False).alias("avg_loss"),
            ]
        ).with_columns(
            [
                (pl.col("sma20") + 2.0 * pl.col("std20")).alias("bb_upper"),
                (pl.col("sma20") - 2.0 * pl.col("std20")).alias("bb_lower"),
                (pl.col("ema12") - pl.col("ema26")).alias("macd"),
                (
                    100.0
                    - (
                        100.0
                        / (
                            1.0
                            + (pl.col("avg_gain") / pl.when(pl.col("avg_loss") == 0).then(1e-9).otherwise(pl.col("avg_loss")))
                        )
                    )
                ).alias("rsi14"),
            ]
        ).with_columns(
            [
                pl.col("macd").ewm_mean(span=9, adjust=False).alias("macd_signal"),
            ]
        ).with_columns(
            [
                (pl.col("macd") - pl.col("macd_signal")).alias("macd_hist"),
            ]
        )

        # Slice to requested lookback window
        range_limits = {"1M": 22, "3M": 66, "6M": 132, "1Y": 260, "ALL": len(df)}
        n_bars = range_limits.get(range_code.upper(), 260)
        sliced = df.tail(n_bars)

        def _opt_round(v: Any, digits: int = 3) -> float | None:
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                return None
            return round(float(v), digits)

        candles: list[dict[str, Any]] = []
        indicators: dict[str, list[dict[str, Any]]] = {
            "sma20": [],
            "sma50": [],
            "ema12": [],
            "bb_upper": [],
            "bb_lower": [],
            "rsi14": [],
            "macd": [],
            "macd_signal": [],
            "macd_hist": [],
        }

        for row in sliced.iter_rows(named=True):
            t_str = row["ts_utc"].strftime("%Y-%m-%d")
            candles.append(
                {
                    "time": t_str,
                    "open": round(float(row["open"]), 4),
                    "high": round(float(row["high"]), 4),
                    "low": round(float(row["low"]), 4),
                    "close": round(float(row["close"]), 4),
                    "volume": round(float(row["volume"]), 2),
                }
            )
            for key in indicators:
                val = _opt_round(row[key], 3)
                if val is not None:
                    indicators[key].append({"time": t_str, "value": val})

        # Compute Volume Profile (Price-by-Volume histogram across 20 buckets)
        closes = sliced["close"].to_numpy()
        vols = sliced["volume"].to_numpy()
        p_min = float(np.min(sliced["low"].to_numpy()))
        p_max = float(np.max(sliced["high"].to_numpy()))
        n_bins = 20
        edges = np.linspace(p_min, p_max, n_bins + 1)
        hist_vols, _ = np.histogram(closes, bins=edges, weights=vols)
        max_bin_vol = float(np.max(hist_vols)) if len(hist_vols) else 1.0
        poc_idx = int(np.argmax(hist_vols)) if len(hist_vols) else 0
        volume_profile = [
            {
                "price_low": round(float(edges[i]), 2),
                "price_high": round(float(edges[i + 1]), 2),
                "price_mid": round(float((edges[i] + edges[i + 1]) / 2.0), 2),
                "volume": round(float(hist_vols[i]), 2),
                "pct_of_max": round(float(hist_vols[i] / max_bin_vol * 100.0), 1) if max_bin_vol > 0 else 0.0,
                "is_poc": i == poc_idx,
            }
            for i in range(n_bins)
        ]

        # Event overlays falling within sliced date range
        min_dt = sliced["ts_utc"].min()
        events_raw = self.db.query_dicts(
            """
            SELECT event_id, event_ts_utc, event_type, title
            FROM fact_events
            WHERE instrument_id = ? AND event_ts_utc >= ?
            ORDER BY event_ts_utc ASC
            """,
            [instrument_id, min_dt],
        )
        # Snap each event date to the nearest trading bar date so Lightweight Charts renders every marker
        bar_dates = [c["time"] for c in candles]
        events: list[dict[str, Any]] = []
        for ev in events_raw:
            raw_date = str(ev["event_ts_utc"])[:10]
            snapped = next((bd for bd in bar_dates if bd >= raw_date), bar_dates[-1] if bar_dates else raw_date)
            events.append(
                {
                    "event_id": ev["event_id"],
                    "time": snapped,
                    "event_type": ev["event_type"],
                    "title": ev["title"],
                }
            )

        # China A-share limit-up/down markers overlay if applicable
        limit_hits: list[dict[str, Any]] = []
        if inst["market"] == "CN_ASHARE":
            hits = self.db.query_dicts(
                """
                SELECT trade_date, hit_limit_up, hit_limit_down, limit_up_price, limit_down_price
                FROM fact_cn_microstructure
                WHERE instrument_id = ? AND (hit_limit_up OR hit_limit_down)
                ORDER BY trade_date ASC
                """,
                [instrument_id],
            )
            for h in hits:
                ds = str(h["trade_date"])
                if bar_dates and ds >= bar_dates[0]:
                    limit_hits.append(
                        {
                            "time": ds,
                            "type": "LIMIT_UP" if h["hit_limit_up"] else "LIMIT_DOWN",
                            "label": "涨停" if h["hit_limit_up"] else "跌停",
                        }
                    )

        return {
            "instrument": inst,
            "range": range_code.upper(),
            "timeframe": timeframe,
            "candles": candles,
            "indicators": indicators,
            "volume_profile": volume_profile,
            "events": events,
            "cn_limit_hits": limit_hits,
        }
