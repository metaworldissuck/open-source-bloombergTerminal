-- OpenTerm Unified Multi-Asset Analytical Schema (DuckDB)
-- Supports US Equities, China A-Shares (SSE/SZSE/BSE), and Cryptocurrencies (Spot/Perp)

CREATE TABLE IF NOT EXISTS dim_instruments (
    instrument_id        VARCHAR PRIMARY KEY,
    asset_class          VARCHAR NOT NULL,
    market               VARCHAR NOT NULL,
    exchange_mic         VARCHAR NOT NULL,
    native_symbol        VARCHAR NOT NULL,
    display_name         VARCHAR NOT NULL,
    display_name_local   VARCHAR,
    base_currency        VARCHAR NOT NULL,
    sector               VARCHAR,
    industry             VARCHAR,
    settlement_rule      VARCHAR NOT NULL,
    lot_size             DOUBLE  NOT NULL,
    price_limit_pct      DOUBLE,
    trading_calendar_id  VARCHAR NOT NULL,
    is_active            BOOLEAN DEFAULT TRUE,
    description          VARCHAR,
    microstructure_meta  JSON,
    updated_at_utc       TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_instrument_aliases (
    alias_scheme         VARCHAR NOT NULL,
    alias_value          VARCHAR NOT NULL,
    instrument_id        VARCHAR NOT NULL,
    PRIMARY KEY (alias_scheme, alias_value)
);

CREATE TABLE IF NOT EXISTS fact_ohlcv (
    instrument_id        VARCHAR     NOT NULL,
    timeframe            VARCHAR     NOT NULL,
    ts_utc               TIMESTAMPTZ NOT NULL,
    session_type         VARCHAR     NOT NULL,
    currency             VARCHAR     NOT NULL,
    open                 DOUBLE      NOT NULL,
    high                 DOUBLE      NOT NULL,
    low                  DOUBLE      NOT NULL,
    close                DOUBLE      NOT NULL,
    adj_close            DOUBLE,
    volume               DOUBLE      NOT NULL,
    turnover_value       DOUBLE,
    vwap                 DOUBLE,
    adj_factor           DOUBLE      DEFAULT 1.0,
    source_adapter       VARCHAR     NOT NULL,
    PRIMARY KEY (instrument_id, timeframe, ts_utc)
);

CREATE TABLE IF NOT EXISTS fact_cn_microstructure (
    instrument_id            VARCHAR     NOT NULL,
    trade_date               DATE        NOT NULL,
    prev_close               DOUBLE      NOT NULL,
    limit_up_price           DOUBLE      NOT NULL,
    limit_down_price         DOUBLE      NOT NULL,
    hit_limit_up             BOOLEAN     NOT NULL,
    hit_limit_down           BOOLEAN     NOT NULL,
    is_st_flagged            BOOLEAN     NOT NULL DEFAULT FALSE,
    turnover_rate_pct        DOUBLE,
    northbound_hold_shares   DOUBLE,
    northbound_hold_pct      DOUBLE,
    northbound_net_flow_cny  DOUBLE,
    margin_buy_balance_cny   DOUBLE,
    PRIMARY KEY (instrument_id, trade_date)
);

CREATE TABLE IF NOT EXISTS fact_crypto_metrics (
    instrument_id            VARCHAR     NOT NULL,
    ts_utc                   TIMESTAMPTZ NOT NULL,
    venue                    VARCHAR     NOT NULL,
    funding_rate             DOUBLE,
    annualized_funding_pct   DOUBLE,
    open_interest_usd        DOUBLE,
    mark_price               DOUBLE,
    index_price              DOUBLE,
    perp_basis_bps           DOUBLE,
    cex_volume_24h_usd       DOUBLE,
    dex_volume_24h_usd       DOUBLE,
    tvl_usd                  DOUBLE,
    active_addresses_24h     BIGINT,
    PRIMARY KEY (instrument_id, ts_utc, venue)
);

CREATE TABLE IF NOT EXISTS fact_us_options (
    instrument_id            VARCHAR     NOT NULL,
    snapshot_ts_utc          TIMESTAMPTZ NOT NULL,
    contract_symbol          VARCHAR     NOT NULL,
    expiration_date          DATE        NOT NULL,
    strike                   DOUBLE      NOT NULL,
    option_type              VARCHAR     NOT NULL,
    bid                      DOUBLE,
    ask                      DOUBLE,
    last_price               DOUBLE,
    implied_volatility       DOUBLE,
    open_interest            BIGINT,
    volume                   BIGINT,
    delta                    DOUBLE,
    gamma                    DOUBLE,
    theta                    DOUBLE,
    vega                     DOUBLE,
    PRIMARY KEY (contract_symbol, snapshot_ts_utc)
);

CREATE TABLE IF NOT EXISTS fact_us_13f_holdings (
    instrument_id            VARCHAR NOT NULL,
    report_date              DATE    NOT NULL,
    filing_date              DATE    NOT NULL,
    institution_cik          VARCHAR NOT NULL,
    institution_name         VARCHAR NOT NULL,
    shares_held              BIGINT  NOT NULL,
    market_value_usd         DOUBLE  NOT NULL,
    pct_of_shares_out        DOUBLE,
    qoq_share_change         BIGINT,
    PRIMARY KEY (instrument_id, report_date, institution_cik)
);

CREATE TABLE IF NOT EXISTS fact_financials (
    instrument_id            VARCHAR NOT NULL,
    statement_type           VARCHAR NOT NULL,
    period_type              VARCHAR NOT NULL,
    fiscal_year              INTEGER NOT NULL,
    fiscal_end_date          DATE    NOT NULL,
    filing_date              DATE    NOT NULL,
    accounting_standard      VARCHAR NOT NULL,
    reporting_currency       VARCHAR NOT NULL,
    metric_code              VARCHAR NOT NULL,
    value                    DOUBLE  NOT NULL,
    yoy_growth               DOUBLE,
    qoq_growth               DOUBLE,
    source_adapter           VARCHAR NOT NULL,
    PRIMARY KEY (instrument_id, period_type, fiscal_end_date, filing_date, metric_code)
);

CREATE TABLE IF NOT EXISTS fact_events (
    event_id                 VARCHAR PRIMARY KEY,
    instrument_id            VARCHAR     NOT NULL,
    event_ts_utc             TIMESTAMPTZ NOT NULL,
    event_type               VARCHAR     NOT NULL,
    title                    VARCHAR     NOT NULL,
    payload_json             JSON,
    source_url               VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_news_sentiment (
    news_id                  VARCHAR PRIMARY KEY,
    published_at_utc         TIMESTAMPTZ NOT NULL,
    source                   VARCHAR     NOT NULL,
    language                 VARCHAR     NOT NULL,
    title                    VARCHAR     NOT NULL,
    summary                  VARCHAR,
    url                      VARCHAR,
    instrument_ids           VARCHAR[],
    sentiment_score          DOUBLE,
    sentiment_label          VARCHAR,
    relevance_score          DOUBLE
);

CREATE TABLE IF NOT EXISTS fact_fx_rates (
    base_ccy                 VARCHAR     NOT NULL,
    quote_ccy                VARCHAR     NOT NULL,
    ts_utc                   TIMESTAMPTZ NOT NULL,
    rate                     DOUBLE      NOT NULL,
    PRIMARY KEY (base_ccy, quote_ccy, ts_utc)
);

CREATE TABLE IF NOT EXISTS dim_portfolios (
    portfolio_id             VARCHAR PRIMARY KEY,
    name                     VARCHAR NOT NULL,
    base_currency            VARCHAR NOT NULL DEFAULT 'USD',
    benchmark_instrument_id  VARCHAR DEFAULT 'EQ:US:SPY',
    created_at_utc           TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_transactions (
    tx_id                    VARCHAR PRIMARY KEY,
    portfolio_id             VARCHAR     NOT NULL,
    instrument_id            VARCHAR     NOT NULL,
    trade_ts_utc             TIMESTAMPTZ NOT NULL,
    settlement_date          DATE        NOT NULL,
    side                     VARCHAR     NOT NULL,
    quantity                 DOUBLE      NOT NULL,
    price                    DOUBLE      NOT NULL,
    trade_currency           VARCHAR     NOT NULL,
    fx_to_base_at_trade      DOUBLE      NOT NULL,
    commission               DOUBLE      DEFAULT 0.0,
    notes                    VARCHAR
);
