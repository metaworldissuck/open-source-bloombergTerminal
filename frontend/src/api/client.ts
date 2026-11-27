import type {
  AutocompleteSuggestion,
  BqlExecuteResult,
  BqlTemplate,
  CompPayload,
  DcfResult,
  DesPayload,
  FaPayload,
  FlowPayload,
  GpPayload,
  InstrumentSummary,
  MarketStatusResponse,
  NewsPayload,
  OptPayload,
  ParsedCommandResult,
  PerpPayload,
  PortPayload,
} from '../types/terminal'

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      // ignore json parse failure
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

export const terminalApi = {
  getMarketStatus: () => apiFetch<MarketStatusResponse>('/v1/market/status'),

  parseCommand: (command: string, active_instrument_id?: string | null) =>
    apiFetch<ParsedCommandResult>('/v1/command/parse', {
      method: 'POST',
      body: JSON.stringify({ command, active_instrument_id: active_instrument_id ?? null }),
    }),

  autocomplete: (q: string, active_instrument_id?: string | null) => {
    const params = new URLSearchParams({ q })
    if (active_instrument_id) params.set('active_instrument_id', active_instrument_id)
    return apiFetch<{ suggestions: AutocompleteSuggestion[] }>(
      `/v1/command/autocomplete?${params.toString()}`,
    )
  },

  listInstruments: (q = '') =>
    apiFetch<{ items: InstrumentSummary[] }>(`/v1/instruments?q=${encodeURIComponent(q)}`),

  getDes: (instrumentId: string) =>
    apiFetch<DesPayload>(`/v1/analytics/des/${encodeURIComponent(instrumentId)}`),

  getFa: (instrumentId: string, period: 'FY' | 'Q' = 'FY') =>
    apiFetch<FaPayload>(`/v1/analytics/fa/${encodeURIComponent(instrumentId)}?period=${period}`),

  calculateDcf: (payload: {
    instrument_id: string
    wacc: number
    terminal_growth: number
    fcf_growth_5y: number
  }) =>
    apiFetch<DcfResult>('/v1/analytics/dcf', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getGp: (instrumentId: string, range = '1Y', timeframe = '1d') =>
    apiFetch<GpPayload>(
      `/v1/analytics/gp/${encodeURIComponent(instrumentId)}?range=${range}&timeframe=${timeframe}`,
    ),

  getComp: (instrument_ids: string[], base_currency = 'USD', lookback_days = 180) =>
    apiFetch<CompPayload>('/v1/analytics/comp', {
      method: 'POST',
      body: JSON.stringify({ instrument_ids, base_currency, lookback_days }),
    }),

  getNews: (params: {
    instrument_id?: string | null
    sentiment?: string
    keyword?: string
    language?: string
  }) => {
    const sp = new URLSearchParams()
    if (params.instrument_id) sp.set('instrument_id', params.instrument_id)
    if (params.sentiment) sp.set('sentiment', params.sentiment)
    if (params.keyword) sp.set('keyword', params.keyword)
    if (params.language) sp.set('language', params.language)
    return apiFetch<NewsPayload>(`/v1/news?${sp.toString()}`)
  },

  getOpt: (instrumentId: string) =>
    apiFetch<OptPayload>(`/v1/microstructure/opt/${encodeURIComponent(instrumentId)}`),

  getFlow: () => apiFetch<FlowPayload>('/v1/microstructure/flow'),

  getPerp: (instrumentId: string) =>
    apiFetch<PerpPayload>(`/v1/microstructure/perp/${encodeURIComponent(instrumentId)}`),

  refreshLive: (instrumentId: string) =>
    apiFetch<{ status: string; source: string; bars_upserted: number; latest_close?: number }>(
      `/v1/market/refresh/${encodeURIComponent(instrumentId)}`,
      { method: 'POST' },
    ),

  getPortfolio: (base_currency: 'USD' | 'CNY' | 'USDT' = 'USD') =>
    apiFetch<PortPayload>(`/v1/port?base_currency=${base_currency}`),

  createTransaction: (payload: {
    instrument_id: string
    side: 'BUY' | 'SELL'
    quantity: number
    price: number
    notes?: string
  }) =>
    apiFetch<{ tx_id: string; settlement_date: string; currency: string }>('/v1/port/transactions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getBqlTemplates: () => apiFetch<{ templates: BqlTemplate[] }>('/v1/bql/templates'),

  executeBql: (mode: 'SQL' | 'PYTHON', code: string) =>
    apiFetch<BqlExecuteResult>('/v1/bql/execute', {
      method: 'POST',
      body: JSON.stringify({ mode, code }),
    }),
}

export function formatCompact(val: number | null | undefined, currency?: string): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—'
  const sign = val < 0 ? '-' : ''
  const abs = Math.abs(val)
  const sym = currency === 'CNY' ? '¥' : currency === 'USD' || currency === 'USDT' ? '$' : ''
  if (abs >= 1e12) return `${sign}${sym}${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}${sym}${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}${sym}${(abs / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${sign}${sym}${(abs / 1e3).toFixed(1)}K`
  return `${sign}${sym}${abs.toFixed(2)}`
}

export function formatPrice(val: number | null | undefined, currency?: string): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—'
  const sym = currency === 'CNY' ? '¥' : currency === 'USD' || currency === 'USDT' ? '$' : ''
  const digits = Math.abs(val) >= 10 ? 2 : 4
  return `${sym}${val.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`
}
