import { useEffect, useState } from 'react'
import { ArrowLeftRight, ShieldAlert } from 'lucide-react'
import { formatCompact, formatPrice, terminalApi } from '../api/client'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { FlowPayload } from '../types/terminal'

interface Props {
  paneId: string
}

export function FlowModule({ paneId }: Props) {
  const [data, setData] = useState<FlowPayload | null>(null)
  const setPaneSecurity = useWorkspaceStore((s) => s.setPaneSecurity)

  useEffect(() => {
    let cancelled = false
    terminalApi
      .getFlow()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (!data) {
    return (
      <div className="p-4 font-mono-num text-xs text-slate-400 animate-pulse">
        Loading China A-Share Stock Connect (北向/南向资金) & 涨跌停 board monitor...
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3 text-[11px]">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#1c2636]">
        <div className="flex items-center gap-2">
          <ArrowLeftRight className="w-4 h-4 text-rose-400" />
          <span className="font-mono-num font-bold text-rose-300">
            CHINA A-SHARE FLOW & 涨跌停 MONITOR (沪深/北交所)
          </span>
        </div>
        <div className="flex flex-wrap gap-2 font-mono-num text-[10px]">
          <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300">
            北向 NORTHBOUND: {formatCompact(data.summary.northbound_net_today_cny, 'CNY')}
          </span>
          <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-300">
            南向 SOUTHBOUND: HK${(data.summary.southbound_net_today_hkd / 1e8).toFixed(2)}亿
          </span>
          <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300">
            T+1 SETTLEMENT ENFORCED
          </span>
        </div>
      </div>

      {/* 30D Stock Connect Northbound Flow Bar Chart */}
      <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5">
        <div className="flex justify-between font-mono-num text-[10px] text-slate-400 mb-1.5">
          <span>30D STOCK CONNECT NORTHBOUND DAILY NET FLOW (北向资金净流入 · CNY)</span>
          <span>Red = Net Inflow · Green = Net Outflow (A-Share Convention)</span>
        </div>
        <div className="flex items-end gap-1 h-20 bg-[#06090e] p-2 rounded border border-[#182232]">
          {data.flow_history.map((pt) => {
            const h = Math.max(10, Math.min(100, (Math.abs(pt.northbound_cny) / 1.4e9) * 100))
            return (
              <div
                key={pt.date}
                title={`${pt.date}: Northbound ${formatCompact(pt.northbound_cny, 'CNY')}`}
                className="flex-1 flex flex-col justify-end h-full"
              >
                <div
                  className={`w-full rounded-t-xs ${
                    pt.northbound_cny >= 0 ? 'bg-rose-400/80' : 'bg-emerald-400/80'
                  }`}
                  style={{ height: `${h}%` }}
                />
              </div>
            )
          })}
        </div>
      </div>

      {/* Board-Aware 涨跌停 Limit Monitor Table */}
      <div className="bg-[#0a0f17] border border-[#1c2636] rounded overflow-x-auto">
        <div className="px-2.5 py-1.5 bg-[#0f1622] border-b border-[#1c2636] flex items-center gap-1.5 font-mono-num text-[10px] text-amber-300 uppercase">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Multi-Board Price Limit Monitor (SSE Main ±10% · ChiNext/STAR ±20% · BSE ±30%)</span>
        </div>
        <table className="term-table font-mono-num">
          <thead>
            <tr>
              <th className="text-left">Ticker</th>
              <th className="text-left">Board</th>
              <th className="text-right">Last (CNY)</th>
              <th className="text-right">Chg %</th>
              <th className="text-right">涨停 Up</th>
              <th className="text-right">跌停 Down</th>
              <th className="text-right">Turnover</th>
              <th className="text-right">北向 Hold</th>
              <th className="text-right">北向 Today</th>
            </tr>
          </thead>
          <tbody>
            {data.board_monitor.map((r) => (
              <tr
                key={r.instrument_id}
                onClick={() => setPaneSecurity(paneId, r.instrument_id)}
                className="cursor-pointer"
              >
                <td>
                  <span className="font-bold text-amber-300">{r.yahoo_ticker}</span>{' '}
                  <span className="font-sans text-slate-300">{r.display_name_local}</span>
                </td>
                <td>
                  <span className="px-1.5 py-0.5 rounded bg-[#141d2b] text-cyan-300 text-[9.5px]">
                    {r.board} ±{r.limit_pct}%
                  </span>
                </td>
                <td className="text-right font-semibold text-slate-100">
                  {formatPrice(r.price, 'CNY')}
                </td>
                <td
                  className={`text-right font-semibold ${
                    r.change_pct >= 0 ? 'text-rose-400' : 'text-emerald-400'
                  }`}
                >
                  {r.change_pct >= 0 ? '+' : ''}
                  {r.change_pct.toFixed(2)}%
                </td>
                <td className="text-right text-rose-400">
                  ¥{r.limit_up_price.toFixed(2)}
                  {r.hit_limit_up && (
                    <span className="ml-1 px-1 rounded bg-rose-500 text-white text-[9px]">涨停</span>
                  )}
                </td>
                <td className="text-right text-emerald-400">
                  ¥{r.limit_down_price.toFixed(2)}
                  {r.hit_limit_down && (
                    <span className="ml-1 px-1 rounded bg-emerald-500 text-black text-[9px]">跌停</span>
                  )}
                </td>
                <td className="text-right text-slate-300">{r.turnover_rate_pct ?? '—'}%</td>
                <td className="text-right text-cyan-300">
                  {r.northbound_eligible ? `${r.northbound_hold_pct ?? 0}%` : 'N/A (BSE)'}
                </td>
                <td
                  className={`text-right ${
                    r.northbound_net_flow_cny >= 0 ? 'text-rose-300' : 'text-emerald-300'
                  }`}
                >
                  {r.northbound_eligible ? formatCompact(r.northbound_net_flow_cny, 'CNY') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* CSRC & Exchange Announcements */}
      <div className="bg-[#0a0f17] border border-[#1c2636] rounded p-2.5 space-y-2">
        <div className="font-mono-num text-[10px] text-rose-300 uppercase">
          CSRC / SSE / SZSE / BSE Exchange Announcements (交易所公告)
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {data.exchange_notices.map((n) => (
            <div key={n.event_id} className="border-l-2 border-rose-500/50 pl-2">
              <div className="font-mono-num text-[9.5px] text-slate-400">
                {n.date} · <strong className="text-amber-300">{n.symbol} {n.name_cn}</strong> · {n.type}
              </div>
              <div className="text-slate-200">{n.title}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
