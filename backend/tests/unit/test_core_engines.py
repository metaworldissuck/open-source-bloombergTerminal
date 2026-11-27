from __future__ import annotations

from datetime import date

import pytest

from app.adapters.seed_fixtures import seed_database_if_empty
from app.analytics.bql_engine import BqlEngine
from app.analytics.fa_service import FaService
from app.analytics.port_service import PortService
from app.core.command_parser import MnemonicCommandParser
from app.core.security_master import SecurityMaster, normalize_china_ashare_ticker
from app.normalization.cn_microstructure import compute_cn_price_limits, compute_settlement_date
from app.normalization.sentiment import score_financial_sentiment
from app.storage.duckdb_engine import DuckDBEngine


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> DuckDBEngine:
    db_file = tmp_path_factory.mktemp("duckdb") / "test.duckdb"
    engine = DuckDBEngine(db_path=db_file)
    seed_database_if_empty(engine)
    yield engine
    engine.close()


def test_china_ashare_ticker_normalization() -> None:
    moutai = normalize_china_ashare_ticker("600519")
    assert moutai is not None
    assert moutai.instrument_id == "EQ:SSE:600519"
    assert moutai.yahoo_suffix == ".SS"
    assert moutai.board == "MAIN"
    assert moutai.price_limit_pct == 0.10

    catl = normalize_china_ashare_ticker("300750.SZ")
    assert catl is not None
    assert catl.instrument_id == "EQ:SZSE:300750"
    assert catl.board == "CHINEXT"
    assert catl.price_limit_pct == 0.20

    smic = normalize_china_ashare_ticker("688981")
    assert smic is not None
    assert smic.board == "STAR"
    assert smic.price_limit_pct == 0.20

    bse = normalize_china_ashare_ticker("430047")
    assert bse is not None
    assert bse.yahoo_suffix == ".BJ"
    assert bse.board == "BSE"
    assert bse.price_limit_pct == 0.30

    st_stock = normalize_china_ashare_ticker("600001", is_st=True)
    assert st_stock is not None
    assert st_stock.price_limit_pct == 0.05


def test_cn_price_limit_rounding_and_settlement() -> None:
    band = compute_cn_price_limits(prev_close=10.05, current_price=11.06, limit_pct=0.10)
    assert band.limit_up == 11.06  # 10.05 * 1.10 = 11.055 -> half-up 11.06
    assert band.limit_down == 9.05  # 10.05 * 0.90 = 9.045 -> half-up 9.05
    assert band.hit_limit_up is True
    assert band.hit_limit_down is False

    # Friday trade settles Monday under T+1, same day under T+0
    fri = date(2026, 11, 27)
    assert compute_settlement_date(fri, "T+1_CN_STRICT") == date(2026, 11, 30)
    assert compute_settlement_date(fri, "T+0_INSTANT") == fri


def test_mnemonic_command_parser(db: DuckDBEngine) -> None:
    parser = MnemonicCommandParser(SecurityMaster(db))

    c1 = parser.parse("AAPL US <Equity> DES")
    assert c1.error is None
    assert c1.function == "DES"
    assert c1.instrument_ids == ["EQ:US:AAPL"]

    c2 = parser.parse("600519 CH <Equity> FA")
    assert c2.error is None
    assert c2.function == "FA"
    assert c2.instrument_ids == ["EQ:SSE:600519"]

    c3 = parser.parse("BTC-USD <Crypto> GP 1D")
    assert c3.error is None
    assert c3.function == "GP"
    assert c3.instrument_ids == ["CR:SPOT:BTC-USD"]
    assert c3.args == ["1D"]

    # Context-inherited shorthand
    c4 = parser.parse("FA", active_instrument_id="EQ:SZSE:300750")
    assert c4.error is None
    assert c4.function == "FA"
    assert c4.instrument_ids == ["EQ:SZSE:300750"]

    # Multi-security comparison
    c5 = parser.parse("AAPL US, NVDA US, 600519 CH COMP")
    assert c5.error is None
    assert c5.function == "COMP"
    assert c5.instrument_ids == ["EQ:US:AAPL", "EQ:US:NVDA", "EQ:SSE:600519"]

    # Global commands
    assert parser.parse("PORT").function == "PORT"
    assert parser.parse("BQL").function == "BQL"
    assert parser.parse("NEWS").function == "NEWS"


def test_dcf_engine_monotonicity(db: DuckDBEngine) -> None:
    fa = FaService(db)
    low_wacc = fa.calculate_dcf("EQ:US:AAPL", wacc=0.08, terminal_growth=0.03, fcf_growth_5y=0.10)
    high_wacc = fa.calculate_dcf("EQ:US:AAPL", wacc=0.11, terminal_growth=0.03, fcf_growth_5y=0.10)
    assert low_wacc["outputs"]["implied_share_price"] > high_wacc["outputs"]["implied_share_price"]
    assert len(low_wacc["sensitivity"]["implied_prices"]) == 5


def test_bql_sandbox_security_and_backtest(db: DuckDBEngine) -> None:
    bql = BqlEngine(db)
    # Read-only SQL succeeds
    res = bql.execute("SELECT COUNT(*) AS n FROM dim_instruments", mode="SQL")
    assert res["rows"][0]["n"] >= 10

    # Mutating SQL is blocked
    with pytest.raises(ValueError, match="Read-only violation"):
        bql.execute("DROP TABLE dim_instruments", mode="SQL")

    # Python sandbox blocks imports & os escapes
    with pytest.raises(ValueError, match="Imports are disabled"):
        bql.execute("import os\nresult = os.listdir('.')", mode="PYTHON")

    # Vectorized Python backtest template runs cleanly
    tpl = next(t for t in bql.get_templates() if t["mode"] == "PYTHON")
    py_res = bql.execute(tpl["code"], mode="PYTHON")
    assert py_res["row_count"] == 1
    assert isinstance(py_res["chart"], list) and len(py_res["chart"]) > 50


def test_portfolio_risk_and_t1_lock(db: DuckDBEngine) -> None:
    port = PortService(db).get_portfolio_analytics("PORT_MAIN", base_currency="USD")
    assert port["summary"]["total_market_value"] > 0
    assert port["risk"]["var_95_1d_pct"] > 0
    assert port["risk"]["max_drawdown_pct"] <= 0
    assert len(port["correlation_matrix"]["matrix"]) == len(port["holdings"])
    # Verify Moutai intraday lot has T+1 sell lock > 0
    moutai = next(h for h in port["holdings"] if h["instrument_id"] == "EQ:SSE:600519")
    assert moutai["t1_locked_qty"] == 100.0


def test_bilingual_sentiment() -> None:
    s_en, lbl_en = score_financial_sentiment("NVIDIA beats guidance with record growth and surge", "en")
    assert s_en > 0 and lbl_en == "BULLISH"
    s_zh, lbl_zh = score_financial_sentiment("贵州茅台净流入增长超预期创新高", "zh")
    assert s_zh > 0 and lbl_zh == "BULLISH"
    s_neg, lbl_neg = score_financial_sentiment("Company faces SEC investigation and plunge after miss", "en")
    assert s_neg < 0 and lbl_neg == "BEARISH"
