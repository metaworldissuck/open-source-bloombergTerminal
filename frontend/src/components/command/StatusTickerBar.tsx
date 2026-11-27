import { useEffect, useState } from 'react'
import { Activity, Radio } from 'lucide-react'
import { formatPrice, terminalApi } from '../../api/client'
import { useWorkspaceStore } from '../../store/workspaceStore'
import type { MarketStatusResponse } from '../../types/terminal'

export function StatusTickerBar() {
  const [status, setStatus] = useState<MarketStatusResponse | null>(null)
  const liveTicks = useWorkspaceStore((s) => s.liveTicks)
  const wsConnected = useWorkspaceStore((s) => s.wsConnected)
  const activePaneId = useWorkspaceStore((s) => s.activePaneId)
  const setPaneSecurity = useWorkspaceStore((s) => s.setPaneSecurity)

  useEffect(() => {
    let mounted = true
    const load = () => {
      terminalApi
        .getMarketStatus()
        .then((res) => {
          if (mounted) setStatus(res)
        })
        .catch(() => {})
    }
    load()
    const timer = window.setInterval(load, 30000)
    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [])

  const sessionOrder = ['US', 'CN_ASHARE', 'CRYPTO']

  return (
    <div className="flex items-center justify-between gap-3 px-3 py-1 bg-[#05080d] border-b border-[#1c2636] text-[11px] select-none overflow-x-auto">
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1.5 font-mono-num font-bold tracking-wider text-amber-400">
          <Activity className="w-3.5 h-3.5 text-amber-500" />
          <span>OPENTERM</span>
          <span className="text-[9px] text-slate-500 font-normal">v0.1</span>
        </div>

        <div className="h-3.5 w-px bg-[#1f2a3c]" />

        <div className="flex items-center gap-2.5">
          {sessionOrder.map((key) => {
            const s = status?.sessions?.[key]
            if (!s) return null
            return (
              <div key={key} className="flex items-center gap-1.5 text-[10.5px]">
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${
                    s.is_open ? 'bg-emerald-400' : 'bg-slate-600'
                  }`}
                />
                <span className="text-slate-400 font-medium">{s.label}</span>
                <span
                  className={`font-mono-num text-[10px] px-1 py-0.2 rounded ${
                    s.is_open
                      ? 'bg-emerald-500/10 text-emerald-300'
                      : 'bg-slate-800/80 text-slate-400'
                  }`}
                >
                  {s.status.replace('_', ' ')}
                </span>
                <span className="font-mono-num text-slate-500 hidden xl:inline">
                  {s.local_time}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Live Multi-Asset Ticker Tape */}
      <div className="flex items-center gap-3 shrink-0">
        {status?.fx?.map((f) => (
          <div key={f.pair} className="font-mono-num text-[10.5px] text-slate-400 hidden lg:flex items-center gap-1">
            <span className="text-slate-500">{f.pair}</span>
            <span className="text-cyan-300">{f.rate.toFixed(4)}</span>
          </div>
        ))}

        <div className="h-3.5 w-px bg-[#1f2a3c] hidden lg:block" />

        <div className="flex items-center gap-2.5">
          {status?.ticker_tape?.map((item) => {
            const live = liveTicks[item.instrument_id]
            const px = live ? live.price : item.price
            const chg = live ? live.change_pct : item.change_pct ?? 0
            const pos = chg >= 0
            return (
              <button
                key={item.instrument_id}
                onClick={() => setPaneSecurity(activePaneId, item.instrument_id)}
                title={`Load ${item.instrument_id} into active pane`}
                className="flex items-center gap-1.5 px-1.5 py-0.5 rounded hover:bg-[#151e2c] transition-colors cursor-pointer"
              >
                <span className="font-mono-num font-semibold text-slate-200">
                  {item.native_symbol}
                </span>
                <span className="font-mono-num text-slate-300">
                  {formatPrice(px, item.base_currency)}
                </span>
                <span
                  className={`font-mono-num text-[10px] ${
                    pos ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {pos ? '+' : ''}
                  {chg.toFixed(2)}%
                </span>
              </button>
            )
          })}
        </div>

        <div
          className={`flex items-center gap-1 font-mono-num text-[10px] px-1.5 py-0.5 rounded ${
            wsConnected
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-rose-500/10 text-rose-400'
          }`}
          title="WebSocket Live Stream Status"
        >
          <Radio className="w-3 h-3" />
          <span>{wsConnected ? 'LIVE' : 'SYNC'}</span>
        </div>
      </div>
    </div>
  )
}
