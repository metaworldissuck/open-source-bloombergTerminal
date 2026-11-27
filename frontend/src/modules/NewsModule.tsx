import { useEffect, useState } from 'react'
import { Newspaper, Search } from 'lucide-react'
import { terminalApi } from '../api/client'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { NewsPayload } from '../types/terminal'

interface Props {
  paneId: string
  instrumentId?: string | null
  filterByActive?: boolean
}

export function NewsModule({ paneId, instrumentId }: Props) {
  const [scopeTicker, setScopeTicker] = useState(false)
  const [sentiment, setSentiment] = useState('')
  const [language, setLanguage] = useState('')
  const [keyword, setKeyword] = useState('')
  const [data, setData] = useState<NewsPayload | null>(null)
  const setPaneSecurity = useWorkspaceStore((s) => s.setPaneSecurity)

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      terminalApi
        .getNews({
          instrument_id: scopeTicker ? instrumentId : null,
          sentiment: sentiment || undefined,
          language: language || undefined,
          keyword: keyword || undefined,
        })
        .then((res) => {
          if (!cancelled) setData(res)
        })
        .catch(() => {})
    }, 120)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [scopeTicker, instrumentId, sentiment, language, keyword])

  return (
    <div className="h-full flex flex-col overflow-hidden text-[11.5px]">
      {/* Filter Toolbar */}
      <div className="px-3 py-1.5 bg-[#0a0f17] border-b border-[#1c2636] flex items-center justify-between flex-wrap gap-2 shrink-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <div className="flex items-center bg-[#06090e] border border-[#243247] rounded px-2 py-0.5 gap-1.5">
            <Search className="w-3 h-3 text-slate-500" />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Filter headlines / filings..."
              className="bg-transparent text-slate-200 placeholder-slate-500 text-[11px] outline-none w-36"
            />
          </div>

          {instrumentId && (
            <button
              onClick={() => setScopeTicker((v) => !v)}
              className={`px-2 py-0.5 rounded font-mono-num text-[10px] border cursor-pointer ${
                scopeTicker
                  ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                  : 'bg-[#121a26] border-[#223045] text-slate-400'
              }`}
            >
              {scopeTicker ? `ONLY ${instrumentId.split(':').pop()}` : 'ALL MARKETS'}
            </button>
          )}

          <select
            value={sentiment}
            onChange={(e) => setSentiment(e.target.value)}
            className="bg-[#121a26] border border-[#223045] rounded px-1.5 py-0.5 font-mono-num text-[10px] text-slate-300 outline-none"
          >
            <option value="">SENTIMENT: ALL</option>
            <option value="BULLISH">BULLISH</option>
            <option value="NEUTRAL">NEUTRAL</option>
            <option value="BEARISH">BEARISH</option>
          </select>

          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-[#121a26] border border-[#223045] rounded px-1.5 py-0.5 font-mono-num text-[10px] text-slate-300 outline-none"
          >
            <option value="">LANG: ALL</option>
            <option value="en">EN (US/CRYPTO)</option>
            <option value="zh">ZH (A-SHARES)</option>
          </select>
        </div>

        {data && (
          <div className="flex items-center gap-2 font-mono-num text-[10px]">
            <span className="text-emerald-400">BULL {data.sentiment_summary.bullish}</span>
            <span className="text-slate-400">NEUT {data.sentiment_summary.neutral}</span>
            <span className="text-rose-400">BEAR {data.sentiment_summary.bearish}</span>
            <span className="px-1.5 py-0.5 rounded bg-[#141d2b] text-cyan-300">
              AVG {data.sentiment_summary.avg_score >= 0 ? '+' : ''}
              {data.sentiment_summary.avg_score.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* Live Feed */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#161f2e]">
        {data?.items.length === 0 && (
          <div className="p-6 text-center text-slate-500 font-mono-num text-xs">
            No matching news or filings found.
          </div>
        )}
        {data?.items.map((item) => {
          const badgeStyle =
            item.sentiment_label === 'BULLISH'
              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
              : item.sentiment_label === 'BEARISH'
                ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                : 'bg-slate-700/40 text-slate-300 border-slate-600/40'

          return (
            <article
              key={item.news_id}
              className="px-3 py-2.5 hover:bg-[#111824] transition-colors space-y-1"
            >
              <div className="flex items-center justify-between gap-2 font-mono-num text-[10px]">
                <div className="flex items-center gap-2 text-slate-400">
                  <Newspaper className="w-3 h-3 text-amber-400 shrink-0" />
                  <span className="text-amber-300/90 font-medium">{item.source}</span>
                  <span>{item.published_at_utc.slice(0, 16).replace('T', ' ')} UTC</span>
                </div>
                <span className={`px-1.5 py-0.2 rounded border text-[9.5px] ${badgeStyle}`}>
                  {item.sentiment_label} ({item.sentiment_score >= 0 ? '+' : ''}
                  {item.sentiment_score.toFixed(2)})
                </span>
              </div>

              <h3 className="text-[12px] font-semibold text-slate-100 leading-snug">
                {item.title}
              </h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">{item.summary}</p>

              <div className="flex items-center gap-1.5 pt-0.5 flex-wrap">
                {item.instrument_ids.map((iid) => (
                  <button
                    key={iid}
                    onClick={() => setPaneSecurity(paneId, iid)}
                    className="px-1.5 py-0.5 rounded bg-[#141d2b] hover:bg-amber-500/20 border border-[#243247] font-mono-num text-[9.5px] text-cyan-300 hover:text-amber-300 cursor-pointer transition-colors"
                  >
                    {iid}
                  </button>
                ))}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
