from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.base import MarketDataAdapter
from app.config import settings


class USYFinanceAdapter(MarketDataAdapter):
    """Live US Equities adapter using yfinance + SEC EDGAR CompanyFacts XBRL."""

    name = "us_yfinance_edgar"
    supported_markets = ("US",)

    async def fetch_ohlcv(
        self, instrument: dict[str, Any], timeframe: str = "1d", limit: int = 250
    ) -> list[dict[str, Any]]:
        if not settings.enable_live_adapters or not self.breaker.allow_request():
            return []
        try:
            import yfinance as yf  # type: ignore[import-not-found]
        except ImportError:
            return []

        symbol = instrument["native_symbol"]
        interval_map = {"1m": "1m", "5m": "5m", "1h": "60m", "1d": "1d", "1w": "1wk"}
        yf_interval = interval_map.get(timeframe, "1d")
        period = "2y" if timeframe in ("1d", "1w") else "5d"

        def _dl() -> list[dict[str, Any]]:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=yf_interval, auto_adjust=False)
            if df is None or df.empty:
                return []
            out: list[dict[str, Any]] = []
            for ts, row in df.tail(limit).iterrows():
                dt = ts.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                else:
                    dt = dt.astimezone(UTC)
                out.append(
                    {
                        "instrument_id": instrument["instrument_id"],
                        "timeframe": timeframe,
                        "ts_utc": dt,
                        "session_type": "REGULAR",
                        "currency": "USD",
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "adj_close": float(row.get("Adj Close", row["Close"])),
                        "volume": float(row["Volume"]),
                        "turnover_value": float(row["Close"] * row["Volume"]),
                        "vwap": float((row["High"] + row["Low"] + row["Close"]) / 3.0),
                        "adj_factor": 1.0,
                        "source_adapter": self.name,
                    }
                )
            return out

        try:
            rows = await asyncio.wait_for(asyncio.to_thread(_dl), timeout=settings.adapter_timeout_sec)
            self.breaker.record_success()
            return rows
        except Exception:
            self.breaker.record_failure()
            return []

    async def fetch_quote(self, instrument: dict[str, Any]) -> dict[str, Any] | None:
        return None

    async def fetch_sec_edgar_facts(self, cik: str) -> dict[str, Any] | None:
        """Fetch raw SEC EDGAR XBRL CompanyFacts JSON for a 10-digit zero-padded CIK."""
        if not settings.enable_live_adapters or not self.breaker.allow_request():
            return None
        padded = cik.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"
        headers = {"User-Agent": settings.sec_edgar_user_agent, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=settings.adapter_timeout_sec) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                self.breaker.record_success()
                return resp.json()
        except Exception:
            self.breaker.record_failure()
            return None


class ChinaAkShareAdapter(MarketDataAdapter):
    """Live China A-Shares adapter via AkShare (SSE/SZSE/BSE OHLCV, Northbound, CAS financials)."""

    name = "cn_akshare"
    supported_markets = ("CN_ASHARE",)

    async def fetch_ohlcv(
        self, instrument: dict[str, Any], timeframe: str = "1d", limit: int = 250
    ) -> list[dict[str, Any]]:
        if not settings.enable_live_adapters or not self.breaker.allow_request():
            return []
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError:
            return []

        code = instrument["native_symbol"]

        def _dl() -> list[dict[str, Any]]:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")
            if df is None or df.empty:
                return []
            out: list[dict[str, Any]] = []
            for _, row in df.tail(limit).iterrows():
                dt = datetime.strptime(str(row["日期"]), "%Y-%m-%d").replace(tzinfo=UTC)
                close_px = float(row["收盘"])
                vol = float(row["成交量"]) * 100.0  # AkShare returns lots (手) -> shares
                out.append(
                    {
                        "instrument_id": instrument["instrument_id"],
                        "timeframe": "1d",
                        "ts_utc": dt,
                        "session_type": "REGULAR",
                        "currency": "CNY",
                        "open": float(row["开盘"]),
                        "high": float(row["最高"]),
                        "low": float(row["最低"]),
                        "close": close_px,
                        "adj_close": close_px,
                        "volume": vol,
                        "turnover_value": float(row["成交额"]),
                        "vwap": float(row["成交额"]) / vol if vol > 0 else close_px,
                        "adj_factor": 1.0,
                        "source_adapter": self.name,
                    }
                )
            return out

        try:
            rows = await asyncio.wait_for(asyncio.to_thread(_dl), timeout=settings.adapter_timeout_sec)
            self.breaker.record_success()
            return rows
        except Exception:
            self.breaker.record_failure()
            return []

    async def fetch_quote(self, instrument: dict[str, Any]) -> dict[str, Any] | None:
        return None


class CryptoCCXTAdapter(MarketDataAdapter):
    """Live Crypto Spot & Perp adapter via CCXT + DefiLlama public TVL/fees API."""

    name = "crypto_ccxt_defillama"
    supported_markets = ("CRYPTO",)

    async def fetch_ohlcv(
        self, instrument: dict[str, Any], timeframe: str = "1d", limit: int = 250
    ) -> list[dict[str, Any]]:
        if not settings.enable_live_adapters or not self.breaker.allow_request():
            return []
        try:
            import ccxt  # type: ignore[import-not-found]
        except ImportError:
            return []

        base = instrument["native_symbol"].split("-")[0]
        pair = f"{base}/USDT"

        def _dl() -> list[dict[str, Any]]:
            ex = ccxt.binance({"enableRateLimit": True})
            candles = ex.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
            out: list[dict[str, Any]] = []
            for c in candles:
                dt = datetime.fromtimestamp(c[0] / 1000.0, tz=UTC)
                close_px = float(c[4])
                vol = float(c[5])
                out.append(
                    {
                        "instrument_id": instrument["instrument_id"],
                        "timeframe": timeframe,
                        "ts_utc": dt,
                        "session_type": "CONTINUOUS_24_7",
                        "currency": "USD",
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": close_px,
                        "adj_close": close_px,
                        "volume": vol,
                        "turnover_value": close_px * vol,
                        "vwap": float((c[2] + c[3] + c[4]) / 3.0),
                        "adj_factor": 1.0,
                        "source_adapter": self.name,
                    }
                )
            return out

        try:
            rows = await asyncio.wait_for(asyncio.to_thread(_dl), timeout=settings.adapter_timeout_sec)
            self.breaker.record_success()
            return rows
        except Exception:
            self.breaker.record_failure()
            return []

    async def fetch_quote(self, instrument: dict[str, Any]) -> dict[str, Any] | None:
        return None
