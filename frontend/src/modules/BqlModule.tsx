import { useEffect, useRef, useState } from 'react'
import { ColorType, LineSeries, createChart, type Time } from 'lightweight-charts'
import { Code2, Play } from 'lucide-react'
import { terminalApi } from '../api/client'
import type { BqlExecuteResult, BqlTemplate } from '../types/terminal'

export function BqlModule() {
  const chartElRef = useRef<HTMLDivElement>(null)
  const [templates, setTemplates] = useState<BqlTemplate[]>([])
  const [mode, setMode] = useState<'SQL' | 'PYTHON'>('SQL')
  const [code, setCode] = useState('')
  const [result, setResult] = useState<BqlExecuteResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    terminalApi
      .getBqlTemplates()
      .then((res) => {
        setTemplates(res.templates)
        if (res.templates[0]) {
          setMode(res.templates[0].mode)
          setCode(res.templates[0].code)
        }
      })
      .catch(() => {})
  }, [])

  const runQuery = async () => {
    if (!code.trim()) return
    setRunning(true)
    setError(null)
    try {
      const res = await terminalApi.executeBql(mode, code)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed')
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  // Render strategy equity curve if Python backtest returned chart points
  useEffect(() => {
    const el = chartElRef.current
    if (!el || !result?.chart?.length) return

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

    const strat = chart.addSeries(LineSeries, {
      color: '#10b981',
      lineWidth: 2,
      title: 'Strategy',
    })
    strat.setData(result.chart.map((pt) => ({ time: pt.time as Time, value: pt.strategy })))

    const bm = chart.addSeries(LineSeries, {
      color: '#64748b',
      lineWidth: 1,
      lineStyle: 2,
      title: 'Buy & Hold',
    })
    bm.setData(result.chart.map((pt) => ({ time: pt.time as Time, value: pt.benchmark })))

    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [result])

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11px]">
      {/* Top Bar: Mode + Templates + Execute */}
      <div className="px-3 py-1.5 bg-[#0a0f17] border-b border-[#1c2636] flex items-center justify-between flex-wrap gap-2 shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex rounded overflow-hidden border border-[#243247] font-mono-num text-[10px]">
            {(['SQL', 'PYTHON'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-2.5 py-1 cursor-pointer ${
                  mode === m
                    ? 'bg-amber-500/20 text-amber-300 font-semibold'
                    : 'bg-[#0e1520] text-slate-400'
                }`}
              >
                {m === 'SQL' ? 'DuckDB SQL' : 'Python / Polars'}
              </button>
            ))}
          </div>

          <select
            onChange={(e) => {
              const tpl = templates.find((t) => t.id === e.target.value)
              if (tpl) {
                setMode(tpl.mode)
                setCode(tpl.code)
              }
            }}
            className="bg-[#121a26] border border-[#243247] rounded px-2 py-1 text-[10.5px] font-mono-num text-cyan-300 outline-none max-w-xs"
            defaultValue=""
          >
            <option value="" disabled>
              Load Quant Template...
            </option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                [{t.mode}] {t.name}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={() => void runQuery()}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black font-mono-num text-[10.5px] font-bold cursor-pointer disabled:opacity-50"
        >
          <Play className="w-3 h-3 fill-current" />
          <span>{running ? 'RUNNING...' : 'RUN (Ctrl+Enter)'}</span>
        </button>
      </div>

      {/* Editor */}
      <div className="h-44 border-b border-[#1c2636] bg-[#06090e] flex flex-col shrink-0">
        <div className="px-3 py-1 bg-[#0b1019] border-b border-[#182232] flex items-center justify-between text-[9.5px] font-mono-num text-slate-500">
          <span className="flex items-center gap-1">
            <Code2 className="w-3 h-3 text-amber-400" />
            BQL-LITE SANDBOX · Tables: dim_instruments, fact_ohlcv, fact_financials, fact_cn_microstructure, fact_crypto_metrics, fact_fx_rates
          </span>
          {result && (
            <span className="text-emerald-400">
              {result.row_count} rows in {result.elapsed_ms} ms
            </span>
          )}
        </div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault()
              void runQuery()
            }
          }}
          spellCheck={false}
          className="flex-1 w-full bg-transparent text-amber-100 font-mono-num text-[11.5px] p-2.5 outline-none resize-none leading-relaxed"
        />
      </div>

      {/* Results & Optional Equity Curve */}
      <div className="flex-1 overflow-auto flex flex-col">
        {error && (
          <div className="m-3 p-2.5 rounded bg-rose-500/15 border border-rose-500/35 text-rose-300 font-mono-num text-[11px]">
            EXECUTION ERROR: {error}
          </div>
        )}

        {result?.stdout && (
          <pre className="mx-3 mt-2 p-2 rounded bg-[#0b1018] border border-[#1c2636] text-emerald-300 font-mono-num text-[10.5px] whitespace-pre-wrap">
            {result.stdout}
          </pre>
        )}

        {result?.chart && result.chart.length > 0 && (
          <div className="h-44 border-b border-[#1c2636] relative shrink-0 mt-2">
            <div className="absolute top-1 left-3 z-10 font-mono-num text-[9.5px] text-emerald-300 pointer-events-none">
              BACKTEST EQUITY CURVE (GREEN: STRATEGY vs GRAY: BUY & HOLD, BASE=100)
            </div>
            <div ref={chartElRef} className="w-full h-full" />
          </div>
        )}

        {result && result.columns.length > 0 && (
          <div className="flex-1 overflow-auto">
            <table className="term-table font-mono-num">
              <thead>
                <tr>
                  {result.columns.map((col) => (
                    <th key={col} className="text-left">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, idx) => (
                  <tr key={idx}>
                    {result.columns.map((col) => (
                      <td key={col} className="text-slate-200">
                        {row[col] === null || row[col] === undefined ? '—' : String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!result && !error && (
          <div className="p-6 text-center font-mono-num text-xs text-slate-500">
            Select a template or write DuckDB SQL / Python Polars code above and press{' '}
            <kbd className="px-1.5 py-0.5 rounded bg-[#141d2b] text-amber-300">Ctrl+Enter</kbd> to
            execute.
          </div>
        )}
      </div>
    </div>
  )
}
