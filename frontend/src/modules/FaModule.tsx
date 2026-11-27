import { useEffect, useMemo, useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import { Calculator } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import type { DcfResult, FaPayload } from '../types/terminal'

interface Props {
  instrumentId: string
}

type StatementTab = 'IS' | 'BS' | 'CF' | 'DCF'

export function FaModule({ instrumentId }: Props) {
  const [periodMode, setPeriodMode] = useState<'FY' | 'Q'>('FY')
  const [tab, setTab] = useState<StatementTab>('IS')
  const [data, setData] = useState<FaPayload | null>(null)
  const [dcf, setDcf] = useState<DcfResult | null>(null)
  const [wacc, setWacc] = useState(9.5)
  const [termGrowth, setTermGrowth] = useState(3.0)
  const [fcfGrowth, setFcfGrowth] = useState(12.0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    terminalApi
      .getFa(instrumentId, periodMode)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setDcf(res.dcf_baseline)
          setWacc(Number((res.dcf_baseline.inputs.wacc * 100).toFixed(1)))
          setTermGrowth(Number((res.dcf_baseline.inputs.terminal_growth * 100).toFixed(1)))
          setFcfGrowth(Number((res.dcf_baseline.inputs.fcf_growth_5y * 100).toFixed(1)))
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load FA')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [instrumentId, periodMode])

  const recalcDcf = (nextWacc: number, nextTg: number, nextFcfG: number) => {
    setWacc(nextWacc)
    setTermGrowth(nextTg)
    setFcfGrowth(nextFcfG)
    terminalApi
      .calculateDcf({
        instrument_id: instrumentId,
        wacc: nextWacc / 100,
        terminal_growth: nextTg / 100,
        fcf_growth_5y: nextFcfG / 100,
      })
      .then((res) => setDcf(res))
      .catch(() => {})
  }

  const activeRows = useMemo(() => {
    if (!data || tab === 'DCF') return []
    return data.statements[tab] ?? []
  }, [data, tab])

  const columns = useMemo<ColumnDef<any>[]>(() => {
    if (!data) return []
    const baseCols: ColumnDef<any>[] = [
      {
        accessorKey: 'label',
        header: () => <span className="text-left block">Line Item ({data.reporting_currency})</span>,
        cell: (info) => (
          <span className="font-medium text-slate-200">{String(info.getValue())}</span>
        ),
      },
    ]

    for (const pkey of data.periods) {
      baseCols.push({
        id: pkey,
        header: () => <span className="text-right block">{pkey}</span>,
        cell: ({ row }) => {
          const cell = row.original.periods?.[pkey]
          if (!cell) return <span className="text-right block text-slate-600">—</span>
          const unit = row.original.unit
          const formatted =
            unit === 'per_share'
              ? formatPrice(cell.value, data.reporting_currency)
              : unit === 'shares'
                ? formatCompact(cell.value)
                : formatCompact(cell.value, data.reporting_currency)
          const growth = periodMode === 'FY' ? cell.yoy_growth : cell.qoq_growth
          return (
            <div className="text-right font-mono-num">
              <div className="text-slate-100">{formatted}</div>
              {growth !== null && growth !== undefined && (
                <div
                  className={`text-[9.5px] ${
                    growth >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {growth >= 0 ? '+' : ''}
                  {(growth * 100).toFixed(1)}% {periodMode === 'FY' ? 'YoY' : 'QoQ'}
                </div>
              )}
            </div>
          )
        },
      })
    }
    return baseCols
  }, [data, periodMode])

  const table = useReactTable({
    data: activeRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (loading) {
    return (
      <div className="p-4 text-xs font-mono-num text-slate-400 animate-pulse">
        Loading standardized financials & valuation multiples for {instrumentId}...
      </div>
    )
  }
  if (error || !data) {
    return <div className="p-4 text-xs font-mono-num text-rose-400">FA Error: {error}</div>
  }

  const m = data.multiples

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11.5px]">
      {/* Top Controls & Multiples Bar */}
      <div className="px-3 py-2 border-b border-[#1c2636] bg-[#0a0f17] space-y-2 shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-1">
            {(['IS', 'BS', 'CF', 'DCF'] as StatementTab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-2.5 py-1 rounded font-mono-num text-[10.5px] font-semibold cursor-pointer transition-colors ${
                  tab === t
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'bg-[#121a26] text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                {t === 'IS'
                  ? 'INCOME STMT'
                  : t === 'BS'
                    ? 'BALANCE SHEET'
                    : t === 'CF'
                      ? 'CASH FLOW'
                      : 'DCF MODEL'}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 font-mono-num text-[10px]">
            <span className="px-1.5 py-0.5 rounded bg-[#141d2b] text-cyan-300">
              {data.accounting_standard}
            </span>
            {tab !== 'DCF' && (
              <div className="flex rounded overflow-hidden border border-[#243247]">
                {(['FY', 'Q'] as const).map((pm) => (
                  <button
                    key={pm}
                    onClick={() => setPeriodMode(pm)}
                    className={`px-2 py-0.5 cursor-pointer ${
                      periodMode === pm
                        ? 'bg-cyan-500/20 text-cyan-200 font-semibold'
                        : 'bg-[#0c121b] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {pm === 'FY' ? 'ANNUAL' : 'QUARTERLY'}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Multiples KPI Strip */}
        <div className="grid grid-cols-4 md:grid-cols-8 gap-2 font-mono-num text-[10.5px] pt-1">
          {[
            ['P/E', m.pe != null ? `${m.pe}x` : '—'],
            ['EV/EBITDA', m.ev_ebitda != null ? `${m.ev_ebitda}x` : '—'],
            ['P/B', m.pb != null ? `${m.pb}x` : '—'],
            ['P/S', m.ps != null ? `${m.ps}x` : '—'],
            ['FCF YLD', m.fcf_yield_pct != null ? `${m.fcf_yield_pct}%` : '—'],
            ['GROSS MGN', m.gross_margin_pct != null ? `${m.gross_margin_pct}%` : '—'],
            ['NET MGN', m.net_margin_pct != null ? `${m.net_margin_pct}%` : '—'],
            ['ROE', m.roe_pct != null ? `${m.roe_pct}%` : '—'],
          ].map(([k, v]) => (
            <div key={k} className="bg-[#0e1520] border border-[#1b2638] rounded px-2 py-1">
              <div className="text-[9px] text-slate-500">{k}</div>
              <div className="text-slate-100 font-semibold">{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area: TanStack Table OR Interactive DCF Calculator */}
      {tab !== 'DCF' ? (
        <div className="flex-1 overflow-auto">
          <table className="term-table">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th key={header.id}>
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {dcf && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                {/* Interactive Assumptions */}
                <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-3 space-y-3">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono-num uppercase text-amber-400">
                    <Calculator className="w-3.5 h-3.5" />
                    <span>DCF Assumptions</span>
                  </div>

                  <label className="block space-y-1">
                    <div className="flex justify-between font-mono-num text-[11px]">
                      <span className="text-slate-400">WACC (Discount Rate)</span>
                      <span className="text-amber-300 font-semibold">{wacc.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min={5.5}
                      max={18.0}
                      step={0.5}
                      value={wacc}
                      onChange={(e) => recalcDcf(Number(e.target.value), termGrowth, fcfGrowth)}
                      className="w-full accent-amber-400 cursor-pointer"
                    />
                  </label>

                  <label className="block space-y-1">
                    <div className="flex justify-between font-mono-num text-[11px]">
                      <span className="text-slate-400">5Y FCF Growth Rate</span>
                      <span className="text-cyan-300 font-semibold">{fcfGrowth.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min={-5.0}
                      max={35.0}
                      step={1.0}
                      value={fcfGrowth}
                      onChange={(e) => recalcDcf(wacc, termGrowth, Number(e.target.value))}
                      className="w-full accent-cyan-400 cursor-pointer"
                    />
                  </label>

                  <label className="block space-y-1">
                    <div className="flex justify-between font-mono-num text-[11px]">
                      <span className="text-slate-400">Terminal Growth (g)</span>
                      <span className="text-emerald-300 font-semibold">
                        {termGrowth.toFixed(1)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={1.0}
                      max={5.5}
                      step={0.25}
                      value={termGrowth}
                      onChange={(e) => recalcDcf(wacc, Number(e.target.value), fcfGrowth)}
                      className="w-full accent-emerald-400 cursor-pointer"
                    />
                  </label>
                </div>

                {/* Valuation Output Summary */}
                <div className="lg:col-span-2 bg-[#0a0f17] border border-[#1c2636] rounded p-3 flex flex-col justify-between">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono-num">
                    <div className="bg-[#101724] p-2.5 rounded border border-[#1d283a]">
                      <div className="text-[9.5px] text-slate-500">IMPLIED FAIR VALUE</div>
                      <div className="text-base font-bold text-amber-300">
                        {formatPrice(dcf.outputs.implied_share_price, dcf.currency)}
                      </div>
                    </div>
                    <div className="bg-[#101724] p-2.5 rounded border border-[#1d283a]">
                      <div className="text-[9.5px] text-slate-500">SPOT PRICE</div>
                      <div className="text-base font-bold text-slate-100">
                        {formatPrice(dcf.outputs.current_price, dcf.currency)}
                      </div>
                    </div>
                    <div className="bg-[#101724] p-2.5 rounded border border-[#1d283a]">
                      <div className="text-[9.5px] text-slate-500">IMPLIED UPSIDE</div>
                      <div
                        className={`text-base font-bold ${
                          dcf.outputs.upside_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {dcf.outputs.upside_pct >= 0 ? '+' : ''}
                        {dcf.outputs.upside_pct.toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-[#101724] p-2.5 rounded border border-[#1d283a]">
                      <div className="text-[9.5px] text-slate-500">EQUITY VALUE</div>
                      <div className="text-base font-bold text-cyan-300">
                        {formatCompact(dcf.outputs.equity_value, dcf.currency)}
                      </div>
                    </div>
                  </div>

                  {/* 5Y FCF Projections */}
                  <div className="mt-3 overflow-x-auto">
                    <table className="term-table font-mono-num">
                      <thead>
                        <tr>
                          <th className="text-left">Year</th>
                          {dcf.projections.map((p) => (
                            <th key={p.year} className="text-right">
                              Yr +{p.year}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="text-slate-400">Projected FCF</td>
                          {dcf.projections.map((p) => (
                            <td key={p.year} className="text-right text-slate-200">
                              {formatCompact(p.projected_fcf, dcf.currency)}
                            </td>
                          ))}
                        </tr>
                        <tr>
                          <td className="text-slate-400">Present Value (PV)</td>
                          {dcf.projections.map((p) => (
                            <td key={p.year} className="text-right text-cyan-300">
                              {formatCompact(p.pv_fcf, dcf.currency)}
                            </td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* 5x5 Sensitivity Matrix */}
              <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-3 overflow-x-auto">
                <div className="text-[10px] font-mono-num uppercase tracking-wider text-slate-400 mb-2">
                  Implied Share Price Sensitivity Matrix — WACC (Rows) vs Terminal Growth (Columns)
                </div>
                <table className="term-table font-mono-num">
                  <thead>
                    <tr>
                      <th className="text-left">WACC \ g</th>
                      {dcf.sensitivity.terminal_growth_axis.map((tg) => (
                        <th key={tg} className="text-right">
                          {tg.toFixed(2)}%
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dcf.sensitivity.wacc_axis.map((wVal, rIdx) => (
                      <tr key={wVal}>
                        <td className="font-semibold text-amber-300">{wVal.toFixed(2)}%</td>
                        {dcf.sensitivity.implied_prices[rIdx].map((cellPx, cIdx) => {
                          const isCenter = rIdx === 2 && cIdx === 2
                          const aboveSpot = cellPx !== null && cellPx >= dcf.outputs.current_price
                          return (
                            <td
                              key={`${rIdx}-${cIdx}`}
                              className={`text-right ${
                                isCenter
                                  ? 'bg-amber-500/20 text-amber-200 font-bold border border-amber-400/50'
                                  : aboveSpot
                                    ? 'bg-emerald-500/10 text-emerald-300'
                                    : 'bg-rose-500/10 text-rose-300'
                              }`}
                            >
                              {cellPx !== null ? formatPrice(cellPx, dcf.currency) : 'N/A'}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
