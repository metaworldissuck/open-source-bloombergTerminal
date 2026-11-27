import { useState } from 'react'
import { Link2, Maximize2, RefreshCw, Unlink } from 'lucide-react'
import { formatPrice, terminalApi } from '../../api/client'
import { BqlModule } from '../../modules/BqlModule'
import { CompModule } from '../../modules/CompModule'
import { DesModule } from '../../modules/DesModule'
import { FaModule } from '../../modules/FaModule'
import { FlowModule } from '../../modules/FlowModule'
import { GpModule } from '../../modules/GpModule'
import { NewsModule } from '../../modules/NewsModule'
import { OptModule } from '../../modules/OptModule'
import { PerpModule } from '../../modules/PerpModule'
import { PortModule } from '../../modules/PortModule'
import { useWorkspaceStore, type PaneState } from '../../store/workspaceStore'
import type { FunctionCode, LinkGroup } from '../../types/terminal'

const FUNCTIONS: FunctionCode[] = [
  'DES',
  'GP',
  'FA',
  'COMP',
  'OPT',
  'FLOW',
  'PERP',
  'NEWS',
  'PORT',
  'BQL',
]

const LINK_STYLES: Record<LinkGroup, { badge: string; label: string }> = {
  A: { badge: 'bg-sky-500/20 text-sky-300 border-sky-500/40', label: 'GRP A' },
  B: { badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40', label: 'GRP B' },
  C: { badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', label: 'GRP C' },
  NONE: { badge: 'bg-slate-800/80 text-slate-500 border-slate-700/60', label: 'FREE' },
}

interface Props {
  pane: PaneState
  isActive: boolean
}

export function PaneShell({ pane, isActive }: Props) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const setActivePane = useWorkspaceStore((s) => s.setActivePane)
  const setPaneFunction = useWorkspaceStore((s) => s.setPaneFunction)
  const setPaneCompList = useWorkspaceStore((s) => s.setPaneCompList)
  const cycleLinkGroup = useWorkspaceStore((s) => s.cycleLinkGroup)
  const layout = useWorkspaceStore((s) => s.layout)
  const setLayout = useWorkspaceStore((s) => s.setLayout)
  const liveTick = useWorkspaceStore((s) => s.liveTicks[pane.instrumentId])

  const linkCfg = LINK_STYLES[pane.linkGroup]
  const symbolShort = pane.instrumentId.split(':').pop() ?? pane.instrumentId
  const isGlobalFn = pane.fn === 'PORT' || pane.fn === 'BQL' || pane.fn === 'FLOW'

  const handleLiveSync = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (refreshing) return
    setRefreshing(true)
    try {
      await terminalApi.refreshLive(pane.instrumentId)
      setRefreshKey((k) => k + 1)
    } catch {
      // fallback silently to cached DuckDB lakehouse
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <section
      onMouseDown={() => {
        if (!isActive) setActivePane(pane.id)
      }}
      className={`pane-surface rounded flex flex-col min-h-0 min-w-0 overflow-hidden transition-colors ${
        isActive ? 'pane-active' : ''
      }`}
    >
      {/* Pane Top Chrome */}
      <div
        className={`px-2 py-1 border-b flex items-center justify-between gap-1.5 shrink-0 select-none overflow-x-auto ${
          isActive
            ? 'bg-[#121a27] border-amber-500/35'
            : 'bg-[#0b1018] border-[#1c2636]'
        }`}
      >
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`font-mono-num text-[10px] font-bold px-1.5 py-0.2 rounded ${
              isActive ? 'bg-amber-500 text-black' : 'bg-[#1a2434] text-slate-400'
            }`}
            title={`Pane ${pane.index} (Alt+${pane.index})`}
          >
            P{pane.index}
          </span>

          <button
            onClick={(e) => {
              e.stopPropagation()
              cycleLinkGroup(pane.id)
            }}
            title="Cycle Pane Link Group (Alt+L)"
            className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded border font-mono-num text-[9.5px] font-semibold cursor-pointer ${linkCfg.badge}`}
          >
            {pane.linkGroup === 'NONE' ? (
              <Unlink className="w-2.5 h-2.5" />
            ) : (
              <Link2 className="w-2.5 h-2.5" />
            )}
            <span>{linkCfg.label}</span>
          </button>

          {!isGlobalFn && (
            <div className="flex items-center gap-1.5 font-mono-num text-[10.5px]">
              <span className="font-bold text-amber-300">{symbolShort}</span>
              {liveTick && (
                <>
                  <span className="text-slate-200 hidden xl:inline">
                    {formatPrice(liveTick.price)}
                  </span>
                  <span
                    className={`text-[9.5px] hidden 2xl:inline ${
                      liveTick.change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {liveTick.change_pct >= 0 ? '+' : ''}
                    {liveTick.change_pct.toFixed(2)}%
                  </span>
                </>
              )}
              <button
                onClick={handleLiveSync}
                title="Pull latest live bars from yfinance / AkShare / CCXT into DuckDB"
                className="p-0.5 rounded text-slate-500 hover:text-emerald-400 cursor-pointer"
              >
                <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
              </button>
            </div>
          )}
        </div>

        {/* Function Tabs + Maximize */}
        <div className="flex items-center gap-0.5 shrink-0">
          {FUNCTIONS.map((f) => (
            <button
              key={f}
              onClick={(e) => {
                e.stopPropagation()
                setPaneFunction(pane.id, f)
              }}
              className={`px-1.5 py-0.5 rounded font-mono-num text-[9.5px] font-semibold cursor-pointer transition-colors ${
                pane.fn === f
                  ? 'bg-amber-500/20 text-amber-300'
                  : 'text-slate-500 hover:text-slate-200 hover:bg-[#172131]'
              }`}
            >
              {f}
            </button>
          ))}
          <button
            onClick={(e) => {
              e.stopPropagation()
              setActivePane(pane.id)
              setLayout(layout === '1x1' ? '2x2' : '1x1')
            }}
            title={layout === '1x1' ? 'Restore Multi-Pane Grid' : 'Maximize Pane'}
            className="ml-0.5 p-1 rounded text-slate-500 hover:text-amber-300 hover:bg-[#172131] cursor-pointer"
          >
            <Maximize2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Pane Module Body */}
      <div className="flex-1 min-h-0 overflow-hidden" key={`${pane.fn}-${pane.instrumentId}-${refreshKey}`}>
        {pane.fn === 'DES' && <DesModule instrumentId={pane.instrumentId} />}
        {pane.fn === 'GP' && <GpModule instrumentId={pane.instrumentId} />}
        {pane.fn === 'FA' && <FaModule instrumentId={pane.instrumentId} />}
        {pane.fn === 'COMP' && (
          <CompModule
            instrumentIds={pane.compInstrumentIds}
            onChangeIds={(next) => setPaneCompList(pane.id, next)}
          />
        )}
        {pane.fn === 'OPT' && <OptModule instrumentId={pane.instrumentId} />}
        {pane.fn === 'FLOW' && <FlowModule paneId={pane.id} />}
        {pane.fn === 'PERP' && <PerpModule paneId={pane.id} instrumentId={pane.instrumentId} />}
        {pane.fn === 'NEWS' && <NewsModule paneId={pane.id} instrumentId={pane.instrumentId} />}
        {pane.fn === 'PORT' && <PortModule />}
        {pane.fn === 'BQL' && <BqlModule />}
        {pane.fn === 'HELP' && (
          <div className="p-4 font-mono-num text-xs text-slate-300 space-y-2 overflow-y-auto h-full">
            <div className="text-amber-300 font-bold">OPENTERM MNEMONIC COMMAND REFERENCE</div>
            <p>AAPL US &lt;Equity&gt; DES — US Equity Description, Options & 13F</p>
            <p>AAPL US &lt;Equity&gt; OPT — Full US Options Straddle Chain, IV & SEC Filings</p>
            <p>600519 CH &lt;Equity&gt; FA — China A-Share CAS Financials & DCF Model</p>
            <p>FLOW — China A-Share Stock Connect (北向/南向) & 涨跌停 Board Monitor</p>
            <p>BTC-USD &lt;Crypto&gt; GP — 24/7 Candlesticks, Indicators, RSI/MACD & Volume Profile</p>
            <p>BTC-USD &lt;Crypto&gt; PERP — Crypto Funding Rates, OI, Basis & CEX/DEX TVL</p>
            <p>AAPL US, NVDA US, 600519 CH, BTC-USD COMP — FX-Normalized Peer Comparison</p>
            <p>NEWS / PORT / BQL — Bilingual Sentiment Feed, Multi-CCY Risk, DuckDB/Python Console</p>
          </div>
        )}
      </div>
    </section>
  )
}
