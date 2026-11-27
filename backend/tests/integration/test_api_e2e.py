from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.storage.duckdb_engine as db_mod
from app.config import settings
from app.main import app


def test_full_api_smoke_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(db_mod, "_engine_singleton", None)

    with TestClient(app) as client:
        h = client.get("/v1/health")
        assert h.status_code == 200
        assert h.json()["instruments_loaded"] >= 10

        # Command parse across US, A-share, Crypto
        for cmd, expected_fn, expected_id in [
            ("AAPL US <Equity> DES", "DES", "EQ:US:AAPL"),
            ("600519 CH <Equity> FA", "FA", "EQ:SSE:600519"),
            ("BTC-USD <Crypto> GP", "GP", "CR:SPOT:BTC-USD"),
        ]:
            r = client.post("/v1/command/parse", json={"command": cmd})
            assert r.status_code == 200
            body = r.json()
            assert body["function"] == expected_fn
            assert body["instrument_ids"] == [expected_id]

        # DES across all 3 markets
        for iid in ("EQ:US:AAPL", "EQ:SSE:600519", "CR:SPOT:BTC-USD"):
            r = client.get(f"/v1/analytics/des/{iid}")
            assert r.status_code == 200
            assert r.json()["quote"]["price"] > 0

        # FA + DCF
        r_fa = client.get("/v1/analytics/fa/EQ:SSE:600519?period=FY")
        assert r_fa.status_code == 200
        assert len(r_fa.json()["statements"]["IS"]) >= 4

        # GP + Indicators + Volume Profile + Events
        r_gp = client.get("/v1/analytics/gp/CR:SPOT:BTC-USD?range=1Y&timeframe=1d")
        assert r_gp.status_code == 200
        gp = r_gp.json()
        assert len(gp["candles"]) > 100
        assert len(gp["volume_profile"]) == 20
        assert len(gp["indicators"]["sma20"]) > 50

        # COMP cross-market
        r_comp = client.post(
            "/v1/analytics/comp",
            json={"instrument_ids": ["EQ:US:NVDA", "EQ:SSE:600519", "CR:SPOT:BTC-USD"], "base_currency": "USD"},
        )
        assert r_comp.status_code == 200
        assert len(r_comp.json()["peers"]) == 3

        # NEWS
        r_news = client.get("/v1/news")
        assert r_news.status_code == 200
        assert r_news.json()["count"] >= 8

        # OPT, FLOW, PERP dedicated microstructure views
        r_opt = client.get("/v1/microstructure/opt/EQ:US:AAPL")
        assert r_opt.status_code == 200
        assert len(r_opt.json()["straddle_chain"]) >= 5
        assert len(r_opt.json()["institutional_13f"]) >= 4

        r_flow = client.get("/v1/microstructure/flow")
        assert r_flow.status_code == 200
        assert len(r_flow.json()["board_monitor"]) >= 4
        assert len(r_flow.json()["flow_history"]) >= 10

        r_perp = client.get("/v1/microstructure/perp/CR:SPOT:BTC-USD")
        assert r_perp.status_code == 200
        assert len(r_perp.json()["markets"]) >= 3
        assert len(r_perp.json()["history"]) >= 10

        # PORT (CNY + USDT)
        for ccy in ("CNY", "USDT"):
            r_port = client.get(f"/v1/port?base_currency={ccy}")
            assert r_port.status_code == 200
            assert r_port.json()["portfolio"]["base_currency"] == ccy

        # BQL
        r_bql = client.post(
            "/v1/bql/execute",
            json={"mode": "SQL", "code": "SELECT market, COUNT(*) AS n FROM dim_instruments GROUP BY market"},
        )
        assert r_bql.status_code == 200
        assert r_bql.json()["row_count"] == 3
