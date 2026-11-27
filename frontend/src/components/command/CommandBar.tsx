import { useEffect, useRef, useState } from 'react'
import { Columns2, Grid2x2, Rows2, Square, Terminal, X } from 'lucide-react'
import { terminalApi } from '../../api/client'
import { useWorkspaceStore } from '../../store/workspaceStore'
import type { AutocompleteSuggestion, LayoutMode } from '../../types/terminal'

const QUICK_COMMANDS = [
  { label: 'AAPL DES', cmd: 'AAPL US <Equity> DES' },
  { label: '600519 FA', cmd: '600519 CH <Equity> FA' },
  { label: '300750 DES', cmd: '300750 CH <Equity> DES' },
  { label: 'BTC GP', cmd: 'BTC-USD <Crypto> GP' },
  { label: 'COMP', cmd: 'AAPL US, NVDA US, 600519 CH, BTC-USD COMP' },
  { label: 'PORT', cmd: 'PORT' },
  { label: 'BQL', cmd: 'BQL' },
  { label: 'NEWS', cmd: 'NEWS' },
]

export function CommandBar() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [historyIdx, setHistoryIdx] = useState(-1)

  const layout = useWorkspaceStore((s) => s.layout)
  const setLayout = useWorkspaceStore((s) => s.setLayout)
  const activePaneId = useWorkspaceStore((s) => s.activePaneId)
  const panes = useWorkspaceStore((s) => s.panes)
  const commandHistory = useWorkspaceStore((s) => s.commandHistory)
  const lastError = useWorkspaceStore((s) => s.lastError)
  const clearError = useWorkspaceStore((s) => s.clearError)
  const executeCommand = useWorkspaceStore((s) => s.executeCommand)
  const focusPaneByIndex = useWorkspaceStore((s) => s.focusPaneByIndex)
  const cycleLinkGroup = useWorkspaceStore((s) => s.cycleLinkGroup)

  const activePane = panes.find((p) => p.id === activePaneId) ?? panes[0]

  // Global keyboard shortcut manager
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const inEditable =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
        setOpen(true)
        return
      }

      if (e.key === '/' && !inEditable) {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
        return
      }

      // Bloomberg Yellow-Key Asset Class shortcuts while command bar is focused
      if (document.activeElement === inputRef.current) {
        if (e.key === 'F2') {
          e.preventDefault()
          setInput((v) => `${v.trim()} <Equity> `)
          return
        }
        if (e.key === 'F3') {
          e.preventDefault()
          setInput((v) => `${v.trim()} <Crypto> `)
          return
        }
        if (e.key === 'F4') {
          e.preventDefault()
          setInput((v) => `${v.trim()} <FX> `)
          return
        }
      }

      // Pane navigation: Alt+1..4, Alt+L (cycle link group)
      if (e.altKey && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault()
        focusPaneByIndex(Number(e.key))
        return
      }
      if (e.altKey && e.key.toLowerCase() === 'l') {
        e.preventDefault()
        cycleLinkGroup(useWorkspaceStore.getState().activePaneId)
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
        e.preventDefault()
        setLayout(useWorkspaceStore.getState().layout === '1x2' ? '2x2' : '1x2')
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [focusPaneByIndex, cycleLinkGroup, setLayout])

  // Fetch context-aware autocomplete suggestions
  useEffect(() => {
    if (!open) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      terminalApi
        .autocomplete(input, activePane.instrumentId)
        .then((res) => {
          if (!cancelled) {
            setSuggestions(res.suggestions)
            setSelectedIdx(0)
          }
        })
        .catch(() => {})
    }, 90)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [input, open, activePane.instrumentId])

  const submit = async (cmdText: string) => {
    const trimmed = cmdText.trim()
    if (!trimmed) return
    setOpen(false)
    setInput('')
    setHistoryIdx(-1)
    await executeCommand(trimmed)
    inputRef.current?.blur()
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false)
      setInput('')
      inputRef.current?.blur()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (open && suggestions.length > 0) {
        setSelectedIdx((i) => (i + 1) % suggestions.length)
      } else if (commandHistory.length > 0) {
        const next = Math.max(-1, historyIdx - 1)
        setHistoryIdx(next)
        setInput(next === -1 ? '' : commandHistory[next])
      }
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (open && suggestions.length > 0 && input.length > 0) {
        setSelectedIdx((i) => (i - 1 + suggestions.length) % suggestions.length)
      } else if (commandHistory.length > 0) {
        const next = Math.min(commandHistory.length - 1, historyIdx + 1)
        setHistoryIdx(next)
        setInput(commandHistory[next])
      }
      return
    }
    if (e.key === 'Tab' && open && suggestions[selectedIdx]) {
      e.preventDefault()
      setInput(suggestions[selectedIdx].insert_text)
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (!input.trim() && open && suggestions[selectedIdx]) {
        void submit(suggestions[selectedIdx].insert_text)
      } else {
        void submit(input)
      }
    }
  }

  const layouts: Array<{ id: LayoutMode; icon: typeof Square; title: string }> = [
    { id: '1x1', icon: Square, title: 'Single Pane (1x1)' },
    { id: '1x2', icon: Columns2, title: 'Vertical Split (1x2)' },
    { id: '2x1', icon: Rows2, title: 'Horizontal Split (2x1)' },
    { id: '2x2', icon: Grid2x2, title: 'Quad Terminal (2x2)' },
  ]

  return (
    <header className="relative z-30 bg-[#0b1018] border-b border-[#1f2a3c] px-3 py-1.5">
      <div className="flex items-center gap-2.5">
        {/* Global Mnemonic Input */}
        <div className="relative flex-1 max-w-2xl">
          <div className="flex items-center bg-[#06090e] border border-amber-500/40 focus-within:border-amber-400 rounded px-2.5 py-1 gap-2 transition-colors">
            <Terminal className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="font-mono-num text-[10px] font-semibold text-amber-500/90 bg-amber-500/10 px-1.5 py-0.5 rounded shrink-0">
              P{activePane.index}
            </span>
            <input
              id="global-command-input"
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                setOpen(true)
                if (lastError) clearError()
              }}
              onFocus={() => setOpen(true)}
              onBlur={() => window.setTimeout(() => setOpen(false), 160)}
              onKeyDown={handleInputKeyDown}
              placeholder="Enter command: AAPL US <Equity> DES | 600519 CH FA | BTC-USD GP | PORT | BQL   (Press / or Ctrl+K)"
              className="w-full bg-transparent text-amber-100 placeholder-slate-500 font-mono-num text-[12px] outline-none"
              autoComplete="off"
              spellCheck={false}
            />
            {input && (
              <button
                onClick={() => setInput('')}
                className="text-slate-500 hover:text-slate-300 cursor-pointer"
                aria-label="Clear command"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <div className="hidden sm:flex items-center gap-1 shrink-0 text-[9.5px] font-mono-num text-slate-500">
              <kbd className="px-1 py-0.2 bg-[#141c29] border border-[#243247] rounded text-amber-400">
                F2 EQ
              </kbd>
              <kbd className="px-1 py-0.2 bg-[#141c29] border border-[#243247] rounded text-cyan-400">
                F3 CR
              </kbd>
            </div>
          </div>

          {/* Autocomplete Dropdown */}
          {open && suggestions.length > 0 && (
            <div className="absolute left-0 right-0 mt-1 bg-[#0d131d] border border-[#2a3952] rounded shadow-2xl max-h-80 overflow-y-auto z-50">
              <div className="px-2.5 py-1 text-[9.5px] font-mono-num uppercase tracking-wider text-slate-500 border-b border-[#1c2636] flex justify-between">
                <span>Mnemonic Autocomplete (Tab to complete · Enter to run)</span>
                <span>Target: Pane {activePane.index} (Group {activePane.linkGroup})</span>
              </div>
              {suggestions.map((s, idx) => (
                <button
                  key={`${s.kind}-${s.label}-${idx}`}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    void submit(s.insert_text)
                  }}
                  className={`w-full text-left px-2.5 py-1.5 flex items-center justify-between gap-2 text-[11.5px] cursor-pointer ${
                    idx === selectedIdx
                      ? 'bg-amber-500/15 text-amber-100'
                      : 'text-slate-300 hover:bg-[#151f2e]'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`font-mono-num text-[9.5px] px-1.5 py-0.5 rounded shrink-0 ${
                        s.badge === 'US'
                          ? 'bg-sky-500/15 text-sky-300'
                          : s.badge === 'CN_ASHARE'
                            ? 'bg-rose-500/15 text-rose-300'
                            : s.badge === 'CRYPTO'
                              ? 'bg-amber-500/15 text-amber-300'
                              : 'bg-slate-700/60 text-slate-300'
                      }`}
                    >
                      {s.badge}
                    </span>
                    <span className="font-mono-num font-semibold text-amber-300 shrink-0">
                      {s.label}
                    </span>
                    <span className="text-slate-400 truncate text-[11px]">{s.detail}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quick Mnemonic Presets */}
        <div className="hidden xl:flex items-center gap-1">
          {QUICK_COMMANDS.map((q) => (
            <button
              key={q.label}
              onClick={() => void executeCommand(q.cmd)}
              className="px-2 py-1 rounded bg-[#121924] hover:bg-[#1b2638] border border-[#223045] text-[10.5px] font-mono-num text-slate-300 hover:text-amber-300 transition-colors cursor-pointer"
              title={`Run: ${q.cmd}`}
            >
              {q.label}
            </button>
          ))}
        </div>

        {/* Multi-Pane Layout Controls */}
        <div className="flex items-center gap-0.5 bg-[#06090e] border border-[#1f2a3c] rounded p-0.5 shrink-0">
          {layouts.map((l) => {
            const Icon = l.icon
            const active = layout === l.id
            return (
              <button
                key={l.id}
                onClick={() => setLayout(l.id)}
                title={l.title}
                className={`p-1 rounded cursor-pointer transition-colors ${
                  active
                    ? 'bg-amber-500/20 text-amber-300'
                    : 'text-slate-500 hover:text-slate-200 hover:bg-[#141d2b]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </button>
            )
          })}
        </div>
      </div>

      {/* Inline Parser Error Banner */}
      {lastError && (
        <div className="mt-1.5 flex items-center justify-between px-2.5 py-1 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[11px] font-mono-num">
          <span>CMD ERROR: {lastError}</span>
          <button onClick={clearError} className="text-rose-200 hover:text-white cursor-pointer">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </header>
  )
}
