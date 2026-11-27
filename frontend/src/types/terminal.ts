export type FunctionCode = 'DES' | 'FA' | 'GP' | 'COMP' | 'OPT' | 'FLOW' | 'PERP' | 'NEWS' | 'PORT' | 'BQL' | 'HELP'
export type LinkGroup = 'A' | 'B' | 'C' | 'NONE'
export type LayoutMode = '1x1' | '1x2' | '2x1' | '2x2'

export interface InstrumentSummary {
  instrument_id: string
  asset_class: string
  market: 'US' | 'CN_ASHARE' | 'CRYPTO' | string
  exchange_mic?: string
  native_symbol: string
  display_name: string
  display_name_local?: string | null
  base_currency: string
}

export interface ParsedCommandResult {
  raw: string
  function: FunctionCode | string
  instrument_ids: string[]
  instruments: InstrumentSummary[]
  args: string[]
  is_global: boolean
  error?: string | null
}

export interface AutocompleteSuggestion {
  kind: 'FUNCTION' | 'SECURITY' | 'COMMAND'
  label: string
  detail: string
  insert_text: string
  badge: string
  instrument_id?: string
}

export interface MarketStatusResponse {
  sessions: Record<
    string,
    {
      label: string
      status: string
      is_open: boolean
      local_time: string
      settlement: string
    }
  >
  fx: Array<{ pair: string; rate: number }>
  ticker_tape: Array<{
    instrument_id: string
    native_symbol: string
    market: string
    base_currency: string
    price: number
    change_pct: number | null
  }>
}

export interface LiveTick {
  type: 'tick'
  instrument_id: string
  price: number
  change: number
  change_pct: number
  volume: number
  hit_limit_up: boolean
  hit_limit_down: boolean
  ts_utc: string
}

export interface DesPayload {
  instrument: InstrumentSummary & {
    sector?: string
    industry?: string
    settlement_rule: string
    lot_size: number
    price_limit_pct?: number | null
    description?: string
    session?: { label: string; status: string; is_open: boolean; local_time: string; settlement: string }
  }
  quote: {
    price: number
    prev_close: number
    change: number
    change_pct: number
    open: number
    high: number
    low: number
    volume: number
    turnover_value?: number | null
    vwap?: number | null
    high_52w: number
    low_52w: number
    avg_volume_30d: number
    as_of_utc: string
  }
  valuation: {
    accounting_standard: string
    currency: string
    market_cap?: number | null
    enterprise_value?: number | null
    pe_ratio?: number | null
    ev_ebitda?: number | null
    pb_ratio?: number | null
    ps_ratio?: number | null
    dividend_yield_pct?: number | null
    beta_5y?: number | null
    shares_outstanding: number
    free_float_pct?: number | null
    total_debt: number
    cash_and_equiv: number
    net_debt: number
  }
  microstructure: Record<string, any>
  recent_events: Array<{
    event_id: string
    date: string
    event_type: string
    title: string
  }>
}

export interface DcfResult {
  instrument_id: string
  currency: string
  inputs: {
    wacc: number
    terminal_growth: number
    fcf_growth_5y: number
    base_fcf: number
    cash: number
    total_debt: number
    shares: number
  }
  outputs: {
    enterprise_value: number
    equity_value: number
    implied_share_price: number
    current_price: number
    upside_pct: number
  }
  projections: Array<{
    year: number
    growth_pct: number
    projected_fcf: number
    pv_fcf: number
  }>
  sensitivity: {
    wacc_axis: number[]
    terminal_growth_axis: number[]
    implied_prices: Array<Array<number | null>>
  }
}

export interface FaPayload {
  instrument_id: string
  native_symbol: string
  display_name: string
  market: string
  accounting_standard: string
  reporting_currency: string
  period_mode: 'FY' | 'Q'
  periods: string[]
  statements: Record<
    'IS' | 'BS' | 'CF',
    Array<{
      metric_code: string
      label: string
      unit: string
      periods: Record<
        string,
        {
          value: number
          yoy_growth: number | null
          qoq_growth: number | null
          filing_date: string
        }
      >
    }>
  >
  multiples: Record<string, number | null>
  dcf_baseline: DcfResult
}

