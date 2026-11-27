import { CommandBar } from './components/command/CommandBar'
import { StatusTickerBar } from './components/command/StatusTickerBar'
import { SplitPaneGrid } from './components/workspace/SplitPaneGrid'
import { useRealtimeStream } from './hooks/useRealtimeStream'

export default function App() {
  useRealtimeStream()

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#070a0f] text-[#e4eaf3]">
      <h1 className="sr-only">OpenTerm Quantitative Multi-Asset Financial Terminal</h1>
      <StatusTickerBar />
      <CommandBar />
      <SplitPaneGrid />
      <footer className="px-3 py-0.5 bg-[#05080d] border-t border-[#182232] flex items-center justify-between text-[10px] font-mono-num text-slate-500 shrink-0 select-none">
        <div className="flex items-center gap-3">
          <span>
            <strong className="text-amber-400">/</strong> Command
          </span>
          <span>
            <strong className="text-amber-400">Alt+1..4</strong> Focus Pane
          </span>
          <span>
            <strong className="text-amber-400">Alt+L</strong> Cycle Link Group
          </span>
          <span>
            <strong className="text-amber-400">F2/F3</strong> &lt;Equity&gt; / &lt;Crypto&gt;
          </span>
        </div>
        <div>DuckDB + Polars Lakehouse · US / CN A-Shares / Crypto Unified Engine</div>
      </footer>
    </div>
  )
}
