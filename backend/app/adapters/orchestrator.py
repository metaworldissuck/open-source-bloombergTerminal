from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import polars as pl

from app.adapters.live_adapters import ChinaAkShareAdapter, CryptoCCXTAdapter, USYFinanceAdapter
from app.config import settings
from app.storage.duckdb_engine import DuckDBEngine


class DataOrchestrator:
    """Unified multi-asset data orchestrator coordinating live adapters, normalization, and DuckDB+Parquet persistence."""

    def __init__(self, db: DuckDBEngine):
        self.db = db
        self.us_adapter = USYFinanceAdapter()
        self.cn_adapter = ChinaAkShareAdapter()
        self.crypto_adapter = CryptoCCXTAdapter()

    async def refresh_instrument(self, instrument_id: str) -> dict[str, Any]:
        """Attempt live refresh from upstream provider for the given canonical instrument_id and cache into DuckDB + Parquet."""
        rows = self.db.query_dicts(
            "SELECT * FROM dim_instruments WHERE instrument_id = ? LIMIT 1", [instrument_id]
        )
        if not rows:
            raise ValueError(f"Unknown instrument: {instrument_id}")
        inst = rows[0]
        market = inst["market"]

        prev_flag = settings.enable_live_adapters
        settings.enable_live_adapters = True
        try:
            fetched: list[dict[str, Any]] = []
            source_used = "cached_duckdb"
            extra_info: dict[str, Any] = {}

            if market == "US":
                fetched = await self.us_adapter.fetch_ohlcv(inst, timeframe="1d", limit=180)
                if fetched:
                    source_used = self.us_adapter.name
            elif market == "CN_ASHARE":
                fetched = await self.cn_adapter.fetch_ohlcv(inst, timeframe="1d", limit=180)
                if fetched:
                    source_used = self.cn_adapter.name
            elif market == "CRYPTO":
                fetched = await self._fetch_crypto_resilient(inst, limit=180)
                if fetched:
                    source_used = "ccxt_public_live"
                tvl = await self._fetch_defillama_tvl(inst["native_symbol"])
                if tvl is not None:
                    extra_info["defillama_tvl_usd"] = tvl

            if fetched:
                df = pl.DataFrame(fetched)
                self.db.bulk_insert_polars("fact_ohlcv", df)
                self.db.export_ohlcv_parquet()
                return {
                    "instrument_id": instrument_id,
                    "status": "refreshed_live",
                    "source": source_used,
                    "bars_upserted": len(fetched),
                    "latest_close": fetched[-1]["close"],
                    "as_of_utc": datetime.now(timezone.utc).isoformat(),
                    **extra_info,
                }

            return {
                "instrument_id": instrument_id,
                "status": "fallback_cached",
                "source": "duckdb_lakehouse",
                "bars_upserted": 0,
                "as_of_utc": datetime.now(timezone.utc).isoformat(),
                "note": "Upstream free API unavailable or geoblocked; serving cached DuckDB lakehouse data.",
            }
        finally:
            settings.enable_live_adapters = prev_flag

    async def _fetch_crypto_resilient(
        self, instrument: dict[str, Any], limit: int = 180
    ) -> list[dict[str, Any]]:
        """Try multiple public CEX venues (Kraken, Coinbase, OKX, Binance) to avoid regional geoblocks."""
        try:
            import ccxt  # type: ignore[import-not-found]
        except ImportError:
            return []

        base = instrument["native_symbol"].split("-")[0]
        venues = [
            ("kraken", f"{base}/USD"),
            ("coinbase", f"{base}/USD"),
            ("okx", f"{base}/USDT"),
            ("binance", f"{base}/USDT"),
        ]

        def _try_exchanges() -> list[dict[str, Any]]:
            for ex_id, pair in venues:
                try:
                    ex_cls = getattr(ccxt, ex_id)
                    ex = ex_cls({"enableRateLimit": True, "timeout": 4000})
                    candles = ex.fetch_ohlcv(pair, timeframe="1d", limit=limit)
                    if not candles:
                        continue
                    out: list[dict[str, Any]] = []
                    for c in candles:
                        dt = datetime.fromtimestamp(c[0] / 1000.0, tz=timezone.utc)
                        close_px = float(c[4])
                        vol = float(c[5])
                        out.append(
                            {
                                "instrument_id": instrument["instrument_id"],
                                "timeframe": "1d",
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
                                "source_adapter": f"ccxt_{ex_id}",
                            }
                        )
                    return out
                except Exception:  # noqa: BLE001
                    continue
            return []

        try:
            return await asyncio.wait_for(asyncio.to_thread(_try_exchanges), timeout=8.0)
        except Exception:  # noqa: BLE001
            return []

    async def _fetch_defillama_tvl(self, native_symbol: str) -> float | None:
        slug_map = {"ETH-USD": "ethereum", "SOL-USD": "solana"}
        chain = slug_map.get(native_symbol)
        if not chain:
            return None
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"https://api.llama.fi/v2/historicalChainTvl/{chain}")
                resp.raise_for_status()
                arr = resp.json()
                if isinstance(arr, list) and arr:
                    return float(arr[-1].get("tvl", 0.0))
        except Exception:  # noqa: BLE001
            return None
        return None
