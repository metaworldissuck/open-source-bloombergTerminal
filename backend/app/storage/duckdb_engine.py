from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from app.config import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class DuckDBEngine:
    """Thread-safe DuckDB analytical engine with native Polars zero-copy bulk insert & Parquet export."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else settings.duckdb_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = duckdb.connect(str(self.db_path))
        self._conn.execute("SET TimeZone='UTC';")
        self._apply_migrations()

    def _apply_migrations(self) -> None:
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        with self._lock:
            for mf in migration_files:
                sql = mf.read_text(encoding="utf-8")
                self._conn.execute(sql)

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        with self._lock:
            if params is not None:
                self._conn.execute(sql, params)
            else:
                self._conn.execute(sql)

    def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION")
            try:
                self._conn.executemany(sql, rows)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def bulk_insert_polars(self, table: str, df: pl.DataFrame) -> None:
        """Ultra-fast vectorized insert into DuckDB directly from a Polars DataFrame."""
        if df.is_empty():
            return
        with self._lock:
            self._conn.register("_openterm_bulk_df", df)
            try:
                self._conn.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM _openterm_bulk_df")
            finally:
                self._conn.unregister("_openterm_bulk_df")

    def query_dicts(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params) if params is not None else self._conn.execute(sql)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    def query_polars(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> pl.DataFrame:
        with self._lock:
            cur = self._conn.execute(sql, params) if params is not None else self._conn.execute(sql)
            return pl.from_arrow(cur.to_arrow_table())  # type: ignore[return-value]

    def query_readonly_dicts(
        self, sql: str, max_rows: int = 2000
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Execute a strictly read-only analytical query for BQL-lite."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(sql)
                if cur.description is None:
                    return [], []
                cols = [d[0] for d in cur.description]
                raw_rows = cur.fetchmany(max_rows)
                rows = [dict(zip(cols, row, strict=False)) for row in raw_rows]
                return cols, rows
            finally:
                cur.close()

    def export_ohlcv_parquet(self, parquet_dir: Path | None = None) -> Path:
        """Snapshot fact_ohlcv to a ZSTD-compressed Parquet file for external tools."""
        target = (parquet_dir or settings.parquet_dir) / "ohlcv.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn.execute(
                f"COPY (SELECT * FROM fact_ohlcv ORDER BY instrument_id, ts_utc) "
                f"TO '{target.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);"
            )
        return target

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_engine_singleton: DuckDBEngine | None = None


def get_db() -> DuckDBEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = DuckDBEngine()
    return _engine_singleton
