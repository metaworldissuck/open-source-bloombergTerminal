from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.orchestrator import DataOrchestrator
from app.analytics.bql_engine import BqlEngine
from app.analytics.comp_service import CompService
from app.analytics.des_service import DesService
from app.analytics.fa_service import FaService
from app.analytics.gp_service import GpService
from app.analytics.microstructure_service import MicrostructureService
from app.analytics.news_service import NewsService
from app.analytics.port_service import PortService
from app.core.calendars import get_market_sessions
from app.core.command_parser import MnemonicCommandParser
from app.core.security_master import SecurityMaster
from app.storage.duckdb_engine import get_db

api_router = APIRouter(prefix="/v1")


class CommandParseRequest(BaseModel):
    command: str = Field(..., min_length=1)
    active_instrument_id: str | None = None


class DcfRequest(BaseModel):
    instrument_id: str
    wacc: float = Field(0.095, gt=0.01, lt=0.40)
    terminal_growth: float = Field(0.03, ge=0.0, lt=0.15)
    fcf_growth_5y: float = Field(0.12, ge=-0.20, lt=0.80)


class CompRequest(BaseModel):
    instrument_ids: list[str] = Field(..., min_length=1, max_length=10)
    base_currency: str = "USD"
    lookback_days: int = Field(180, ge=10, le=420)


class TransactionCreateRequest(BaseModel):
    portfolio_id: str = "PORT_MAIN"
    instrument_id: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    trade_date: date | None = None
    notes: str = ""


class BqlExecuteRequest(BaseModel):
    mode: str = Field("SQL", pattern="^(SQL|PYTHON)$")
    code: str = Field(..., min_length=1)


@api_router.get("/health")
def health() -> dict[str, Any]:
    db = get_db()
    cnt = db.query_dicts("SELECT COUNT(*) AS n FROM dim_instruments")[0]["n"]
    return {"status": "ok", "instruments_loaded": cnt, "sessions": get_market_sessions()}


@api_router.get("/market/status")
def market_status() -> dict[str, Any]:
    db = get_db()
    fx = db.query_dicts(
        """
        SELECT base_ccy || '/' || quote_ccy AS pair, arg_max(rate, ts_utc) AS rate
        FROM fact_fx_rates
        WHERE (base_ccy = 'USD' AND quote_ccy = 'CNY')
           OR (base_ccy = 'USDT' AND quote_ccy = 'USD')
        GROUP BY base_ccy, quote_ccy
        """
    )
    watchlist = db.query_dicts(
        """
        WITH ranked AS (
            SELECT instrument_id, close,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY ts_utc DESC) AS rn
            FROM fact_ohlcv WHERE timeframe = '1d'
        )
        SELECT i.instrument_id, i.native_symbol, i.market, i.base_currency,
               r1.close AS price,
               ROUND((r1.close - r2.close) / NULLIF(r2.close, 0) * 100, 2) AS change_pct
        FROM dim_instruments i
        JOIN ranked r1 ON r1.instrument_id = i.instrument_id AND r1.rn = 1
        LEFT JOIN ranked r2 ON r2.instrument_id = i.instrument_id AND r2.rn = 2
        WHERE i.instrument_id IN ('EQ:US:AAPL', 'EQ:US:NVDA', 'EQ:SSE:600519', 'EQ:SZSE:300750', 'CR:SPOT:BTC-USD', 'CR:SPOT:ETH-USD')
        ORDER BY i.market, i.native_symbol
        """
    )
    return {"sessions": get_market_sessions(), "fx": fx, "ticker_tape": watchlist}


@api_router.post("/command/parse")
def parse_command(req: CommandParseRequest) -> dict[str, Any]:
    db = get_db()
    parser = MnemonicCommandParser(SecurityMaster(db))
    parsed = parser.parse(req.command, active_instrument_id=req.active_instrument_id)
    return parsed.to_dict()


