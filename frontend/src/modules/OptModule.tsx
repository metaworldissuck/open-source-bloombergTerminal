import { useEffect, useState } from 'react'
import { FileText, Layers } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import type { OptPayload } from '../types/terminal'

interface Props {
  instrumentId: string
}

export function OptModule({ instrumentId }: Props) {
  const [data, setData] = useState<OptPayload | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    terminalApi
      .getOpt(instrumentId)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [instrumentId])

  if (loading || !data) {
    return (
      <div className="p-4 font-mono-num text-xs text-slate-400 animate-pulse">
        Loading US Options Chain, IV Skew & SEC 13F filings...
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3 text-[11px]">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#1c2636]">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-sky-400" />
          <span className="font-mono-num font-bold text-amber-300">
            {data.instrument.native_symbol} OPTIONS & SEC 13F
          </span>
          <span className="text-slate-400 text-[10.5px]">
            Spot: <strong className="text-slate-100">{formatPrice(data.spot_price, 'USD')}</strong> · Exp:{' '}
            <strong className="text-cyan-300">{data.expiration_date}</strong>
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono-num text-[10px]">
          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
            CALL OI: {formatCompact(data.summary.total_call_oi)}
          </span>
          <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300">
            PUT OI: {formatCompact(data.summary.total_put_oi)}
          </span>
          <span className="px-2 py-0.5 rounded bg-[#141d2b] text-amber-300">
            P/C RATIO: {data.summary.put_call_oi_ratio.toFixed(2)}
          </span>
          <span className="px-2 py-0.5 rounded bg-[#141d2b] text-cyan-300">
            ATM IV: {data.summary.atm_iv_pct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Straddle Chain: CALLS | STRIKE | PUTS */}
      <div className="bg-[#0a0f17] border border-[#1c2636] rounded overflow-x-auto">
        <table className="term-table font-mono-num">
          <thead>
            <tr>
              <th className="text-right text-emerald-400">Call OI</th>
              <th className="text-right text-emerald-400">IV%</th>
              <th className="text-right text-emerald-400">Delta</th>
              <th className="text-right text-emerald-400">Bid / Ask</th>
              <th className="text-center bg-[#151f2f] text-amber-300">STRIKE</th>
              <th className="text-left text-rose-400">Bid / Ask</th>
              <th className="text-right text-rose-400">Delta</th>
              <th className="text-right text-rose-400">IV%</th>
              <th className="text-right text-rose-400">Put OI</th>
            </tr>
          </thead>
          <tbody>
            {data.straddle_chain.map((row) => {
              const callItm = row.strike <= data.spot_price
              const putItm = row.strike >= data.spot_price
              return (
                <tr key={row.strike}>
                  <td className={`text-right ${callItm ? 'bg-emerald-500/5' : ''}`}>
                    {row.call ? formatCompact(row.call.oi) : '—'}
                  </td>
                  <td className={`text-right text-amber-300 ${callItm ? 'bg-emerald-500/5' : ''}`}>
                    {row.call ? `${row.call.iv_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className={`text-right text-cyan-300 ${callItm ? 'bg-emerald-500/5' : ''}`}>
                    {row.call ? row.call.delta.toFixed(2) : '—'}
                  </td>
                  <td className={`text-right text-emerald-300 ${callItm ? 'bg-emerald-500/5' : ''}`}>
                    {row.call ? `${row.call.bid.toFixed(2)} / ${row.call.ask.toFixed(2)}` : '—'}
                  </td>
                  <td className="text-center font-bold bg-[#141d2c] text-amber-200 border-x border-[#243247]">
                    ${row.strike.toFixed(1)}
                  </td>
                  <td className={`text-left text-rose-300 ${putItm ? 'bg-rose-500/5' : ''}`}>
                    {row.put ? `${row.put.bid.toFixed(2)} / ${row.put.ask.toFixed(2)}` : '—'}
                  </td>
                  <td className={`text-right text-cyan-300 ${putItm ? 'bg-rose-500/5' : ''}`}>
                    {row.put ? row.put.delta.toFixed(2) : '—'}
                  </td>
                  <td className={`text-right text-amber-300 ${putItm ? 'bg-rose-500/5' : ''}`}>
                    {row.put ? `${row.put.iv_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className={`text-right ${putItm ? 'bg-rose-500/5' : ''}`}>
                    {row.put ? formatCompact(row.put.oi) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Institutional 13F & SEC Filings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded overflow-x-auto">
          <div className="px-2.5 py-1.5 bg-[#0f1622] border-b border-[#1c2636] font-mono-num text-[10px] text-sky-300 uppercase">
            SEC Form 13F Top Institutional Ownership
          </div>
          <table className="term-table font-mono-num">
            <thead>
              <tr>
                <th className="text-left">Institution</th>
                <th className="text-right">% Out</th>
                <th className="text-right">Value</th>
                <th className="text-right">QoQ Shares</th>
              </tr>
            </thead>
            <tbody>
              {data.institutional_13f.map((h) => (
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

        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5 space-y-2">
          <div className="flex items-center gap-1.5 font-mono-num text-[10px] text-amber-300 uppercase">
            <FileText className="w-3.5 h-3.5" />
            <span>SEC Filings & Corporate Actions (10-K / 10-Q / Earnings)</span>
          </div>
          {data.sec_filings.map((f) => (
            <div key={f.event_id} className="border-l-2 border-sky-500/50 pl-2">
              <div className="font-mono-num text-[9.5px] text-slate-400">
                {f.date} · <span className="text-sky-300">{f.type}</span>
              </div>
              <div className="text-slate-200">{f.title}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
