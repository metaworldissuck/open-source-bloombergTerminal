from __future__ import annotations

import json
from typing import Any

from app.core.calendars import get_market_sessions
from app.normalization.cn_microstructure import compute_cn_price_limits
from app.storage.duckdb_engine import DuckDBEngine


def _safe_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


class DesService:
    """DES (Security Description & Microstructure) analytical service."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def get_des(self, instrument_id: str) -> dict[str, Any] | None:
        inst_rows = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [instrument_id]
        )
        if not inst_rows:
            return None
        inst = inst_rows[0]
        meta = _safe_json(inst.get("microstructure_meta"))

        # Latest & previous bars + 52W range
        bars = self.db.query_dicts(
            """
            SELECT ts_utc, open, high, low, close, volume, turnover_value, vwap
            FROM fact_ohlcv
            WHERE instrument_id = ? AND timeframe = '1d'
            ORDER BY ts_utc DESC
            LIMIT 260
            """,
            [instrument_id],
        )
        if not bars:
            return None

        latest = bars[0]
        prev = bars[1] if len(bars) > 1 else latest
        px = float(latest["close"])
        prev_px = float(prev["close"])
        chg = px - prev_px
        chg_pct = (chg / prev_px * 100.0) if prev_px else 0.0
        high_52w = max(float(b["high"]) for b in bars)
        low_52w = min(float(b["low"]) for b in bars)
        avg_vol_30d = sum(float(b["volume"]) for b in bars[:30]) / min(30, len(bars))

        # Latest FY financials for headline valuation & capital structure
        fin_rows = self.db.query_dicts(
            """
            SELECT metric_code, value, fiscal_year, reporting_currency, accounting_standard
            FROM fact_financials
            WHERE instrument_id = ? AND period_type = 'FY'
            QUALIFY ROW_NUMBER() OVER (PARTITION BY metric_code ORDER BY fiscal_end_date DESC) = 1
            """,
            [instrument_id],
        )
        fin = {r["metric_code"]: float(r["value"]) for r in fin_rows}
        acct_std = fin_rows[0]["accounting_standard"] if fin_rows else "N/A"
        shares = float(
            meta.get("shares_outstanding")
            or meta.get("circulating_supply")
            or fin.get("shares_diluted")
            or 0.0
        )
        market_cap = px * shares if shares > 0 else None
        total_debt = fin.get("total_debt", 0.0)
        cash = fin.get("cash_and_equiv", 0.0)
        ev = (market_cap + total_debt - cash) if market_cap is not None else None
        net_income = fin.get("net_income")
        ebitda = fin.get("ebitda")
        revenue = fin.get("revenue")
        equity = fin.get("total_equity")

        pe = (market_cap / net_income) if (market_cap and net_income and net_income > 0) else None
        ev_ebitda = (ev / ebitda) if (ev and ebitda and ebitda > 0) else None
        pb = (market_cap / equity) if (market_cap and equity and equity > 0) else None
        ps = (market_cap / revenue) if (market_cap and revenue and revenue > 0) else None

        # Market-specific microstructure payload
        microstructure: dict[str, Any] = {"market": inst["market"]}
        if inst["market"] == "US":
            options = self.db.query_dicts(
                """
                SELECT contract_symbol, expiration_date, strike, option_type, bid, ask,
                       last_price, implied_volatility, open_interest, volume, delta, gamma, theta, vega
                FROM fact_us_options
                WHERE instrument_id = ?
                ORDER BY strike ASC, option_type ASC
                LIMIT 20
                """,
                [instrument_id],
            )
            holders_13f = self.db.query_dicts(
                """
                SELECT institution_name, institution_cik, shares_held, market_value_usd,
                       pct_of_shares_out, qoq_share_change, report_date
                FROM fact_us_13f_holdings
                WHERE instrument_id = ?
                ORDER BY pct_of_shares_out DESC
                LIMIT 8
                """,
                [instrument_id],
            )
            microstructure.update(
                {
                    "cik": meta.get("cik"),
                    "exchange": meta.get("exchange", inst["exchange_mic"]),
                    "supports_extended_hours": bool(meta.get("supports_extended_hours", True)),
                    "pre_market_price": meta.get("pre_market_price", round(px * 1.003, 2)),
                    "post_market_price": meta.get("post_market_price", round(px * 0.999, 2)),
                    "next_earnings_date": meta.get("next_earnings_date"),
                    "options_chain": options,
                    "institutional_13f": holders_13f,
                }
            )
        elif inst["market"] == "CN_ASHARE":
            limit_pct = float(inst.get("price_limit_pct") or 0.10)
            band = compute_cn_price_limits(prev_px, px, limit_pct)
            cn_rows = self.db.query_dicts(
                """
                SELECT trade_date, prev_close, limit_up_price, limit_down_price,
                       hit_limit_up, hit_limit_down, is_st_flagged, turnover_rate_pct,
                       northbound_hold_shares, northbound_hold_pct, northbound_net_flow_cny,
                       margin_buy_balance_cny
                FROM fact_cn_microstructure
                WHERE instrument_id = ?
                ORDER BY trade_date DESC
                LIMIT 20
                """,
                [instrument_id],
            )
            latest_cn = cn_rows[0] if cn_rows else {}
            microstructure.update(
                {
                    "board": meta.get("board", "MAIN"),
                    "yahoo_ticker": meta.get("yahoo_ticker"),
                    "t_plus_1_sell_lock": True,
                    "lot_size": int(inst["lot_size"]),
                    "is_st": bool(meta.get("is_st", False)),
                    "is_northbound_eligible": bool(meta.get("is_northbound_eligible", True)),
                    "limit_pct": limit_pct,
                    "limit_up_price": band.limit_up,
                    "limit_down_price": band.limit_down,
                    "hit_limit_up": band.hit_limit_up,
                    "hit_limit_down": band.hit_limit_down,
                    "pct_from_limit_up": band.pct_from_limit_up,
                    "pct_from_limit_down": band.pct_from_limit_down,
                    "turnover_rate_pct": latest_cn.get("turnover_rate_pct"),
                    "northbound_hold_pct": latest_cn.get("northbound_hold_pct"),
                    "northbound_net_flow_cny": latest_cn.get("northbound_net_flow_cny"),
                    "margin_buy_balance_cny": latest_cn.get("margin_buy_balance_cny"),
                    "northbound_history": [
                        {
                            "date": str(r["trade_date"]),
                            "net_flow_cny": r["northbound_net_flow_cny"],
                            "hold_pct": r["northbound_hold_pct"],
                            "hit_limit_up": r["hit_limit_up"],
                            "hit_limit_down": r["hit_limit_down"],
                        }
                        for r in reversed(cn_rows)
                    ],
                }
            )
        else:
            cr_rows = self.db.query_dicts(
                """
                SELECT ts_utc, venue, funding_rate, annualized_funding_pct, open_interest_usd,
                       mark_price, index_price, perp_basis_bps, cex_volume_24h_usd,
                       dex_volume_24h_usd, tvl_usd, active_addresses_24h
                FROM fact_crypto_metrics
                WHERE instrument_id = ?
                ORDER BY ts_utc DESC
                LIMIT 20
                """,
                [instrument_id],
            )
            latest_cr = cr_rows[0] if cr_rows else {}
            cex_v = float(latest_cr.get("cex_volume_24h_usd") or 0.0)
            dex_v = float(latest_cr.get("dex_volume_24h_usd") or 0.0)
            tot_v = cex_v + dex_v
            microstructure.update(
                {
                    "contract_type": meta.get("contract_type", "SPOT"),
                    "chain": meta.get("chain"),
                    "funding_interval_hours": meta.get("funding_interval_hours", 8),
                    "circulating_supply": meta.get("circulating_supply"),
                    "max_supply": meta.get("max_supply"),
                    "fdv_usd": (px * meta["max_supply"]) if meta.get("max_supply") else market_cap,
                    "funding_rate": latest_cr.get("funding_rate"),
                    "annualized_funding_pct": latest_cr.get("annualized_funding_pct"),
                    "open_interest_usd": latest_cr.get("open_interest_usd"),
                    "mark_price": latest_cr.get("mark_price", px),
                    "index_price": latest_cr.get("index_price", px),
                    "perp_basis_bps": latest_cr.get("perp_basis_bps"),
                    "cex_volume_24h_usd": cex_v,
                    "dex_volume_24h_usd": dex_v,
                    "dex_share_pct": round((dex_v / tot_v) * 100.0, 2) if tot_v > 0 else 0.0,
                    "tvl_usd": latest_cr.get("tvl_usd"),
                    "active_addresses_24h": latest_cr.get("active_addresses_24h"),
                    "funding_history": [
                        {
                            "date": str(r["ts_utc"])[:10],
                            "funding_rate_bps": round(float(r["funding_rate"] or 0.0) * 10000, 3),
                            "open_interest_usd": r["open_interest_usd"],
                        }
                        for r in reversed(cr_rows)
                    ],
                }
            )

        events = self.db.query_dicts(
            """
            SELECT event_id, event_ts_utc, event_type, title, payload_json
            FROM fact_events
            WHERE instrument_id = ?
            ORDER BY event_ts_utc DESC
            LIMIT 6
            """,
            [instrument_id],
        )

        sessions = get_market_sessions()
        return {
            "instrument": {
                "instrument_id": inst["instrument_id"],
                "asset_class": inst["asset_class"],
                "market": inst["market"],
                "exchange_mic": inst["exchange_mic"],
                "native_symbol": inst["native_symbol"],
                "display_name": inst["display_name"],
                "display_name_local": inst["display_name_local"],
                "base_currency": inst["base_currency"],
                "sector": inst["sector"],
                "industry": inst["industry"],
                "settlement_rule": inst["settlement_rule"],
                "lot_size": inst["lot_size"],
                "price_limit_pct": inst["price_limit_pct"],
                "description": inst["description"],
                "session": sessions.get(inst["market"]),
            },
            "quote": {
                "price": round(px, 4 if px < 10 else 2),
                "prev_close": round(prev_px, 4 if prev_px < 10 else 2),
                "change": round(chg, 4 if abs(chg) < 1 else 2),
                "change_pct": round(chg_pct, 2),
                "open": latest["open"],
                "high": latest["high"],
                "low": latest["low"],
                "volume": latest["volume"],
                "turnover_value": latest["turnover_value"],
                "vwap": latest["vwap"],
                "high_52w": high_52w,
                "low_52w": low_52w,
                "avg_volume_30d": round(avg_vol_30d, 2),
                "as_of_utc": str(latest["ts_utc"]),
            },
            "valuation": {
                "accounting_standard": acct_std,
                "currency": inst["base_currency"],
                "market_cap": market_cap,
                "enterprise_value": ev,
                "pe_ratio": round(pe, 2) if pe else None,
                "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda else None,
                "pb_ratio": round(pb, 2) if pb else None,
                "ps_ratio": round(ps, 2) if ps else None,
                "dividend_yield_pct": meta.get("dividend_yield_pct"),
                "beta_5y": meta.get("beta_5y"),
                "shares_outstanding": shares,
                "free_float_pct": meta.get("free_float_pct"),
                "total_debt": total_debt,
                "cash_and_equiv": cash,
                "net_debt": total_debt - cash,
            },
            "microstructure": microstructure,
            "recent_events": [
                {
                    "event_id": e["event_id"],
                    "date": str(e["event_ts_utc"])[:10],
                    "event_type": e["event_type"],
                    "title": e["title"],
                }
                for e in events
            ],
        }