@api_router.get("/command/autocomplete")
def autocomplete(
    q: str = Query("", max_length=100),
    active_instrument_id: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    parser = MnemonicCommandParser(SecurityMaster(db))
    return {"suggestions": parser.autocomplete(q, active_instrument_id=active_instrument_id)}


@api_router.get("/instruments")
def list_instruments(q: str = "") -> dict[str, Any]:
    db = get_db()
    sm = SecurityMaster(db)
    return {"items": sm.search(q, limit=30)}


@api_router.get("/analytics/des/{instrument_id:path}")
def get_des(instrument_id: str) -> dict[str, Any]:
    data = DesService(get_db()).get_des(instrument_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")
    return data


@api_router.get("/analytics/fa/{instrument_id:path}")
def get_fa(instrument_id: str, period: str = Query("FY", pattern="^(FY|Q)$")) -> dict[str, Any]:
    data = FaService(get_db()).get_financials(instrument_id, period=period)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Financials for '{instrument_id}' not found")
    return data


@api_router.post("/analytics/dcf")
def compute_dcf(req: DcfRequest) -> dict[str, Any]:
    try:
        return FaService(get_db()).calculate_dcf(
            instrument_id=req.instrument_id,
            wacc=req.wacc,
            terminal_growth=req.terminal_growth,
            fcf_growth_5y=req.fcf_growth_5y,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/analytics/gp/{instrument_id:path}")
def get_gp(
    instrument_id: str,
    range: str = Query("1Y", pattern="^(1M|3M|6M|1Y|ALL)$"),
    timeframe: str = Query("1d", pattern="^(1d|1w)$"),
) -> dict[str, Any]:
    data = GpService(get_db()).get_chart_data(instrument_id, range_code=range, timeframe=timeframe)
    if data is None:
        raise HTTPException(status_code=404, detail=f"OHLCV data for '{instrument_id}' not found")
    return data


@api_router.post("/analytics/comp")
def get_comp(req: CompRequest) -> dict[str, Any]:
    return CompService(get_db()).compare(
        instrument_ids=req.instrument_ids,
        base_currency=req.base_currency,
        lookback_days=req.lookback_days,
    )


@api_router.get("/news")
def get_news(
    instrument_id: str | None = None,
    sentiment: str | None = None,
    keyword: str | None = None,
    language: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return NewsService(get_db()).list_news(
        instrument_id=instrument_id,
        sentiment=sentiment,
        keyword=keyword,
        language=language,
        limit=limit,
    )


@api_router.get("/microstructure/opt/{instrument_id:path}")
def get_opt_view(instrument_id: str) -> dict[str, Any]:
    return MicrostructureService(get_db()).get_us_options_view(instrument_id)


@api_router.get("/microstructure/flow")
def get_cn_flow_view() -> dict[str, Any]:
    return MicrostructureService(get_db()).get_cn_flow_monitor()


@api_router.get("/microstructure/perp/{instrument_id:path}")
def get_crypto_perp_view(instrument_id: str) -> dict[str, Any]:
    return MicrostructureService(get_db()).get_crypto_perp_dashboard(instrument_id)


@api_router.post("/market/refresh/{instrument_id:path}")
async def refresh_live_market(instrument_id: str) -> dict[str, Any]:
    try:
        return await DataOrchestrator(get_db()).refresh_instrument(instrument_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/port")
def get_portfolio(
    portfolio_id: str = "PORT_MAIN",
    base_currency: str = Query("USD", pattern="^(USD|CNY|USDT)$"),
) -> dict[str, Any]:
    return PortService(get_db()).get_portfolio_analytics(
        portfolio_id=portfolio_id, base_currency=base_currency
    )


@api_router.post("/port/transactions")
def create_transaction(req: TransactionCreateRequest) -> dict[str, Any]:
    try:
        return PortService(get_db()).add_transaction(
            portfolio_id=req.portfolio_id,
            instrument_id=req.instrument_id,
            side=req.side,
            quantity=req.quantity,
            price=req.price,
            trade_date=req.trade_date,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/bql/templates")
def get_bql_templates() -> dict[str, Any]:
    return {"templates": BqlEngine(get_db()).get_templates()}


@api_router.post("/bql/execute")
def execute_bql(req: BqlExecuteRequest) -> dict[str, Any]:
    try:
        return BqlEngine(get_db()).execute(code=req.code, mode=req.mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
