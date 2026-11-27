from __future__ import annotations

import ast
import io
import math
import re
import time
from contextlib import redirect_stdout
from typing import Any

import numpy as np
import polars as pl

from app.config import settings
from app.storage.duckdb_engine import DuckDBEngine

FORBIDDEN_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|COPY|ATTACH|DETACH|PRAGMA|CALL|EXPORT|IMPORT|LOAD|INSTALL)\b",
    re.IGNORECASE,
)

FORBIDDEN_AST_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "__builtins__",
    "__subclasses__", "__class__", "__bases__", "__mro__",
}

BQL_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "cross_asset_perf",
        "name": "Cross-Asset 30D USD Return & Volatility (SQL)",
        "mode": "SQL",
        "description": "Joins US Equities, China A-Shares, and Crypto in a single FX-normalized DuckDB query.",
        "code": """WITH latest_fx AS (
    SELECT base_ccy, arg_max(rate, ts_utc) AS fx_to_usd
    FROM fact_fx_rates WHERE quote_ccy = 'USD' GROUP BY base_ccy
),
px AS (
    SELECT o.instrument_id, i.native_symbol, i.market, i.base_currency,
           o.ts_utc::DATE AS dt,
           o.close * COALESCE(fx.fx_to_usd, 1.0) AS close_usd
    FROM fact_ohlcv o
    JOIN dim_instruments i USING (instrument_id)
    LEFT JOIN latest_fx fx ON i.base_currency = fx.base_ccy
    WHERE o.timeframe = '1d'
      AND o.ts_utc >= CURRENT_TIMESTAMP - INTERVAL 45 DAY
),
rets AS (
    SELECT instrument_id, native_symbol, market, dt, close_usd,
           (close_usd / LAG(close_usd) OVER (PARTITION BY instrument_id ORDER BY dt)) - 1 AS ret
    FROM px
)
SELECT native_symbol AS symbol,
       market,
       ROUND(arg_max(close_usd, dt), 2) AS last_usd,
       ROUND((EXP(SUM(LN(1 + ret))) - 1) * 100, 2) AS return_45d_usd_pct,
       ROUND(STDDEV(ret) * SQRT(CASE WHEN market = 'CRYPTO' THEN 365 ELSE 252 END) * 100, 2) AS ann_vol_pct
FROM rets
WHERE ret IS NOT NULL
GROUP BY instrument_id, native_symbol, market
ORDER BY return_45d_usd_pct DESC;""",
    },
    {
        "id": "value_quality_screen",
        "name": "Global Value & Margin Factor Screen (SQL)",
        "mode": "SQL",
        "description": "Screens normalized US GAAP & China CAS financials for high gross margins and FCF generation.",
        "code": """WITH latest_fy AS (
    SELECT instrument_id, metric_code, value
    FROM fact_financials
    WHERE period_type = 'FY'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY instrument_id, metric_code ORDER BY fiscal_end_date DESC) = 1
),
piv AS (
    SELECT instrument_id,
           MAX(CASE WHEN metric_code = 'revenue' THEN value END) AS revenue,
           MAX(CASE WHEN metric_code = 'gross_profit' THEN value END) AS gross_profit,
           MAX(CASE WHEN metric_code = 'net_income' THEN value END) AS net_income,
           MAX(CASE WHEN metric_code = 'free_cash_flow' THEN value END) AS fcf
    FROM latest_fy GROUP BY instrument_id
)
SELECT i.native_symbol AS symbol, i.display_name, i.market, i.base_currency AS ccy,
       ROUND(p.revenue / 1e9, 2) AS rev_bn,
       ROUND((p.gross_profit / NULLIF(p.revenue, 0)) * 100, 1) AS gross_margin_pct,
       ROUND((p.net_income / NULLIF(p.revenue, 0)) * 100, 1) AS net_margin_pct,
       ROUND(p.fcf / 1e9, 2) AS fcf_bn
FROM piv p
JOIN dim_instruments i USING (instrument_id)
WHERE p.revenue > 0
ORDER BY gross_margin_pct DESC;""",
    },
    {
        "id": "cn_northbound_limits",
        "name": "China A-Share Northbound Flow & Limit-Up Scanner (SQL)",
        "mode": "SQL",
        "description": "Inspects A-Share 涨跌停 bands, turnover rate, and Stock Connect Northbound holdings.",
        "code": """SELECT i.native_symbol AS code, i.display_name_local AS name_cn,
       m.trade_date, m.prev_close, m.limit_up_price, m.limit_down_price,
       m.hit_limit_up, m.turnover_rate_pct,
       m.northbound_hold_pct,
       ROUND(m.northbound_net_flow_cny / 1e6, 2) AS nb_net_flow_m_cny
FROM fact_cn_microstructure m
JOIN dim_instruments i USING (instrument_id)
QUALIFY ROW_NUMBER() OVER (PARTITION BY m.instrument_id ORDER BY m.trade_date DESC) = 1
ORDER BY nb_net_flow_m_cny DESC;""",
    },
    {
        "id": "sma_crossover_backtest",
        "name": "Dual-SMA Momentum Backtest on NVDA / BTC (Python)",
        "mode": "PYTHON",
        "description": "Runs a vectorized Polars SMA(10)/SMA(30) crossover backtest and renders an equity curve.",
        "code": """# Available sandbox helpers: query(sql) -> pl.DataFrame, pl (Polars), np (NumPy), run_backtest(df)
df = query(\"\"\"
    SELECT ts_utc::DATE AS dt, close
    FROM fact_ohlcv
    WHERE instrument_id = 'CR:SPOT:BTC-USD' AND timeframe = '1d'
    ORDER BY dt ASC
\"\"\")

df = df.with_columns([
    pl.col("close").rolling_mean(10).alias("sma_fast"),
    pl.col("close").rolling_mean(30).alias("sma_slow"),
]).with_columns([
    pl.when(pl.col("sma_fast") > pl.col("sma_slow")).then(1.0).otherwise(0.0).alias("signal")
])

stats, curve = run_backtest(df, ann_days=365)
print("Strategy Summary:", stats)
result = pl.DataFrame([stats])
chart = curve
""",
    },
]


