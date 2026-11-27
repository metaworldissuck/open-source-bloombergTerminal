import { useEffect, useRef, useState } from 'react'
import { ColorType, LineSeries, createChart, type Time } from 'lightweight-charts'
import { Plus, X } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import type { CompPayload, InstrumentSummary } from '../types/terminal'

interface Props {
  instrumentIds: string[]
  onChangeIds: (next: string[]) => void
}

const LINE_COLORS = ['#f59e0b', '#38bdf8', '#10b981', '#f43f5e', '#a78bfa', '#fb923c']

export function CompModule({ instrumentIds, onChangeIds }: Props) {
  const chartElRef = useRef<HTMLDivElement>(null)
  const [baseCcy, setBaseCcy] = useState<'USD' | 'CNY'>('USD')
  const [lookback, setLookback] = useState<number>(180)
  const [data, setData] = useState<CompPayload | null>(null)
  const [catalog, setCatalog] = useState<InstrumentSummary[]>([])
  const [addSelection, setAddSelection] = useState('')

  useEffect(() => {
    terminalApi
      .listInstruments()
      .then((res) => setCatalog(res.items))
      .catch(() => {})
  }, [])

  const idsKey = instrumentIds.join(',')

  useEffect(() => {
    let cancelled = false
    if (!instrumentIds.length) return
    terminalApi
      .getComp(instrumentIds, baseCcy, lookback)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [idsKey, baseCcy, lookback])

  useEffect(() => {
    const el = chartElRef.current
    if (!el || !data) return

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#080c12' },
        textColor: '#8d9db4',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#141c29' },
        horzLines: { color: '#141c29' },
      },
      rightPriceScale: { borderColor: '#1f2a3c' },
      timeScale: { borderColor: '#1f2a3c' },
      width: el.clientWidth,
      height: el.clientHeight,
    })

    data.peers.forEach((peer, idx) => {
      const seriesData = data.indexed_series[peer.instrument_id]
      if (!seriesData?.length) return
      const line = chart.addSeries(LineSeries, {
        color: LINE_COLORS[idx % LINE_COLORS.length],
        lineWidth: 2,
        title: peer.native_symbol,
      })
      line.setData(seriesData.map((pt) => ({ time: pt.time as Time, value: pt.value })))
    })

    chart.timeScale().fitContent()
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) chart.applyOptions({ width, height })
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [data])

  const addPeer = () => {
    if (!addSelection || instrumentIds.includes(addSelection)) return
    onChangeIds([...instrumentIds, addSelection])
    setAddSelection('')
  }

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11px]">
      {/* Controls */}
      <div className="px-3 py-1.5 bg-[#0a0f17] border-b border-[#1c2636] flex items-center justify-between flex-wrap gap-2 shrink-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          {instrumentIds.map((iid, idx) => (
            <span
              key={iid}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#141d2b] border border-[#243247] font-mono-num text-[10px]"
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: LINE_COLORS[idx % LINE_COLORS.length] }}
              />
              <span className="text-slate-200">{iid.split(':').pop()}</span>
              {instrumentIds.length > 1 && (
                <button
                  onClick={() => onChangeIds(instrumentIds.filter((x) => x !== iid))}
                  className="text-slate-500 hover:text-rose-400 cursor-pointer"
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              )}
            </span>
          ))}

          <div className="flex items-center gap-1">
            <select
              value={addSelection}
              onChange={(e) => setAddSelection(e.target.value)}
              className="bg-[#0e1520] border border-[#243247] rounded px-1.5 py-0.5 text-[10px] font-mono-num text-slate-300 outline-none"
            >
              <option value="">+ Add Peer...</option>
              {catalog
                .filter((c) => !instrumentIds.includes(c.instrument_id))
                .map((c) => (
                  <option key={c.instrument_id} value={c.instrument_id}>
                    {c.native_symbol} ({c.market})
                  </option>
                ))}
            </select>
            <button
              onClick={addPeer}
              className="p-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 cursor-pointer"
              title="Add security to comparison"
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono-num text-[10px]">
          <div className="flex rounded overflow-hidden border border-[#243247]">
            {(['USD', 'CNY'] as const).map((c) => (
              <button
                key={c}
                onClick={() => setBaseCcy(c)}
                className={`px-2 py-0.5 cursor-pointer ${
                  baseCcy === c ? 'bg-amber-500/20 text-amber-300 font-semibold' : 'text-slate-400'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="flex rounded overflow-hidden border border-[#243247]">
            {[60, 180, 365].map((d) => (
              <button
                key={d}
                onClick={() => setLookback(d)}
                className={`px-2 py-0.5 cursor-pointer ${
                  lookback === d ? 'bg-cyan-500/20 text-cyan-300 font-semibold' : 'text-slate-400'
                }`}
              >
                {d}D
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Indexed Return Chart (Base = 100 in Base CCY) */}
      <div className="h-48 border-b border-[#1c2636] relative shrink-0">
        <div className="absolute top-1.5 left-2.5 z-10 font-mono-num text-[9.5px] text-slate-400 pointer-events-none">
          INDEXED PERFORMANCE (BASE = 100 · NORMALIZED TO {baseCcy})
        </div>
        <div ref={chartElRef} className="w-full h-full" />
      </div>

      {/* Side-by-Side Fundamental & Risk Matrix */}
      <div className="flex-1 overflow-auto">
        <table className="term-table font-mono-num">
          <thead>
            <tr>
              <th className="text-left">Ticker</th>
              <th className="text-left">Mkt</th>
              <th className="text-right">Price ({baseCcy})</th>
              <th className="text-right">Mkt Cap ({baseCcy})</th>
              <th className="text-right">Rev ({baseCcy})</th>
              <th className="text-right">Rev YoY</th>
              <th className="text-right">P/E</th>
              <th className="text-right">EV/EBITDA</th>
              <th className="text-right">Net Mgn</th>
              <th className="text-right">Period Ret</th>
              <th className="text-right">Ann Vol</th>
              <th className="text-right">Max DD</th>
            </tr>
          </thead>
          <tbody>
            {data?.peers.map((p, idx) => (
              <tr key={p.instrument_id}>
                <td className="font-semibold text-slate-100">
                  <span
                    className="inline-block w-2 h-2 rounded-full mr-1.5"
                    style={{ backgroundColor: LINE_COLORS[idx % LINE_COLORS.length] }}
                  />
                  {p.native_symbol}
                </td>
                <td className="text-slate-400 text-[10px]">{p.market}</td>
                <td className="text-right text-slate-200">{formatPrice(p.price_base, baseCcy)}</td>
                <td className="text-right text-slate-200">
                  {formatCompact(p.market_cap_base, baseCcy)}
                </td>
                <td className="text-right text-slate-300">
                  {formatCompact(p.revenue_base, baseCcy)}
                </td>
                <td
                  className={`text-right ${
                    (p.revenue_yoy_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {p.revenue_yoy_pct != null ? `${p.revenue_yoy_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="text-right text-cyan-300">{p.pe != null ? `${p.pe}x` : '—'}</td>
                <td className="text-right text-cyan-300">
                  {p.ev_ebitda != null ? `${p.ev_ebitda}x` : '—'}
                </td>
                <td className="text-right text-slate-300">
                  {p.net_margin_pct != null ? `${p.net_margin_pct}%` : '—'}
                </td>
                <td
                  className={`text-right font-semibold ${
                    p.return_period_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {p.return_period_pct >= 0 ? '+' : ''}
                  {p.return_period_pct}%
                </td>
                <td className="text-right text-amber-300">{p.ann_vol_pct}%</td>
                <td className="text-right text-rose-400">{p.max_drawdown_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
