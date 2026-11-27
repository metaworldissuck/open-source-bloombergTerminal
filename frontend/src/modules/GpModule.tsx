import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import { formatPrice, terminalApi } from '../api/client'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { GpPayload } from '../types/terminal'

interface Props {
  instrumentId: string
}

const RANGES = ['1M', '3M', '6M', '1Y', 'ALL'] as const

export function GpModule({ instrumentId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const oscRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const lastCandleRef = useRef<GpPayload['candles'][number] | null>(null)

  const [range, setRange] = useState<(typeof RANGES)[number]>('1Y')
  const [timeframe, setTimeframe] = useState<'1d' | '1w'>('1d')
  const [showSma20, setShowSma20] = useState(true)
  const [showSma50, setShowSma50] = useState(true)
  const [showBb, setShowBb] = useState(false)
  const [showVolProfile, setShowVolProfile] = useState(true)
  const [oscMode, setOscMode] = useState<'OFF' | 'RSI' | 'MACD'>('MACD')
  const [data, setData] = useState<GpPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const liveTick = useWorkspaceStore((s) => s.liveTicks[instrumentId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    terminalApi
      .getGp(instrumentId, range, timeframe)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          lastCandleRef.current = res.candles[res.candles.length - 1] ?? null
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [instrumentId, range, timeframe])

  // Main Candlestick + Volume + Indicators + Event Markers Chart
  useEffect(() => {
    const el = containerRef.current
    if (!el || !data || data.candles.length === 0) return

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
      crosshair: {
        vertLine: { color: '#f59e0b', width: 1, style: 2 },
        horzLine: { color: '#f59e0b', width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: '#1f2a3c' },
      timeScale: { borderColor: '#1f2a3c', timeVisible: true },
      width: el.clientWidth,
      height: el.clientHeight,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderUpColor: '#10b981',
      borderDownColor: '#f43f5e',
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    })
    candleSeries.setData(
      data.candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )

    // Attach Event & China Limit-Up/Down Markers directly on candlesticks
    const markers: SeriesMarker<Time>[] = [
      ...data.events.map((ev) => ({
        time: ev.time as Time,
        position: 'aboveBar' as const,
        color:
          ev.event_type === 'EARNINGS'
            ? '#f59e0b'
            : ev.event_type === 'DIVIDEND'
              ? '#10b981'
              : '#38bdf8',
        shape: 'arrowDown' as const,
        text: ev.event_type.slice(0, 4),
      })),
      ...data.cn_limit_hits.map((h) => ({
        time: h.time as Time,
        position: h.type === 'LIMIT_UP' ? ('aboveBar' as const) : ('belowBar' as const),
        color: h.type === 'LIMIT_UP' ? '#f43f5e' : '#10b981',
        shape: 'circle' as const,
        text: h.label,
      })),
    ].sort((a, b) => String(a.time).localeCompare(String(b.time)))

    if (markers.length > 0) {
      createSeriesMarkers(candleSeries, markers)
    }

    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volSeries.setData(
      data.candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.28)' : 'rgba(244, 63, 94, 0.28)',
      })),
    )

    if (showSma20 && data.indicators.sma20?.length) {
      const s = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1, priceLineVisible: false })
      s.setData(data.indicators.sma20.map((p) => ({ time: p.time as Time, value: p.value })))
    }
    if (showSma50 && data.indicators.sma50?.length) {
      const s = chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1, priceLineVisible: false })
      s.setData(data.indicators.sma50.map((p) => ({ time: p.time as Time, value: p.value })))
    }
    if (showBb && data.indicators.bb_upper?.length && data.indicators.bb_lower?.length) {
      const u = chart.addSeries(LineSeries, {
        color: 'rgba(148, 163, 184, 0.45)',
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
      })
      u.setData(data.indicators.bb_upper.map((p) => ({ time: p.time as Time, value: p.value })))
      const l = chart.addSeries(LineSeries, {
        color: 'rgba(148, 163, 184, 0.45)',
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
      })
      l.setData(data.indicators.bb_lower.map((p) => ({ time: p.time as Time, value: p.value })))
    }

    chart.timeScale().fitContent()
    chartRef.current = chart
    candleSeriesRef.current = candleSeries

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
      chartRef.current = null
      candleSeriesRef.current = null
    }
  }, [data, showSma20, showSma50, showBb])

  // Lower Oscillator Sub-Chart (RSI 14 or MACD 12/26/9)
  useEffect(() => {
    const el = oscRef.current
    if (!el || !data || oscMode === 'OFF') return

    const oscChart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#070a10' },
        textColor: '#8d9db4',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 9,
      },
      grid: {
        vertLines: { color: '#111824' },
        horzLines: { color: '#111824' },
      },
      rightPriceScale: { borderColor: '#1f2a3c' },
      timeScale: { borderColor: '#1f2a3c', visible: false },
      width: el.clientWidth,
      height: el.clientHeight,
    })

    if (oscMode === 'RSI' && data.indicators.rsi14?.length) {
      const rsi = oscChart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1 })
      rsi.setData(data.indicators.rsi14.map((p) => ({ time: p.time as Time, value: p.value })))
    } else if (oscMode === 'MACD' && data.indicators.macd?.length) {
      const hist = oscChart.addSeries(HistogramSeries, { priceLineVisible: false })
      hist.setData(
        (data.indicators.macd_hist ?? []).map((p) => ({
          time: p.time as Time,
          value: p.value,
          color: p.value >= 0 ? 'rgba(16, 185, 129, 0.55)' : 'rgba(244, 63, 94, 0.55)',
        })),
      )
      const macdLine = oscChart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1, priceLineVisible: false })
      macdLine.setData(data.indicators.macd.map((p) => ({ time: p.time as Time, value: p.value })))
      const sigLine = oscChart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1, priceLineVisible: false })
      sigLine.setData((data.indicators.macd_signal ?? []).map((p) => ({ time: p.time as Time, value: p.value })))
    }

    oscChart.timeScale().fitContent()
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          oscChart.applyOptions({ width: entry.contentRect.width, height: entry.contentRect.height })
        }
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      oscChart.remove()
    }
  }, [data, oscMode])

  useEffect(() => {
    if (!liveTick || !candleSeriesRef.current || !lastCandleRef.current) return
    const last = lastCandleRef.current
    const updated = {
      time: last.time as Time,
      open: last.open,
      high: Math.max(last.high, liveTick.price),
      low: Math.min(last.low, liveTick.price),
      close: liveTick.price,
    }
    lastCandleRef.current = { ...last, ...updated, time: last.time }
    candleSeriesRef.current.update(updated)
  }, [liveTick])

  const latestRsi = data?.indicators.rsi14?.[data.indicators.rsi14.length - 1]?.value

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11px]">
      {/* Technical Toolbar */}
      <div className="px-2.5 py-1.5 bg-[#0a0f17] border-b border-[#1c2636] flex items-center justify-between flex-wrap gap-1.5 shrink-0">
        <div className="flex items-center gap-1 font-mono-num">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-1.5 py-0.5 rounded text-[10px] cursor-pointer ${
                range === r ? 'bg-amber-500/20 text-amber-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {r}
            </button>
          ))}
          <span className="mx-0.5 text-slate-700">|</span>
          {(['1d', '1w'] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-1.5 py-0.5 rounded text-[10px] uppercase cursor-pointer ${
                timeframe === tf ? 'bg-cyan-500/20 text-cyan-300 font-semibold' : 'text-slate-400'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 font-mono-num text-[10px] flex-wrap">
          <button
            onClick={() => setShowSma20((v) => !v)}
            className={`px-1.5 py-0.5 rounded border cursor-pointer ${
              showSma20 ? 'border-amber-500/50 bg-amber-500/15 text-amber-300' : 'border-[#223045] text-slate-500'
            }`}
          >
            SMA20
          </button>
          <button
            onClick={() => setShowSma50((v) => !v)}
            className={`px-1.5 py-0.5 rounded border cursor-pointer ${
              showSma50 ? 'border-sky-500/50 bg-sky-500/15 text-sky-300' : 'border-[#223045] text-slate-500'
            }`}
          >
            SMA50
          </button>
          <button
            onClick={() => setShowBb((v) => !v)}
            className={`px-1.5 py-0.5 rounded border cursor-pointer ${
              showBb ? 'border-slate-400/50 bg-slate-500/20 text-slate-200' : 'border-[#223045] text-slate-500'
            }`}
          >
            BB
          </button>
          <button
            onClick={() => setShowVolProfile((v) => !v)}
            className={`px-1.5 py-0.5 rounded border cursor-pointer ${
              showVolProfile ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300' : 'border-[#223045] text-slate-500'
            }`}
          >
            VP
          </button>
          <div className="flex rounded overflow-hidden border border-[#243247]">
            {(['MACD', 'RSI', 'OFF'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setOscMode(m)}
                className={`px-1.5 py-0.5 cursor-pointer ${
                  oscMode === m ? 'bg-cyan-500/20 text-cyan-300 font-semibold' : 'text-slate-500'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          {latestRsi !== undefined && (
            <span className="hidden sm:inline px-1.5 py-0.5 rounded bg-[#121a26] text-slate-300">
              RSI: <strong className="text-cyan-300">{latestRsi.toFixed(1)}</strong>
            </span>
          )}
        </div>
      </div>

      {/* Main Chart + Volume Profile */}
      <div className="flex-1 flex min-h-0 relative">
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0 relative">
            {loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#080c12]/80 font-mono-num text-xs text-slate-400">
                Loading {instrumentId} OHLCV & indicators...
              </div>
            )}
            <div ref={containerRef} className="w-full h-full" />
          </div>
          {oscMode !== 'OFF' && (
            <div className="h-20 border-t border-[#1c2636] relative shrink-0">
              <div className="absolute top-0.5 left-2 z-10 font-mono-num text-[9px] text-slate-500 pointer-events-none">
                {oscMode === 'RSI' ? 'RSI (14)' : 'MACD (12, 26, 9)'}
              </div>
              <div ref={oscRef} className="w-full h-full" />
            </div>
          )}
        </div>

        {showVolProfile && data && data.volume_profile.length > 0 && (
          <div className="w-24 bg-[#090d14] border-l border-[#1c2636] p-1.5 flex flex-col justify-between shrink-0">
            <div className="text-[9px] font-mono-num uppercase text-slate-500 text-center pb-1 border-b border-[#182232]">
              Vol Profile
            </div>
            <div className="flex-1 flex flex-col-reverse justify-between py-1 gap-0.5">
              {data.volume_profile.map((bucket, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-1 h-full"
                  title={`${formatPrice(bucket.price_low)}–${formatPrice(bucket.price_high)}: ${bucket.pct_of_max}%`}
                >
                  <div className="flex-1 h-2 bg-[#111824] rounded-xs overflow-hidden flex justify-end">
                    <div
                      className={bucket.is_poc ? 'bg-amber-400' : 'bg-sky-500/45'}
                      style={{ width: `${Math.max(4, bucket.pct_of_max)}%` }}
                    />
                  </div>
                  <span
                    className={`font-mono-num text-[8.5px] w-9 text-right ${
                      bucket.is_poc ? 'text-amber-300 font-bold' : 'text-slate-500'
                    }`}
                  >
                    {bucket.price_mid >= 1000
                      ? `${(bucket.price_mid / 1000).toFixed(1)}k`
                      : bucket.price_mid.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bottom Event Overlay Ribbon */}
      {data && (data.events.length > 0 || data.cn_limit_hits.length > 0) && (
        <div className="px-2.5 py-1 bg-[#0a0f17] border-t border-[#1c2636] flex items-center gap-2 overflow-x-auto shrink-0 font-mono-num text-[10px]">
          <span className="text-slate-500 shrink-0">EVENTS:</span>
          {data.events.map((ev) => (
            <span
              key={ev.event_id}
              title={ev.title}
              className="px-1.5 py-0.5 rounded bg-[#141d2b] border border-[#243247] text-slate-300 shrink-0"
            >
              <strong className="text-amber-300">{ev.event_type}</strong> {ev.time} · {ev.title.slice(0, 32)}
            </span>
          ))}
          {data.cn_limit_hits.map((h, i) => (
            <span
              key={i}
              className={`px-1.5 py-0.5 rounded shrink-0 ${
                h.type === 'LIMIT_UP' ? 'bg-rose-500/15 text-rose-300' : 'bg-emerald-500/15 text-emerald-300'
              }`}
            >
              {h.label} {h.time}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
