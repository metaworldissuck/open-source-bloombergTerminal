from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.storage.duckdb_engine import DuckDBEngine


@dataclass(frozen=True)
class NormalizedChinaSpec:
    ticker_6digit: str
    exchange_mic: str       # 'XSHG' | 'XSHE' | 'XBSE'
    exchange_code: str      # 'SSE' | 'SZSE' | 'BSE'
    yahoo_suffix: str       # '.SS' | '.SZ' | '.BJ'
    board: str              # 'MAIN' | 'STAR' | 'CHINEXT' | 'BSE'
    price_limit_pct: float  # 0.10 | 0.20 | 0.30 | 0.05 (if ST)
    instrument_id: str      # 'EQ:SSE:600519'


CN_6DIGIT_RE = re.compile(r"^(\d{6})(?:\.(SS|SH|SZ|BJ))?$", re.IGNORECASE)
CRYPTO_PAIR_RE = re.compile(
    r"^([A-Z0-9]{2,10})(?:[-/](USD|USDT|USDC|BTC|ETH)|-(PERP))$", re.IGNORECASE
)
KNOWN_CRYPTO_BASES = {"BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "LINK", "ARB", "OP", "DOGE", "UNI", "AAVE"}


def normalize_china_ashare_ticker(raw: str, is_st: bool = False) -> NormalizedChinaSpec | None:
    """Normalize any 6-digit China A-share ticker into SSE (.SS), SZSE (.SZ), or BSE (.BJ).

    Applies official Chinese exchange prefix rules:
    - 600, 601, 603, 605 -> SSE Main Board (.SS, 10% limit, 5% if ST)
    - 688, 689           -> SSE STAR Market / 科创板 (.SS, 20% limit)
    - 000, 001, 002, 003 -> SZSE Main Board (.SZ, 10% limit, 5% if ST)
    - 300, 301           -> SZSE ChiNext / 创业板 (.SZ, 20% limit)
    - 43, 83, 87, 920    -> Beijing Stock Exchange / 北交所 (.BJ, 30% limit)
    """
    m = CN_6DIGIT_RE.match(raw.strip())
    if not m:
        return None
    code = m.group(1)

    if code.startswith(("688", "689")):
        exchange_mic, exchange_code, suffix, board, limit_pct = "XSHG", "SSE", ".SS", "STAR", 0.20
    elif code.startswith(("600", "601", "603", "605")):
        exchange_mic, exchange_code, suffix, board, limit_pct = (
            "XSHG",
            "SSE",
            ".SS",
            "MAIN",
            0.05 if is_st else 0.10,
        )
    elif code.startswith(("300", "301")):
        exchange_mic, exchange_code, suffix, board, limit_pct = "XSHE", "SZSE", ".SZ", "CHINEXT", 0.20
    elif code.startswith(("000", "001", "002", "003")):
        exchange_mic, exchange_code, suffix, board, limit_pct = (
            "XSHE",
            "SZSE",
            ".SZ",
            "MAIN",
            0.05 if is_st else 0.10,
        )
    elif code.startswith(("43", "83", "87", "920")):
        exchange_mic, exchange_code, suffix, board, limit_pct = "XBSE", "BSE", ".BJ", "BSE", 0.30
    else:
        return None

    return NormalizedChinaSpec(
        ticker_6digit=code,
        exchange_mic=exchange_mic,
        exchange_code=exchange_code,
        yahoo_suffix=suffix,
        board=board,
        price_limit_pct=limit_pct,
        instrument_id=f"EQ:{exchange_code}:{code}",
    )


class SecurityMaster:
    """Canonical instrument resolver across US Equities, China A-Shares, and Crypto."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def resolve(
        self,
        raw_symbol: str,
        market_hint: str | None = None,
        asset_hint: str | None = None,
    ) -> dict[str, Any] | None:
        sym = raw_symbol.strip().upper()
        if not sym:
            return None

        # 1. Direct canonical instrument_id match
        direct = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE UPPER(instrument_id) = ? LIMIT 1", [sym]
        )
        if direct:
            return direct[0]

        # 2. Alias lookup (Bloomberg, Yahoo .SS/.SZ/.BJ, CIK, CoinGecko, etc.)
        alias_candidates = [sym]
        if market_hint:
            alias_candidates.append(f"{sym} {market_hint.upper()}")
        for cand in alias_candidates:
            rows = self.db.query_dicts(
                """
                SELECT i.*
                FROM dim_instrument_aliases a
                JOIN dim_instruments i ON a.instrument_id = i.instrument_id
                WHERE UPPER(a.alias_value) = ?
                LIMIT 1
                """,
                [cand],
            )
            if rows:
                return rows[0]

        # 3. Rule-based China A-share normalization
        cn_spec = normalize_china_ashare_ticker(sym)
        if cn_spec is not None:
            rows = self.db.query_dicts(
                "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1",
                [cn_spec.instrument_id],
            )
            if rows:
                return rows[0]
            # Dynamic synthetic descriptor for unknown 6-digit A-share tickers
            return {
                "instrument_id": cn_spec.instrument_id,
                "asset_class": "EQUITY",
                "market": "CN_ASHARE",
                "exchange_mic": cn_spec.exchange_mic,
                "native_symbol": cn_spec.ticker_6digit,
                "display_name": f"{cn_spec.ticker_6digit}{cn_spec.yahoo_suffix}",
                "display_name_local": cn_spec.ticker_6digit,
                "base_currency": "CNY",
                "settlement_rule": "T+1_CN_STRICT",
                "lot_size": 100.0,
                "price_limit_pct": cn_spec.price_limit_pct,
                "trading_calendar_id": cn_spec.exchange_mic,
            }

        # 4. Rule-based Crypto pair normalization
        cm = CRYPTO_PAIR_RE.match(sym)
        if cm or (asset_hint == "CRYPTO") or (sym in KNOWN_CRYPTO_BASES and market_hint is None):
            if cm:
                base = cm.group(1).upper()
                quote = (cm.group(2) or "USDT").upper()
                is_perp = cm.group(3) is not None
                target_id = (
                    f"CR:PERP:BINANCE:{base}-USDT" if is_perp else f"CR:SPOT:{base}-{quote}"
                )
            else:
                base = sym.split("-")[0]
                target_id = f"CR:SPOT:{base}-USD"
            rows = self.db.query_dicts(
                "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [target_id]
            )
            if rows:
                return rows[0]
            # Fallback match on native_symbol prefix for crypto
            rows = self.db.query_dicts(
                "SELECT * FROM dim_instruments WHERE asset_class = 'CRYPTO' AND UPPER(native_symbol) LIKE ? LIMIT 1",
                [f"{sym.split('-')[0]}%"],
            )
            if rows:
                return rows[0]

        # 5. Native symbol match filtered by optional market/asset hint
        sql = "SELECT * FROM dim_instruments WHERE UPPER(native_symbol) = ?"
        params: list[Any] = [sym]
        if market_hint:
            mh = market_hint.upper()
            if mh in ("CH", "CN", "SS", "SZ", "BJ"):
                sql += " AND market = 'CN_ASHARE'"
            elif mh == "US":
                sql += " AND market = 'US'"
        if asset_hint:
            sql += " AND asset_class = ?"
            params.append(asset_hint.upper())
        sql += " LIMIT 1"
        rows = self.db.query_dicts(sql, params)
        if rows:
            return rows[0]

        # 6. Dynamic US Equity fallback if explicitly hinted as US or Equity
        if market_hint and market_hint.upper() == "US" and re.match(r"^[A-Z]{1,5}$", sym):
            return {
                "instrument_id": f"EQ:US:{sym}",
                "asset_class": "EQUITY",
                "market": "US",
                "exchange_mic": "XNAS",
                "native_symbol": sym,
                "display_name": sym,
                "display_name_local": None,
                "base_currency": "USD",
                "settlement_rule": "T+1_US",
                "lot_size": 1.0,
                "price_limit_pct": None,
                "trading_calendar_id": "XNYS",
            }

        return None

    def search(self, query: str, limit: int = 12) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return self.db.query_dicts(
                "SELECT instrument_id, asset_class, market, native_symbol, display_name, display_name_local, base_currency "
                "FROM dim_instruments ORDER BY market, native_symbol LIMIT ?",
                [limit],
            )
        like_pat = f"%{q.upper()}%"
        return self.db.query_dicts(
            """
            SELECT DISTINCT i.instrument_id, i.asset_class, i.market, i.native_symbol,
                            i.display_name, i.display_name_local, i.base_currency
            FROM dim_instruments i
            LEFT JOIN dim_instrument_aliases a ON a.instrument_id = i.instrument_id
            WHERE UPPER(i.native_symbol) LIKE ?
               OR UPPER(i.instrument_id) LIKE ?
               OR UPPER(i.display_name) LIKE ?
               OR COALESCE(i.display_name_local, '') LIKE ?
               OR UPPER(COALESCE(a.alias_value, '')) LIKE ?
            ORDER BY
                CASE WHEN UPPER(i.native_symbol) = ? THEN 0
                     WHEN UPPER(i.native_symbol) LIKE ? THEN 1
                     ELSE 2 END,
                i.market, i.native_symbol
            LIMIT ?
            """,
            [like_pat, like_pat, like_pat, f"%{q}%", like_pat, q.upper(), f"{q.upper()}%", limit],
        )
