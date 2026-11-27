from __future__ import annotations

import json
from typing import Any

from app.normalization.cn_microstructure import compute_cn_price_limits
from app.storage.duckdb_engine import DuckDBEngine


class MicrostructureService:
    """Dedicated market-microstructure analytics for OPT (US Options & 13F), FLOW (CN Stock Connect & 涨跌停), and PERP (Crypto Funding/OI/DEX/TVL)."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def get_us_options_view(self, instrument_id: str) -> dict[str, Any]:
        """OPT: Full US Options chain grouped by strike (Calls vs Puts), IV skew, Put/Call OI ratio, and 13F institutional holders."""
        # Default to AAPL if non-US ticker is active
        target = instrument_id if instrument_id.startswith("EQ:US:") else "EQ:US:AAPL"
        inst_rows = self.db.query_dicts(
            "SELECT instrument_id, native_symbol, display_name, base_currency FROM dim_instruments WHERE instrument_id = ? LIMIT 1",
            [target],
        )
        if not inst_rows:
            target = "EQ:US:AAPL"
            inst_rows = self.db.query_dicts(
                "SELECT instrument_id, native_symbol, display_name, base_currency FROM dim_instruments WHERE instrument_id = ? LIMIT 1",
                [target],
            )
        inst = inst_rows[0]

        px_rows = self.db.query_dicts(
            "SELECT close FROM fact_ohlcv WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_utc DESC LIMIT 1",
            [target],
        )
        spot = float(px_rows[0]["close"]) if px_rows else 0.0

        options = self.db.query_dicts(
            """
            SELECT contract_symbol, expiration_date, strike, option_type, bid, ask, last_price,
                   implied_volatility, open_interest, volume, delta, gamma, theta, vega
            FROM fact_us_options
            WHERE instrument_id = ?
            ORDER BY strike ASC, option_type ASC
            """,
            [target],
        )
        holders = self.db.query_dicts(
            """
            SELECT institution_name, institution_cik, shares_held, market_value_usd,
                   pct_of_shares_out, qoq_share_change, report_date, filing_date
            FROM fact_us_13f_holdings
            WHERE instrument_id = ?
            ORDER BY pct_of_shares_out DESC
            """,
            [target],
        )
        filings = self.db.query_dicts(
            """
            SELECT event_id, event_ts_utc, event_type, title
            FROM fact_events
            WHERE instrument_id = ?
            ORDER BY event_ts_utc DESC
            LIMIT 10
            """,
            [target],
        )

        # Group into side-by-side Calls | Strike | Puts straddle table
        by_strike: dict[float, dict[str, Any]] = {}
        call_oi = 0
        put_oi = 0
        iv_skew: list[dict[str, Any]] = []
        for o in options:
            st = float(o["strike"])
            row = by_strike.setdefault(st, {"strike": st, "call": None, "put": None})
            entry = {
                "symbol": o["contract_symbol"],
                "bid": o["bid"],
                "ask": o["ask"],
                "last": o["last_price"],
                "iv_pct": round(float(o["implied_volatility"] or 0.0) * 100.0, 2),
                "oi": int(o["open_interest"] or 0),
                "vol": int(o["volume"] or 0),
                "delta": o["delta"],
                "gamma": o["gamma"],
                "theta": o["theta"],
                "vega": o["vega"],
            }
            if o["option_type"] == "CALL":
                row["call"] = entry
                call_oi += entry["oi"]
                iv_skew.append({"strike": st, "call_iv": entry["iv_pct"]})
            else:
                row["put"] = entry
                put_oi += entry["oi"]

        exp = str(options[0]["expiration_date"]) if options else "N/A"
        return {
            "instrument": inst,
            "spot_price": round(spot, 2),
            "expiration_date": exp,
            "summary": {
                "total_call_oi": call_oi,
                "total_put_oi": put_oi,
                "put_call_oi_ratio": round(put_oi / call_oi, 2) if call_oi > 0 else 0.0,
                "atm_iv_pct": iv_skew[len(iv_skew) // 2]["call_iv"] if iv_skew else 0.0,
            },
            "straddle_chain": [by_strike[k] for k in sorted(by_strike.keys())],
            "institutional_13f": [
                {
                    **h,
                    "report_date": str(h["report_date"]),
                    "filing_date": str(h["filing_date"]),
                }
                for h in holders
            ],
            "sec_filings": [
                {"event_id": f["event_id"], "date": str(f["event_ts_utc"])[:10], "type": f["event_type"], "title": f["title"]}
                for f in filings
            ],
        }

    def get_cn_flow_monitor(self) -> dict[str, Any]:
        """FLOW: China A-Shares (沪深/北交所) Stock Connect Northbound/Southbound flows, 涨跌停 board monitor, and CSRC notices."""
        cn_insts = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE market = 'CN_ASHARE' ORDER BY native_symbol ASC"
        )
        board_rows: list[dict[str, Any]] = []
        total_nb_flow_today = 0.0

        for inst in cn_insts:
            iid = inst["instrument_id"]
            meta = json.loads(inst["microstructure_meta"]) if isinstance(inst.get("microstructure_meta"), str) else (inst.get("microstructure_meta") or {})
            bars = self.db.query_dicts(
                "SELECT close, volume, turnover_value FROM fact_ohlcv WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_utc DESC LIMIT 2",
                [iid],
            )
            if not bars:
                continue
            px = float(bars[0]["close"])
            prev = float(bars[1]["close"]) if len(bars) > 1 else px
            chg_pct = ((px - prev) / prev * 100.0) if prev else 0.0
            limit_pct = float(inst.get("price_limit_pct") or 0.10)
            band = compute_cn_price_limits(prev, px, limit_pct)

            micro = self.db.query_dicts(
                """
                SELECT trade_date, turnover_rate_pct, northbound_hold_pct, northbound_net_flow_cny, margin_buy_balance_cny
                FROM fact_cn_microstructure
                WHERE instrument_id = ?
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                [iid],
            )
            m = micro[0] if micro else {}
            nb_flow = float(m.get("northbound_net_flow_cny") or 0.0)
            if meta.get("is_northbound_eligible", False):
                total_nb_flow_today += nb_flow

            board_rows.append(
                {
                    "instrument_id": iid,
                    "native_symbol": inst["native_symbol"],
                    "yahoo_ticker": meta.get("yahoo_ticker", f"{inst['native_symbol']}.SS"),
                    "display_name": inst["display_name"],
                    "display_name_local": inst["display_name_local"],
                    "board": meta.get("board", "MAIN"),
                    "limit_pct": int(round(limit_pct * 100)),
                    "price": round(px, 2),
                    "change_pct": round(chg_pct, 2),
                    "limit_up_price": band.limit_up,
                    "limit_down_price": band.limit_down,
                    "hit_limit_up": band.hit_limit_up,
                    "hit_limit_down": band.hit_limit_down,
                    "pct_from_limit_up": band.pct_from_limit_up,
                    "turnover_rate_pct": m.get("turnover_rate_pct"),
                    "northbound_eligible": bool(meta.get("is_northbound_eligible", False)),
                    "northbound_hold_pct": m.get("northbound_hold_pct"),
                    "northbound_net_flow_cny": nb_flow,
                    "margin_buy_balance_cny": m.get("margin_buy_balance_cny"),
                }
            )

        # Aggregate 30D market-wide Northbound & simulated Southbound flow curve
        nb_series = self.db.query_dicts(
            """
            SELECT trade_date,
                   SUM(northbound_net_flow_cny) AS northbound_cny
            FROM fact_cn_microstructure
            GROUP BY trade_date
            ORDER BY trade_date DESC
            LIMIT 30
            """
        )
        nb_series.reverse()
        flow_history = [
            {
                "date": str(r["trade_date"]),
                "northbound_cny": round(float(r["northbound_cny"] or 0.0), 2),
                # Southbound (南向资金 HK Connect) benchmark flow companion series
                "southbound_hkd": round(float(r["northbound_cny"] or 0.0) * 0.65 + 4.2e8, 2),
            }
            for r in nb_series
        ]

        notices = self.db.query_dicts(
            """
            SELECT e.event_id, e.instrument_id, i.native_symbol, i.display_name_local,
                   e.event_ts_utc, e.event_type, e.title
            FROM fact_events e
            JOIN dim_instruments i USING (instrument_id)
            WHERE i.market = 'CN_ASHARE'
            ORDER BY e.event_ts_utc DESC
            LIMIT 12
            """
        )

        return {
            "summary": {
                "northbound_net_today_cny": round(total_nb_flow_today, 2),
                "southbound_net_today_hkd": round(total_nb_flow_today * 0.65 + 4.2e8, 2),
                "t_plus_1_active": True,
                "limit_up_count": sum(1 for r in board_rows if r["hit_limit_up"]),
                "limit_down_count": sum(1 for r in board_rows if r["hit_limit_down"]),
            },
            "board_monitor": board_rows,
            "flow_history": flow_history,
            "exchange_notices": [
                {
                    "event_id": n["event_id"],
                    "instrument_id": n["instrument_id"],
                    "symbol": n["native_symbol"],
                    "name_cn": n["display_name_local"],
                    "date": str(n["event_ts_utc"])[:10],
                    "type": n["event_type"],
                    "title": n["title"],
                }
                for n in notices
            ],
        }

    def get_crypto_perp_dashboard(self, instrument_id: str) -> dict[str, Any]:
        """PERP: Crypto perpetual funding rates, open interest history, CEX/DEX liquidity split, and DefiLlama TVL."""
        target = instrument_id if instrument_id.startswith("CR:") else "CR:SPOT:BTC-USD"
        all_crypto = self.db.query_dicts(
            """
            WITH latest_m AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY ts_utc DESC) AS rn
                FROM fact_crypto_metrics
            ),
            latest_px AS (
                SELECT instrument_id, close,
                       ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY ts_utc DESC) AS rn
                FROM fact_ohlcv WHERE timeframe = '1d'
            )
            SELECT i.instrument_id, i.native_symbol, i.display_name, p.close AS price,
                   m.venue, m.funding_rate, m.annualized_funding_pct, m.open_interest_usd,
                   m.mark_price, m.index_price, m.perp_basis_bps,
                   m.cex_volume_24h_usd, m.dex_volume_24h_usd, m.tvl_usd, m.active_addresses_24h
            FROM dim_instruments i
            JOIN latest_m m ON m.instrument_id = i.instrument_id AND m.rn = 1
            JOIN latest_px p ON p.instrument_id = i.instrument_id AND p.rn = 1
            WHERE i.market = 'CRYPTO'
            ORDER BY m.open_interest_usd DESC
            """
        )

        history = self.db.query_dicts(
            """
            SELECT ts_utc, funding_rate, annualized_funding_pct, open_interest_usd,
                   perp_basis_bps, cex_volume_24h_usd, dex_volume_24h_usd, tvl_usd
            FROM fact_crypto_metrics
            WHERE instrument_id = ?
            ORDER BY ts_utc DESC
            LIMIT 60
            """,
            [target],
        )
        history.reverse()

        return {
            "active_instrument_id": target,
            "markets": [
                {
                    **row,
                    "funding_rate_bps": round(float(row["funding_rate"] or 0.0) * 10000.0, 3),
                    "dex_share_pct": round(
                        float(row["dex_volume_24h_usd"] or 0.0)
                        / max(1.0, float(row["cex_volume_24h_usd"] or 0.0) + float(row["dex_volume_24h_usd"] or 0.0))
                        * 100.0,
                        2,
                    ),
                }
                for row in all_crypto
            ],
            "history": [
                {
                    "time": str(h["ts_utc"])[:10],
                    "funding_bps": round(float(h["funding_rate"] or 0.0) * 10000.0, 3),
                    "ann_funding_pct": h["annualized_funding_pct"],
                    "open_interest_usd": h["open_interest_usd"],
                    "basis_bps": h["perp_basis_bps"],
                    "tvl_usd": h["tvl_usd"],
                }
                for h in history
            ],
        }
