from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENTERM_", env_file=".env", extra="ignore")

    app_name: str = "OpenTerm Quantitative Terminal"
    version: str = "0.1.0"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    duckdb_filename: str = "openterm.duckdb"
    enable_live_adapters: bool = True  # Queries live yfinance/SEC/AkShare/CCXT/EastMoney adapters
    adapter_timeout_sec: float = 4.0
    ohlcv_cache_ttl_sec: int = 300
    quote_cache_ttl_sec: int = 10
    sec_edgar_user_agent: str = "OpenTermResearch/0.1 (contact@openterm.local)"
    polygon_api_key: str | None = None
    tushare_token: str | None = None
    bql_max_rows: int = 2000
    bql_timeout_sec: float = 5.0
    cors_origins: list[str] = ["*"]

    @property
    def duckdb_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / self.duckdb_filename

    @property
    def parquet_dir(self) -> Path:
        p = self.data_dir / "parquet"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
