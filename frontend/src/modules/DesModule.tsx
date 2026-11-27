import { useEffect, useState } from 'react'
import { Building2, Calendar, Layers, ShieldAlert, TrendingUp } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { DesPayload } from '../types/terminal'

interface Props {
  instrumentId: string
}

export function DesModule({ instrumentId }: Props) {
  const [data, setData] = useState<DesPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const liveTick = useWorkspaceStore((s) => s.liveTicks[instrumentId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    terminalApi
      .getDes(instrumentId)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load DES')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [instrumentId])

  if (loading) {
    return (
      <div className="p-4 text-xs font-mono-num text-slate-400 animate-pulse">
        Loading security master & microstructure for {instrumentId}...
      </div>
    )
  }
  if (error || !data) {
    return <div className="p-4 text-xs font-mono-num text-rose-400">DES Error: {error}</div>
  }

  const { instrument, quote, valuation, microstructure, recent_events } = data
  const ccy = instrument.base_currency
  const px = liveTick ? liveTick.price : quote.price
  const chg = liveTick ? liveTick.change : quote.change
  const chgPct = liveTick ? liveTick.change_pct : quote.change_pct
  const pos = chg >= 0
  const rangePct =
    quote.high_52w > quote.low_52w
      ? Math.max(0, Math.min(100, ((px - quote.low_52w) / (quote.high_52w - quote.low_52w)) * 100))
      : 50

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3 text-[11.5px]">
      {/* Header Banner */}
      <div className="flex flex-wrap items-start justify-between gap-2 pb-2.5 border-b border-[#1c2636]">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono-num text-base font-bold text-amber-300">
              {instrument.native_symbol}
            </span>
            <span className="text-sm font-semibold text-slate-100">{instrument.display_name}</span>
            {instrument.display_name_local && (
              <span className="text-sm text-cyan-300 font-medium">
                {instrument.display_name_local}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap text-[10px] font-mono-num">
            <span className="px-1.5 py-0.5 rounded bg-[#141c29] text-slate-300 border border-[#243247]">
              {instrument.instrument_id}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-300">
              {instrument.exchange_mic}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300">
              {instrument.settlement_rule.replace(/_/g, ' ')}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-[#141c29] text-slate-400">
              {instrument.sector} · {instrument.industry}
            </span>
          </div>
        </div>

        <div className="text-right font-mono-num">
          <div className="text-lg font-bold text-slate-100 leading-tight">
            {formatPrice(px, ccy)}
            <span className="ml-1.5 text-[10px] text-slate-500 font-normal">{ccy}</span>
          </div>
          <div className={`text-xs font-semibold ${pos ? 'text-emerald-400' : 'text-rose-400'}`}>
            {pos ? '+' : ''}
            {chg.toFixed(2)} ({pos ? '+' : ''}
            {chgPct.toFixed(2)}%)
          </div>
        </div>
      </div>

      {/* Quote & Valuation Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <section className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5">
          <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase tracking-wider text-amber-400 mb-2">
            <TrendingUp className="w-3 h-3" />
            <span>Market Snapshot & 52W Range</span>
          </div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5 font-mono-num text-[11px]">
            <div>
              <div className="text-[9.5px] text-slate-500">OPEN</div>
              <div className="text-slate-200">{formatPrice(quote.open, ccy)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">HIGH / LOW</div>
              <div className="text-slate-200">
                {formatPrice(quote.high)} / {formatPrice(quote.low)}
              </div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">VWAP</div>
              <div className="text-cyan-300">{formatPrice(quote.vwap, ccy)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">VOLUME</div>
              <div className="text-slate-200">{formatCompact(liveTick ? liveTick.volume : quote.volume)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">30D AVG VOL</div>
              <div className="text-slate-300">{formatCompact(quote.avg_volume_30d)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">LOT SIZE</div>
              <div className="text-slate-300">{instrument.lot_size}</div>
            </div>
          </div>
          <div className="mt-2.5">
            <div className="flex justify-between text-[10px] font-mono-num text-slate-400 mb-1">
              <span>52W LOW {formatPrice(quote.low_52w, ccy)}</span>
              <span>52W HIGH {formatPrice(quote.high_52w, ccy)}</span>
            </div>
            <div className="h-1.5 bg-[#182232] rounded overflow-hidden relative">
              <div
                className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 opacity-50"
                style={{ width: '100%' }}
              />
              <div
                className="absolute top-0 bottom-0 w-1.5 bg-white rounded shadow"
                style={{ left: `calc(${rangePct}% - 3px)` }}
              />
            </div>
          </div>
        </section>

        <section className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5">
          <div className="flex items-center justify-between text-[10px] font-mono-num uppercase tracking-wider text-amber-400 mb-2">
            <div className="flex items-center gap-1.5">
              <Building2 className="w-3 h-3" />
              <span>Capital Structure & Multiples</span>
            </div>
            <span className="text-slate-500">{valuation.accounting_standard}</span>
          </div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5 font-mono-num text-[11px]">
            <div>
              <div className="text-[9.5px] text-slate-500">MKT CAP</div>
              <div className="text-slate-100 font-semibold">
                {formatCompact(valuation.market_cap, ccy)}
              </div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">ENTERPRISE VAL</div>
              <div className="text-slate-200">{formatCompact(valuation.enterprise_value, ccy)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">P/E · EV/EBITDA</div>
              <div className="text-cyan-300">
                {valuation.pe_ratio ? `${valuation.pe_ratio}x` : '—'} ·{' '}
                {valuation.ev_ebitda ? `${valuation.ev_ebitda}x` : '—'}
              </div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">CASH & EQUIV</div>
              <div className="text-emerald-300">{formatCompact(valuation.cash_and_equiv, ccy)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">TOTAL DEBT</div>
              <div className="text-rose-300">{formatCompact(valuation.total_debt, ccy)}</div>
            </div>
            <div>
              <div className="text-[9.5px] text-slate-500">DIV YLD · BETA</div>
              <div className="text-slate-200">
                {valuation.dividend_yield_pct != null ? `${valuation.dividend_yield_pct}%` : '—'} ·{' '}
                {valuation.beta_5y ?? '—'}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Market-Specific Microstructure Deep Section */}
      {instrument.market === 'CN_ASHARE' && (
        <section className="bg-[#0a0f17] border border-rose-500/25 rounded p-2.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase tracking-wider text-rose-300">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>China A-Share Microstructure (沪深/北交所)</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono-num">
              <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300">
                BOARD: {microstructure.board} (±{(Number(microstructure.limit_pct) * 100).toFixed(0)}%)
              </span>
              <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">
                T+1 SELL LOCK
              </span>
              {microstructure.is_northbound_eligible && (
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300">
                  STOCK CONNECT 北向
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono-num text-[11px]">
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">涨停 LIMIT-UP</div>
              <div className="text-rose-400 font-bold">
                ¥{Number(microstructure.limit_up_price).toFixed(2)}
              </div>
              <div className="text-[9.5px] text-slate-400">
                {microstructure.hit_limit_up ? 'AT LIMIT-UP!' : `${microstructure.pct_from_limit_up}% headroom`}
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">跌停 LIMIT-DOWN</div>
              <div className="text-emerald-400 font-bold">
                ¥{Number(microstructure.limit_down_price).toFixed(2)}
              </div>
              <div className="text-[9.5px] text-slate-400">
                {microstructure.hit_limit_down ? 'AT LIMIT-DOWN!' : `${microstructure.pct_from_limit_down}% buffer`}
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">北向持股 NORTHBOUND</div>
              <div className="text-cyan-300 font-bold">
                {microstructure.northbound_hold_pct != null ? `${microstructure.northbound_hold_pct}%` : '—'}
              </div>
              <div className="text-[9.5px] text-slate-400">
                Net: {formatCompact(microstructure.northbound_net_flow_cny, 'CNY')}
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">换手率 · 融资余额</div>
              <div className="text-slate-100 font-bold">
                {microstructure.turnover_rate_pct ?? '—'}%
              </div>
              <div className="text-[9.5px] text-slate-400">
                Margin: {formatCompact(microstructure.margin_buy_balance_cny, 'CNY')}
              </div>
            </div>
          </div>

          {Array.isArray(microstructure.northbound_history) &&
            microstructure.northbound_history.length > 0 && (
              <div>
                <div className="text-[9.5px] font-mono-num text-slate-400 mb-1">
                  20D NORTHBOUND DAILY NET FLOW (北向资金净流入)
                </div>
                <div className="flex items-end gap-1 h-14 bg-[#070b11] p-1.5 rounded border border-[#182232]">
                  {microstructure.northbound_history.map((pt: any) => {
                    const v = Number(pt.net_flow_cny || 0)
                    const h = Math.max(10, Math.min(100, (Math.abs(v) / 8e8) * 100))
                    return (
                      <div
                        key={pt.date}
                        title={`${pt.date}: ${formatCompact(v, 'CNY')}`}
                        className="flex-1 flex flex-col justify-end h-full"
                      >
                        <div
                          className={`w-full rounded-t-xs ${v >= 0 ? 'bg-rose-400/80' : 'bg-emerald-400/80'}`}
                          style={{ height: `${h}%` }}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
        </section>
      )}

      {instrument.market === 'CRYPTO' && (
        <section className="bg-[#0a0f17] border border-amber-500/25 rounded p-2.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase tracking-wider text-amber-300">
              <Layers className="w-3.5 h-3.5" />
              <span>Crypto Derivatives, Liquidity & On-Chain Microstructure</span>
            </div>
            <span className="font-mono-num text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
              24/7 CONTINUOUS · {microstructure.contract_type}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono-num text-[11px]">
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">8H FUNDING RATE</div>
              <div
                className={`font-bold ${
                  (microstructure.funding_rate ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {microstructure.funding_rate != null
                  ? `${(microstructure.funding_rate * 100).toFixed(4)}%`
                  : '—'}
              </div>
              <div className="text-[9.5px] text-slate-400">
                Ann: {microstructure.annualized_funding_pct ?? '—'}%
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">OPEN INTEREST</div>
              <div className="text-cyan-300 font-bold">
                {formatCompact(microstructure.open_interest_usd, 'USD')}
              </div>
              <div className="text-[9.5px] text-slate-400">
                Basis: {microstructure.perp_basis_bps ?? 0} bps
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">CEX / DEX 24H VOL</div>
              <div className="text-slate-100 font-bold">
                {formatCompact(microstructure.cex_volume_24h_usd, 'USD')}
              </div>
              <div className="text-[9.5px] text-amber-300">
                DEX Share: {microstructure.dex_share_pct ?? 0}%
              </div>
            </div>
            <div className="bg-[#101723] p-2 rounded border border-[#1d283a]">
              <div className="text-[9.5px] text-slate-500">DEFILLAMA TVL / ADDR</div>
              <div className="text-emerald-300 font-bold">
                {microstructure.tvl_usd ? formatCompact(microstructure.tvl_usd, 'USD') : 'PoW L1'}
              </div>
              <div className="text-[9.5px] text-slate-400">
                Active: {formatCompact(microstructure.active_addresses_24h)}/24h
              </div>
            </div>
          </div>
        </section>
      )}

      {instrument.market === 'US' && (
        <section className="bg-[#0a0f17] border border-sky-500/25 rounded p-2.5 space-y-2.5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase tracking-wider text-sky-300">
              <Layers className="w-3.5 h-3.5" />
              <span>US Equity Microstructure · Extended Hours, Options & SEC 13F</span>
            </div>
            <div className="flex items-center gap-2 font-mono-num text-[10.5px]">
              <span className="text-slate-400">
                CIK: <strong className="text-slate-200">{microstructure.cik ?? '—'}</strong>
              </span>
              <span className="text-slate-400">
                PRE:{' '}
                <strong className="text-cyan-300">
                  {formatPrice(microstructure.pre_market_price, 'USD')}
                </strong>
              </span>
              <span className="text-slate-400">
                POST:{' '}
                <strong className="text-amber-300">
                  {formatPrice(microstructure.post_market_price, 'USD')}
                </strong>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {/* Top 13F Institutional Holders */}
            {Array.isArray(microstructure.institutional_13f) &&
              microstructure.institutional_13f.length > 0 && (
                <div className="overflow-x-auto border border-[#1a2333] rounded">
                  <div className="px-2 py-1 bg-[#101724] text-[9.5px] font-mono-num uppercase text-slate-400 border-b border-[#1a2333]">
                    Top Institutional 13F Ownership
                  </div>
                  <table className="term-table font-mono-num">
                    <thead>
                      <tr>
                        <th className="text-left">Institution</th>
                        <th className="text-right">% Out</th>
                        <th className="text-right">Value</th>
                        <th className="text-right">QoQ Chg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {microstructure.institutional_13f.map((h: any) => (
                        <tr key={h.institution_cik}>
                          <td className="font-sans text-slate-200">{h.institution_name}</td>
                          <td className="text-right text-cyan-300">{h.pct_of_shares_out}%</td>
                          <td className="text-right text-slate-300">
                            {formatCompact(h.market_value_usd, 'USD')}
                          </td>
                          <td
                            className={`text-right ${
                              h.qoq_share_change >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {h.qoq_share_change >= 0 ? '+' : ''}
                            {formatCompact(h.qoq_share_change)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

            {/* ATM Options Chain Snapshot */}
            {Array.isArray(microstructure.options_chain) &&
              microstructure.options_chain.length > 0 && (
                <div className="overflow-x-auto border border-[#1a2333] rounded max-h-48 overflow-y-auto">
                  <div className="px-2 py-1 bg-[#101724] text-[9.5px] font-mono-num uppercase text-slate-400 border-b border-[#1a2333]">
                    Near-Term Options Chain Snapshot (IV & Greeks)
                  </div>
                  <table className="term-table font-mono-num">
                    <thead>
                      <tr>
                        <th className="text-left">Type</th>
                        <th className="text-right">Strike</th>
                        <th className="text-right">Last</th>
                        <th className="text-right">IV</th>
                        <th className="text-right">Delta</th>
                        <th className="text-right">OI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {microstructure.options_chain.slice(0, 10).map((o: any) => (
                        <tr key={o.contract_symbol}>
                          <td
                            className={
                              o.option_type === 'CALL'
                                ? 'text-emerald-400 font-semibold'
                                : 'text-rose-400 font-semibold'
                            }
                          >
                            {o.option_type}
                          </td>
                          <td className="text-right text-slate-200">${o.strike.toFixed(1)}</td>
                          <td className="text-right text-slate-300">${o.last_price.toFixed(2)}</td>
                          <td className="text-right text-amber-300">
                            {(o.implied_volatility * 100).toFixed(1)}%
                          </td>
                          <td className="text-right text-cyan-300">{o.delta.toFixed(2)}</td>
                          <td className="text-right text-slate-400">{formatCompact(o.open_interest)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </div>
        </section>
      )}

      {/* Business Description & Corporate Events */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 bg-[#0a0f17] border border-[#1c2636] rounded p-2.5">
          <div className="text-[10px] font-mono-num uppercase tracking-wider text-slate-400 mb-1.5">
            Profile Summary
          </div>
          <p className="text-slate-300 leading-relaxed text-[11.5px]">{instrument.description}</p>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5">
          <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase tracking-wider text-slate-400 mb-1.5">
            <Calendar className="w-3 h-3" />
            <span>Key Filings & Events</span>
          </div>
          <div className="space-y-1.5">
            {recent_events.map((ev) => (
              <div key={ev.event_id} className="text-[11px] border-l-2 border-amber-500/50 pl-2">
                <div className="flex items-center gap-1.5 font-mono-num text-[9.5px] text-slate-400">
                  <span>{ev.date}</span>
                  <span className="text-amber-300">{ev.event_type}</span>
                </div>
                <div className="text-slate-200 leading-snug">{ev.title}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
