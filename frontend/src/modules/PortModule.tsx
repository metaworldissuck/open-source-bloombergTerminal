import { useEffect, useRef, useState } from 'react'
import { AreaSeries, ColorType, LineSeries, createChart, type Time } from 'lightweight-charts'
import { Lock, Plus, ShieldCheck } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import type { InstrumentSummary, PortPayload } from '../types/terminal'

export function PortModule() {
  const curveRef = useRef<HTMLDivElement>(null)
  const [baseCcy, setBaseCcy] = useState<'USD' | 'CNY' | 'USDT'>('USD')
  const [data, setData] = useState<PortPayload | null>(null)
  const [catalog, setCatalog] = useState<InstrumentSummary[]>([])
  const [showOrder, setShowOrder] = useState(false)
  const [orderInst, setOrderInst] = useState('EQ:US:AAPL')
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY')
  const [orderQty, setOrderQty] = useState('100')
  const [orderPx, setOrderPx] = useState('230')
  const [submitting, setSubmitting] = useState(false)

  const loadPortfolio = () => {
    terminalApi
      .getPortfolio(baseCcy)
      .then((res) => setData(res))
      .catch(() => {})
  }

  useEffect(() => {
    loadPortfolio()
  }, [baseCcy])

  useEffect(() => {
    terminalApi
      .listInstruments()
      .then((res) => setCatalog(res.items))
      .catch(() => {})
  }, [])

  // Render Portfolio Equity Curve & Underwater Drawdown Chart
  useEffect(() => {
    const el = curveRef.current
    if (!el || !data?.equity_curve?.length) return

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#080c12' },
        textColor: '#8d9db4',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: { vertLines: { color: '#141c29' }, horzLines: { color: '#141c29' } },
      rightPriceScale: { borderColor: '#1f2a3c' },
      leftPriceScale: { visible: true, borderColor: '#1f2a3c' },
      timeScale: { borderColor: '#1f2a3c' },
      width: el.clientWidth,
      height: el.clientHeight,
    })

    const eqSeries = chart.addSeries(LineSeries, {
      color: '#10b981',
      lineWidth: 2,
      priceScaleId: 'right',
      title: 'Indexed NAV',
    })
    eqSeries.setData(
      data.equity_curve.map((pt) => ({ time: pt.time as Time, value: pt.indexed_value })),
    )

    const ddSeries = chart.addSeries(AreaSeries, {
      lineColor: 'rgba(244, 63, 94, 0.75)',
      topColor: 'rgba(244, 63, 94, 0.05)',
      bottomColor: 'rgba(244, 63, 94, 0.30)',
      lineWidth: 1,
      priceScaleId: 'left',
      title: 'Drawdown %',
    })
    ddSeries.setData(
      data.equity_curve.map((pt) => ({ time: pt.time as Time, value: pt.drawdown_pct })),
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

  const submitOrder = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await terminalApi.createTransaction({
        instrument_id: orderInst,
        side: orderSide,
        quantity: Number(orderQty),
        price: Number(orderPx),
        notes: 'Logged via PORT terminal',
      })
      setShowOrder(false)
      loadPortfolio()
    } finally {
      setSubmitting(false)
    }
  }

  if (!data) {
    return (
      <div className="p-4 font-mono-num text-xs text-slate-400 animate-pulse">
        Computing multi-currency portfolio valuation, VaR & correlation matrix...
      </div>
    )
  }

  const { summary, risk, holdings, correlation_matrix } = data

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3 text-[11px]">
      {/* Header & Base Currency Toggle (USD / CNY / USDT) */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-[#1c2636]">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-amber-400" />
          <span className="font-semibold text-sm text-slate-100">{data.portfolio.name}</span>
          <span className="font-mono-num text-[10px] px-1.5 py-0.5 rounded bg-[#141d2b] text-slate-400">
            BM: {data.portfolio.benchmark_instrument_id}
          </span>
        </div>

        <div className="flex items-center gap-2 font-mono-num text-[10px]">
          <div className="flex rounded overflow-hidden border border-[#243247]">
            {(['USD', 'CNY', 'USDT'] as const).map((c) => (
              <button
                key={c}
                onClick={() => setBaseCcy(c)}
                className={`px-2 py-1 cursor-pointer ${
                  baseCcy === c ? 'bg-amber-500/20 text-amber-300 font-semibold' : 'text-slate-400'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowOrder((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 cursor-pointer"
          >
            <Plus className="w-3 h-3" />
            <span>LOG TRADE</span>
          </button>
        </div>
      </div>

      {/* Add Transaction Inline Drawer */}
      {showOrder && (
        <form
          onSubmit={submitOrder}
          className="bg-[#0e1520] border border-amber-500/40 rounded p-2.5 flex items-end flex-wrap gap-2 font-mono-num text-[11px]"
        >
          <div>
            <label className="block text-[9.5px] text-slate-400 mb-0.5">INSTRUMENT</label>
            <select
              value={orderInst}
              onChange={(e) => setOrderInst(e.target.value)}
              className="bg-[#070b11] border border-[#243247] rounded px-2 py-1 text-slate-200"
            >
              {catalog.map((c) => (
                <option key={c.instrument_id} value={c.instrument_id}>
                  {c.native_symbol} ({c.market} · {c.base_currency})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[9.5px] text-slate-400 mb-0.5">SIDE</label>
            <select
              value={orderSide}
              onChange={(e) => setOrderSide(e.target.value as 'BUY' | 'SELL')}
              className="bg-[#070b11] border border-[#243247] rounded px-2 py-1 text-slate-200"
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div>
            <label className="block text-[9.5px] text-slate-400 mb-0.5">QTY</label>
            <input
              type="number"
              step="any"
              value={orderQty}
              onChange={(e) => setOrderQty(e.target.value)}
              className="w-24 bg-[#070b11] border border-[#243247] rounded px-2 py-1 text-slate-200"
              required
            />
          </div>
          <div>
            <label className="block text-[9.5px] text-slate-400 mb-0.5">EXEC PRICE</label>
            <input
              type="number"
              step="any"
              value={orderPx}
              onChange={(e) => setOrderPx(e.target.value)}
              className="w-28 bg-[#070b11] border border-[#243247] rounded px-2 py-1 text-slate-200"
              required
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="px-3 py-1 rounded bg-amber-500 text-black font-bold hover:bg-amber-400 cursor-pointer"
          >
            {submitting ? 'SAVING...' : 'RECORD FILL'}
          </button>
        </form>
      )}

      {/* Portfolio Valuation & Quantitative Risk KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2 font-mono-num">
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">NAV ({baseCcy})</div>
          <div className="text-sm font-bold text-slate-100">
            {formatCompact(summary.total_market_value, baseCcy)}
          </div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">UNREALIZED P&L</div>
          <div
            className={`text-sm font-bold ${
              summary.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {summary.unrealized_pnl >= 0 ? '+' : ''}
            {formatCompact(summary.unrealized_pnl, baseCcy)} ({summary.unrealized_pnl_pct}%)
          </div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">SHARPE / SORTINO</div>
          <div className="text-sm font-bold text-cyan-300">
            {risk.sharpe_ratio} / {risk.sortino_ratio}
          </div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">MAX DRAWDOWN</div>
          <div className="text-sm font-bold text-rose-400">{risk.max_drawdown_pct}%</div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">BETA (vs SPY)</div>
          <div className="text-sm font-bold text-amber-300">{risk.beta_vs_benchmark}</div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">1D VaR (95%)</div>
          <div className="text-sm font-bold text-rose-300">
            -{risk.var_95_1d_pct}% ({formatCompact(risk.var_95_1d_value, baseCcy)})
          </div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">1D VaR (99%)</div>
          <div className="text-sm font-bold text-rose-400">
            -{risk.var_99_1d_pct}% ({formatCompact(risk.var_99_1d_value, baseCcy)})
          </div>
        </div>
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2">
          <div className="text-[9px] text-slate-500">ANN RET / VOL</div>
          <div className="text-sm font-bold text-slate-200">
            {risk.annualized_return_pct}% / {risk.annualized_volatility_pct}%
          </div>
        </div>
      </div>

      {/* Equity Curve & Underwater Drawdown Chart */}
      <div className="h-40 bg-[#0a0f17] border border-[#1c2636] rounded relative overflow-hidden">
        <div className="absolute top-1.5 left-3 z-10 font-mono-num text-[9.5px] text-slate-400 pointer-events-none">
          GREEN (RIGHT): 252D INDEXED EQUITY CURVE (BASE=100) · RED (LEFT): UNDERWATER DRAWDOWN (%)
        </div>
        <div ref={curveRef} className="w-full h-full" />
      </div>

      {/* Multi-Currency Holdings & T+1 Settlement Grid */}
      <div className="bg-[#0a0f17] border border-[#1c2636] rounded overflow-x-auto">
        <div className="px-2.5 py-1.5 bg-[#0f1622] border-b border-[#1c2636] flex items-center justify-between font-mono-num text-[10px] text-slate-400">
          <span>HOLDINGS & FX P&L ATTRIBUTION</span>
          <div className="flex items-center gap-3">
            {summary.currency_exposure.map((ce) => (
              <span key={ce.currency}>
                {ce.currency}: <strong className="text-cyan-300">{ce.weight_pct}%</strong>
              </span>
            ))}
          </div>
        </div>
        <table className="term-table font-mono-num">
          <thead>
            <tr>
              <th className="text-left">Symbol</th>
              <th className="text-left">Mkt / CCY</th>
              <th className="text-right">Qty (Sellable)</th>
              <th className="text-right">Avg Cost</th>
              <th className="text-right">Last Px</th>
              <th className="text-right">Value ({baseCcy})</th>
              <th className="text-right">Weight</th>
              <th className="text-right">Total P&L</th>
              <th className="text-right">FX P&L</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.instrument_id}>
                <td className="font-semibold text-amber-300">{h.native_symbol}</td>
                <td className="text-slate-400 text-[10px]">
                  {h.market} · {h.currency}
                </td>
                <td className="text-right text-slate-200">
                  {h.quantity}
                  {h.t1_locked_qty > 0 && (
                    <span
                      title={`${h.t1_locked_qty} shares locked under China A-Share T+1 settlement`}
                      className="ml-1 inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-rose-500/15 text-rose-300 text-[9px]"
                    >
                      <Lock className="w-2.5 h-2.5" />
                      T+1: {h.t1_locked_qty}
                    </span>
                  )}
                </td>
                <td className="text-right text-slate-400">
                  {formatPrice(h.avg_cost_native, h.currency)}
                </td>
                <td className="text-right text-slate-200">
                  {formatPrice(h.last_price_native, h.currency)}
                </td>
                <td className="text-right text-slate-100 font-semibold">
                  {formatCompact(h.market_value_base, baseCcy)}
                </td>
                <td className="text-right text-cyan-300">{h.weight_pct}%</td>
                <td
                  className={`text-right font-semibold ${
                    h.unrealized_pnl_base >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {h.unrealized_pnl_base >= 0 ? '+' : ''}
                  {formatCompact(h.unrealized_pnl_base, baseCcy)} ({h.unrealized_pnl_pct}%)
                </td>
                <td
                  className={`text-right ${
                    h.fx_pnl_base >= 0 ? 'text-emerald-300' : 'text-rose-300'
                  }`}
                >
                  {h.fx_pnl_base >= 0 ? '+' : ''}
                  {formatCompact(h.fx_pnl_base, baseCcy)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Asset Correlation Matrix Heatmap */}
      {correlation_matrix.symbols.length >= 2 && (
        <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5 overflow-x-auto">
          <div className="text-[10px] font-mono-num uppercase tracking-wider text-amber-400 mb-2">
            252D Cross-Asset Return Correlation Matrix (US · A-Shares · Crypto)
          </div>
          <table className="term-table font-mono-num">
            <thead>
              <tr>
                <th className="text-left">Asset</th>
                {correlation_matrix.symbols.map((sym) => (
                  <th key={sym} className="text-center">
                    {sym}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {correlation_matrix.symbols.map((rowSym, rIdx) => (
                <tr key={rowSym}>
                  <td className="font-semibold text-slate-200">{rowSym}</td>
                  {correlation_matrix.matrix[rIdx].map((val, cIdx) => {
                    const bg =
                      rIdx === cIdx
                        ? 'bg-slate-800/80 text-slate-400'
                        : val >= 0.6
                          ? 'bg-rose-500/25 text-rose-200'
                          : val >= 0.3
                            ? 'bg-amber-500/20 text-amber-200'
                            : val <= 0.1
                              ? 'bg-emerald-500/20 text-emerald-200'
                              : 'bg-sky-500/15 text-sky-200'
                    return (
                      <td key={`${rIdx}-${cIdx}`} className={`text-center font-semibold ${bg}`}>
                        {val.toFixed(2)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