def _validate_python_ast(code: str) -> None:
    """Strictly validate Python AST to prevent arbitrary code execution or filesystem/OS access."""
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are disabled in BQL-lite sandbox. Use preloaded `query`, `pl`, `np`, `math`, `run_backtest`.")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_AST_NAMES:
            raise ValueError(f"Disallowed identifier in sandbox: '{node.id}'")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"Access to dunder attribute '{node.attr}' is prohibited in sandbox.")


def _run_vectorized_backtest(df: pl.DataFrame, ann_days: int = 252) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Vectorized long/flat or long/short strategy backtester over ['dt', 'close', 'signal']."""
    if not {"dt", "close", "signal"}.issubset(set(df.columns)):
        raise ValueError("run_backtest requires columns: 'dt', 'close', 'signal'")

    work = df.drop_nulls(subset=["close", "signal"]).with_columns(
        [
            pl.col("close").pct_change().fill_null(0.0).alias("asset_ret"),
            pl.col("signal").shift(1).fill_null(0.0).alias("pos"),
        ]
    ).with_columns(
        [
            (pl.col("pos") * pl.col("asset_ret")).alias("strat_ret"),
        ]
    )

    strat_rets = work["strat_ret"].to_numpy()
    bm_rets = work["asset_ret"].to_numpy()
    dates = [str(d) for d in work["dt"].to_list()]

    eq = np.cumprod(1.0 + strat_rets)
    bm = np.cumprod(1.0 + bm_rets)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak

    total_ret = float((eq[-1] - 1.0) * 100.0) if len(eq) else 0.0
    bm_ret = float((bm[-1] - 1.0) * 100.0) if len(bm) else 0.0
    std = float(np.std(strat_rets, ddof=1)) if len(strat_rets) > 1 else 0.0
    mean = float(np.mean(strat_rets)) if len(strat_rets) else 0.0
    sharpe = (mean / std * math.sqrt(ann_days)) if std > 1e-9 else 0.0
    max_dd = float(np.min(dd) * 100.0) if len(dd) else 0.0
    active_days = strat_rets[work["pos"].to_numpy() != 0]
    win_rate = float(np.mean(active_days > 0) * 100.0) if len(active_days) else 0.0

    stats = {
        "total_return_pct": round(total_ret, 2),
        "buy_hold_return_pct": round(bm_ret, 2),
        "excess_return_pct": round(total_ret - bm_ret, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 1),
        "bars_tested": len(eq),
    }
    curve = [
        {
            "time": dates[i],
            "strategy": round(float(eq[i] * 100.0), 2),
            "benchmark": round(float(bm[i] * 100.0), 2),
        }
        for i in range(len(eq))
    ]
    return stats, curve


def _serialize_val(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


class BqlEngine:
    """BQL-lite Programmable Analytical Query Console (Read-Only DuckDB SQL + Sandboxed Python/Polars)."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def get_templates(self) -> list[dict[str, str]]:
        return BQL_TEMPLATES

    def execute(self, code: str, mode: str = "SQL") -> dict[str, Any]:
        t0 = time.perf_counter()
        m = mode.upper()
        if m == "SQL":
            return self._execute_sql(code, t0)
        if m == "PYTHON":
            return self._execute_python(code, t0)
        raise ValueError(f"Unsupported BQL mode: {mode}")

    def _execute_sql(self, sql: str, t0: float) -> dict[str, Any]:
        stripped = sql.strip()
        if not stripped:
            raise ValueError("SQL query cannot be empty.")
        if FORBIDDEN_SQL_RE.search(stripped):
            raise ValueError("Read-only violation: Mutating SQL statements are blocked in BQL-lite.")

        cols, rows = self.db.query_readonly_dicts(stripped, max_rows=settings.bql_max_rows)
        serialized = [{k: _serialize_val(v) for k, v in r.items()} for r in rows]
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "mode": "SQL",
            "columns": cols,
            "rows": serialized,
            "row_count": len(serialized),
            "stdout": "",
            "chart": None,
            "elapsed_ms": elapsed_ms,
        }

    def _execute_python(self, code: str, t0: float) -> dict[str, Any]:
        _validate_python_ast(code)

        def _safe_query(sql: str) -> pl.DataFrame:
            if FORBIDDEN_SQL_RE.search(sql):
                raise ValueError("Read-only violation in query().")
            return self.db.query_polars(sql)

        safe_builtins = {
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "enumerate": enumerate, "float": float, "int": int, "len": len,
            "list": list, "max": max, "min": min, "print": print, "range": range,
            "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "zip": zip,
        }
        sandbox_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "query": _safe_query,
            "pl": pl,
            "np": np,
            "math": math,
            "run_backtest": _run_vectorized_backtest,
        }
        sandbox_locals: dict[str, Any] = {}
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(compile(code, "<bql_sandbox>", "exec"), sandbox_globals, sandbox_locals)

        res_obj = sandbox_locals.get("result")
        chart_obj = sandbox_locals.get("chart")
        cols: list[str] = []
        rows: list[dict[str, Any]] = []

        if isinstance(res_obj, pl.DataFrame):
            limited = res_obj.head(settings.bql_max_rows)
            cols = limited.columns
            rows = [{k: _serialize_val(v) for k, v in r.items()} for r in limited.to_dicts()]
        elif isinstance(res_obj, list) and res_obj and isinstance(res_obj[0], dict):
            cols = list(res_obj[0].keys())
            rows = [{k: _serialize_val(v) for k, v in r.items()} for r in res_obj[: settings.bql_max_rows]]
        elif isinstance(res_obj, dict):
            cols = list(res_obj.keys())
            rows = [{k: _serialize_val(v) for k, v in res_obj.items()}]

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "mode": "PYTHON",
            "columns": cols,
            "rows": rows,
            "row_count": len(rows),
            "stdout": buf.getvalue(),
            "chart": chart_obj if isinstance(chart_obj, list) else None,
            "elapsed_ms": elapsed_ms,
        }
