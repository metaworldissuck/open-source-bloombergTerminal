import { useEffect, useRef, useState } from 'react'
import { ColorType, HistogramSeries, LineSeries, createChart, type Time } from 'lightweight-charts'
import { Coins } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { PerpPayload } from '../types/terminal'

interface Props {
  paneId: string
  instrumentId: string
}

export function PerpModule({ paneId, instrumentId }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<PerpPayload | null>(null)
  const setPaneSecurity = useWorkspaceStore((s) => s.setPaneSecurity)

  useEffect(() => {
    let cancelled = false
    terminalApi
      .getPerp(instrumentId)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [instrumentId])

  useEffect(() => {
    const el = chartRef.current
    if (!el || !data?.history.length) return

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
      leftPriceScale: { visible: true, borderColor: '#1f2a3c' },
      timeScale: { borderColor: '#1f2a3c' },
      width: el.clientWidth,
      height: el.clientHeight,
    })

    const oiSeries = chart.addSeries(LineSeries, {
      color: '#38bdf8',
      lineWidth: 2,
      priceScaleId: 'left',
      title: 'Open Interest ($)',
    })
    oiSeries.setData(
      data.history.map((h) => ({ time: h.time as Time, value: h.open_interest_usd })),
    )

    const fundingSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: 'right',
      title: '8h Funding (bps)',
    })
    fundingSeries.setData(
      data.history.map((h) => ({
        time: h.time as Time,
        value: h.funding_bps,
        color: h.funding_bps >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(244, 63, 94, 0.7)',
      })),
    )

    chart.timeScale().fitContent()
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          chart.applyOptions({ width: entry.contentRect.width, height: entry.contentRect.height })
        }
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [data])

  if (!data) {
    return (
      <div className="p-4 font-mono-num text-xs text-slate-400 animate-pulse">
        Loading Crypto perpetual funding rates, Open Interest & CEX/DEX liquidity...
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11px]">
      <div className="px-3 py-1.5 bg-[#0a0f17] border-b border-[#1c2636] flex items-center justify-between flex-wrap gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <Coins className="w-4 h-4 text-amber-400" />
          <span className="font-mono-num font-bold text-amber-300">
            CRYPTO PERPETUALS, FUNDING, OI & ON-CHAIN TVL
          </span>
        </div>
        <span className="font-mono-num text-[10px] text-cyan-300">
          ACTIVE SERIES: {data.active_instrument_id} · 24/7 T+0
        </span>
      </div>

      {/* Funding Rate (bps) + Open Interest Dual-Axis Chart */}
      <div className="h-48 border-b border-[#1c2636] relative shrink-0">
        <div className="absolute top-1.5 left-3 z-10 font-mono-num text-[9.5px] text-slate-400 pointer-events-none">
          BLUE (LEFT): OPEN INTEREST USD · BARS (RIGHT): 8H FUNDING RATE (BPS)
        </div>
        <div ref={chartRef} className="w-full h-full" />
      </div>

      {/* Multi-Asset Crypto Derivatives & Liquidity Matrix */}
      <div className="flex-1 overflow-auto">
        <table className="term-table font-mono-num">
          <thead>
            <tr>
              <th className="text-left">Contract</th>
              <th className="text-right">Price</th>
              <th className="text-right">8h Fund</th>
              <th className="text-right">Ann Fund</th>
              <th className="text-right">Open Int</th>
              <th className="text-right">Basis</th>
              <th className="text-right">CEX 24h</th>
              <th className="text-right">DEX Share</th>
              <th className="text-right">TVL</th>
              <th className="text-right">Active Addr</th>
            </tr>
          </thead>
          <tbody>
            {data.markets.map((m) => (
              <tr
                key={m.instrument_id}
                onClick={() => setPaneSecurity(paneId, m.instrument_id)}
                className={`cursor-pointer ${
                  m.instrument_id === data.active_instrument_id ? 'bg-amber-500/10' : ''
                }`}
              >
                <td className="font-bold text-amber-300">{m.native_symbol}</td>
                <td className="text-right text-slate-100">{formatPrice(m.price, 'USD')}</td>
                <td
                  className={`text-right ${
                    m.funding_rate_bps >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {m.funding_rate_bps >= 0 ? '+' : ''}
                  {m.funding_rate_bps.toFixed(2)} bp
                </td>
                <td className="text-right text-cyan-300">{m.annualized_funding_pct.toFixed(1)}%</td>
                <td className="text-right text-slate-200">
                  {formatCompact(m.open_interest_usd, 'USD')}
                </td>
                <td className="text-right text-amber-200">{m.perp_basis_bps.toFixed(1)} bp</td>
                <td className="text-right text-slate-300">
                  {formatCompact(m.cex_volume_24h_usd, 'USD')}
                </td>
                <td className="text-right text-amber-300">{m.dex_share_pct}%</td>
                <td className="text-right text-emerald-300">
                  {m.tvl_usd > 0 ? formatCompact(m.tvl_usd, 'USD') : 'PoW L1'}
                </td>
                <td className="text-right text-slate-400">
                  {formatCompact(m.active_addresses_24h)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
