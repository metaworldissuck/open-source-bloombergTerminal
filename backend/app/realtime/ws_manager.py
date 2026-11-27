from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from app.normalization.cn_microstructure import compute_cn_price_limits
from app.storage.duckdb_engine import DuckDBEngine


class RealtimeTickManager:
    """WebSocket pub/sub multiplexer streaming real-time price & volume ticks per canonical instrument_id."""

    def __init__(self, db: DuckDBEngine):
        self.db = db
        self._connections: dict[WebSocket, set[str]] = {}
        self._live_state: dict[str, dict[str, Any]] = {}
        self._task: asyncio.Task[None] | None = None
        self._rng = random.Random(42)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[ws] = set()

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.pop(ws, None)

    def subscribe(self, ws: WebSocket, instrument_ids: list[str]) -> None:
        if ws in self._connections:
            self._connections[ws].update(instrument_ids)

    def unsubscribe(self, ws: WebSocket, instrument_ids: list[str]) -> None:
        if ws in self._connections:
            self._connections[ws].difference_update(instrument_ids)

    def _ensure_state(self, instrument_id: str) -> dict[str, Any] | None:
        if instrument_id in self._live_state:
            return self._live_state[instrument_id]
        rows = self.db.query_dicts(
            """
            SELECT o.close, o.volume, i.market, i.price_limit_pct, i.base_currency
            FROM fact_ohlcv o
            JOIN dim_instruments i USING (instrument_id)
            WHERE o.instrument_id = ? AND o.timeframe = '1d'
            ORDER BY o.ts_utc DESC
            LIMIT 2
            """,
            [instrument_id],
        )
        if not rows:
            return None
        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else latest
        state = {
            "price": float(latest["close"]),
            "prev_close": float(prev["close"]),
            "volume": float(latest["volume"]),
            "market": latest["market"],
            "price_limit_pct": latest["price_limit_pct"],
            "currency": latest["base_currency"],
        }
        self._live_state[instrument_id] = state
        return state

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(1.5)
            if not self._connections:
                continue

            subscribed_all: set[str] = set()
            for subs in self._connections.values():
                subscribed_all.update(subs)
            if not subscribed_all:
                continue

            ticks: dict[str, dict[str, Any]] = {}
            now_iso = datetime.now(UTC).isoformat()
            for iid in subscribed_all:
                st = self._ensure_state(iid)
                if not st:
                    continue
                sigma = 0.0014 if st["market"] == "CRYPTO" else 0.0006
                nxt = st["price"] * (1.0 + self._rng.gauss(0.0, sigma))
                # Respect China A-Share exact limit-up/limit-down bounds
                hit_up, hit_dn = False, False
                if st["market"] == "CN_ASHARE" and st["price_limit_pct"]:
                    band = compute_cn_price_limits(st["prev_close"], nxt, float(st["price_limit_pct"]))
                    nxt = min(band.limit_up, max(band.limit_down, round(nxt, 2)))
                    hit_up, hit_dn = band.hit_limit_up, band.hit_limit_down
                else:
                    nxt = round(nxt, 4 if nxt < 10 else 2)

                st["price"] = nxt
                st["volume"] += round(abs(self._rng.gauss(1200, 800)), 2)
                chg = nxt - st["prev_close"]
                chg_pct = (chg / st["prev_close"] * 100.0) if st["prev_close"] else 0.0
                ticks[iid] = {
                    "type": "tick",
                    "instrument_id": iid,
                    "price": nxt,
                    "change": round(chg, 4 if abs(chg) < 1 else 2),
                    "change_pct": round(chg_pct, 2),
                    "volume": round(st["volume"], 2),
                    "hit_limit_up": hit_up,
                    "hit_limit_down": hit_dn,
                    "ts_utc": now_iso,
                }

            dead: list[WebSocket] = []
            for ws, subs in list(self._connections.items()):
                for iid in subs:
                    payload = ticks.get(iid)
                    if payload:
                        try:
                            await ws.send_json(payload)
                        except Exception:
                            dead.append(ws)
                            break
            for ws in dead:
                self.disconnect(ws)