export interface GpPayload {
  instrument: InstrumentSummary & { price_limit_pct?: number | null }
  range: string
  timeframe: string
  candles: Array<{
    time: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
  indicators: Record<string, Array<{ time: string; value: number }>>
  volume_profile: Array<{
    price_low: number
    price_high: number
    price_mid: number
    volume: number
    pct_of_max: number
    is_poc: boolean
  }>
  events: Array<{
    event_id: string
    time: string
    event_type: string
    title: string
  }>
  cn_limit_hits: Array<{
    time: string
    type: 'LIMIT_UP' | 'LIMIT_DOWN'
    label: string
  }>
}

export interface CompPayload {
  base_currency: string
  lookback_days: number
  peers: Array<{
    instrument_id: string
    native_symbol: string
    display_name: string
    market: string
    native_currency: string
    price_native: number
    price_base: number
    market_cap_base: number | null
    revenue_base: number
    revenue_yoy_pct: number | null
    pe: number | null
    ev_ebitda: number | null
    net_margin_pct: number | null
    return_period_pct: number
    return_30d_pct: number
    ann_vol_pct: number
    max_drawdown_pct: number
  }>
  indexed_series: Record<string, Array<{ time: string; value: number }>>
}

export interface NewsPayload {
  count: number
  sentiment_summary: {
    bullish: number
    neutral: number
    bearish: number
    avg_score: number
  }
  items: Array<{
    news_id: string
    published_at_utc: string
    source: string
    language: string
    title: string
    summary: string
    url: string
    instrument_ids: string[]
    sentiment_score: number
    sentiment_label: 'BULLISH' | 'NEUTRAL' | 'BEARISH'
    relevance_score: number
  }>
}

export interface PortPayload {
  portfolio: {
    portfolio_id: string
    name: string
    base_currency: string
    benchmark_instrument_id: string
  }
  summary: {
    total_market_value: number
    total_cost_basis: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
    realized_pnl: number
    currency_exposure: Array<{ currency: string; value_base: number; weight_pct: number }>
    market_exposure: Array<{ market: string; value_base: number; weight_pct: number }>
  }
  holdings: Array<{
    instrument_id: string
    native_symbol: string
    display_name: string
    market: string
    currency: string
    settlement_rule: string
    quantity: number
    sellable_qty: number
    t1_locked_qty: number
    avg_cost_native: number
    last_price_native: number
    market_value_native: number
    market_value_base: number
    cost_basis_base: number
    unrealized_pnl_base: number
    unrealized_pnl_pct: number
    asset_pnl_base: number
    fx_pnl_base: number
    weight_pct: number
  }>
  risk: {
    annualized_return_pct: number
    annualized_volatility_pct: number
    sharpe_ratio: number
    sortino_ratio: number
    max_drawdown_pct: number
    beta_vs_benchmark: number
    var_95_1d_pct: number
    var_95_1d_value: number
    var_99_1d_pct: number
    var_99_1d_value: number
    parametric_var_95_pct: number
    parametric_var_99_pct: number
    risk_free_rate_pct: number
  }
  equity_curve: Array<{ time: string; indexed_value: number; drawdown_pct: number }>
  correlation_matrix: {
    symbols: string[]
    instrument_ids: string[]
    matrix: number[][]
  }
}

export interface BqlTemplate {
  id: string
  name: string
  mode: 'SQL' | 'PYTHON'
  description: string
  code: string
}

export interface BqlExecuteResult {
  mode: 'SQL' | 'PYTHON'
  columns: string[]
  rows: Array<Record<string, any>>
  row_count: number
  stdout: string
  chart: Array<{ time: string; strategy: number; benchmark: number }> | null
  elapsed_ms: number
}

export interface OptContract {
  symbol: string
  bid: number
  ask: number
  last: number
  iv_pct: number
  oi: number
  vol: number
  delta: number
  gamma: number
  theta: number
  vega: number
}

export interface OptPayload {
  instrument: { instrument_id: string; native_symbol: string; display_name: string; base_currency: string }
  spot_price: number
  expiration_date: string
  summary: {
    total_call_oi: number
    total_put_oi: number
    put_call_oi_ratio: number
    atm_iv_pct: number
  }
  straddle_chain: Array<{ strike: number; call: OptContract | null; put: OptContract | null }>
  institutional_13f: Array<{
    institution_name: string
    institution_cik: string
    shares_held: number
    market_value_usd: number
    pct_of_shares_out: number
    qoq_share_change: number
    report_date: string
    filing_date: string
  }>
  sec_filings: Array<{ event_id: string; date: string; type: string; title: string }>
}

export interface FlowPayload {
  summary: {
    northbound_net_today_cny: number
    southbound_net_today_hkd: number
    t_plus_1_active: boolean
    limit_up_count: number
    limit_down_count: number
  }
  board_monitor: Array<{
    instrument_id: string
    native_symbol: string
    yahoo_ticker: string
    display_name: string
    display_name_local: string
    board: string
    limit_pct: number
    price: number
    change_pct: number
    limit_up_price: number
    limit_down_price: number
    hit_limit_up: boolean
    hit_limit_down: boolean
    pct_from_limit_up: number
    turnover_rate_pct: number | null
    northbound_eligible: boolean
    northbound_hold_pct: number | null
    northbound_net_flow_cny: number
    margin_buy_balance_cny: number | null
  }>
  flow_history: Array<{ date: string; northbound_cny: number; southbound_hkd: number }>
  exchange_notices: Array<{
    event_id: string
    instrument_id: string
    symbol: string
    name_cn: string
    date: string
    type: string
    title: string
  }>
}

export interface PerpPayload {
  active_instrument_id: string
  markets: Array<{
    instrument_id: string
    native_symbol: string
    display_name: string
    price: number
    venue: string
    funding_rate: number
    funding_rate_bps: number
    annualized_funding_pct: number
    open_interest_usd: number
    mark_price: number
    index_price: number
    perp_basis_bps: number
    cex_volume_24h_usd: number
    dex_volume_24h_usd: number
    dex_share_pct: number
    tvl_usd: number
    active_addresses_24h: number
  }>
  history: Array<{
    time: string
    funding_bps: number
    ann_funding_pct: number
    open_interest_usd: number
    basis_bps: number
    tvl_usd: number
  }>
}
