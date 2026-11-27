import { create } from 'zustand'
import { terminalApi } from '../api/client'
import type { FunctionCode, LayoutMode, LinkGroup, LiveTick } from '../types/terminal'

export interface PaneState {
  id: string
  index: number
  fn: FunctionCode
  instrumentId: string
  compInstrumentIds: string[]
  linkGroup: LinkGroup
  args: string[]
}

const DEFAULT_PANES: PaneState[] = [
  {
    id: 'pane-1',
    index: 1,
    fn: 'DES',
    instrumentId: 'EQ:US:AAPL',
    compInstrumentIds: ['EQ:US:AAPL', 'EQ:US:NVDA', 'EQ:SSE:600519', 'CR:SPOT:BTC-USD'],
    linkGroup: 'A',
    args: [],
  },
  {
    id: 'pane-2',
    index: 2,
    fn: 'GP',
    instrumentId: 'EQ:US:AAPL',
    compInstrumentIds: ['EQ:US:AAPL', 'EQ:US:NVDA', 'EQ:SSE:600519', 'CR:SPOT:BTC-USD'],
    linkGroup: 'A',
    args: ['1Y'],
  },
  {
    id: 'pane-3',
    index: 3,
    fn: 'FA',
    instrumentId: 'EQ:SSE:600519',
    compInstrumentIds: ['EQ:SSE:600519', 'EQ:SZSE:300750', 'EQ:US:AAPL'],
    linkGroup: 'B',
    args: [],
  },
  {
    id: 'pane-4',
    index: 4,
    fn: 'NEWS',
    instrumentId: 'CR:SPOT:BTC-USD',
    compInstrumentIds: ['CR:SPOT:BTC-USD', 'CR:SPOT:ETH-USD', 'CR:SPOT:SOL-USD'],
    linkGroup: 'NONE',
    args: [],
  },
]

const LINK_CYCLE: LinkGroup[] = ['A', 'B', 'C', 'NONE']

interface WorkspaceStore {
  layout: LayoutMode
  panes: PaneState[]
  activePaneId: string
  commandHistory: string[]
  lastError: string | null
  lastExecuted: string | null
  liveTicks: Record<string, LiveTick>
  wsConnected: boolean

  setLayout: (layout: LayoutMode) => void
  setActivePane: (paneId: string) => void
  focusPaneByIndex: (index: number) => void
  cycleLinkGroup: (paneId: string) => void
  setPaneFunction: (paneId: string, fn: FunctionCode) => void
  setPaneSecurity: (paneId: string, instrumentId: string) => void
  setPaneCompList: (paneId: string, instrumentIds: string[]) => void
  executeCommand: (rawCommand: string, targetPaneId?: string) => Promise<void>
  clearError: () => void
  upsertTick: (tick: LiveTick) => void
  setWsConnected: (connected: boolean) => void
}

export function getVisiblePaneCount(layout: LayoutMode): number {
  if (layout === '1x1') return 1
  if (layout === '1x2' || layout === '2x1') return 2
  return 4
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  layout: '2x2',
  panes: DEFAULT_PANES,
  activePaneId: 'pane-1',
  commandHistory: [
    'AAPL US <Equity> DES',
    '600519 CH <Equity> FA',
    'BTC-USD <Crypto> GP',
    'AAPL US, NVDA US, 600519 CH, BTC-USD COMP',
    'PORT',
    'BQL',
  ],
  lastError: null,
  lastExecuted: 'AAPL US <Equity> DES',
  liveTicks: {},
  wsConnected: false,

  setLayout: (layout) => {
    const visible = getVisiblePaneCount(layout)
    const { panes, activePaneId } = get()
    const visibleIds = panes.slice(0, visible).map((p) => p.id)
    set({
      layout,
      activePaneId: visibleIds.includes(activePaneId) ? activePaneId : visibleIds[0],
    })
  },

  setActivePane: (paneId) => set({ activePaneId: paneId }),

  focusPaneByIndex: (index) => {
    const { panes, layout } = get()
    const visibleCount = getVisiblePaneCount(layout)
    if (index >= 1 && index <= visibleCount) {
      set({ activePaneId: panes[index - 1].id })
    }
  },

  cycleLinkGroup: (paneId) =>
    set((state) => ({
      panes: state.panes.map((p) => {
        if (p.id !== paneId) return p
        const next = LINK_CYCLE[(LINK_CYCLE.indexOf(p.linkGroup) + 1) % LINK_CYCLE.length]
        return { ...p, linkGroup: next }
      }),
    })),

  setPaneFunction: (paneId, fn) =>
    set((state) => ({
      activePaneId: paneId,
      panes: state.panes.map((p) => (p.id === paneId ? { ...p, fn } : p)),
    })),

  setPaneSecurity: (paneId, instrumentId) =>
    set((state) => {
      const target = state.panes.find((p) => p.id === paneId)
      const group = target?.linkGroup ?? 'NONE'
      return {
        panes: state.panes.map((p) => {
          if (p.id === paneId) return { ...p, instrumentId }
          if (group !== 'NONE' && p.linkGroup === group) return { ...p, instrumentId }
          return p
        }),
      }
    }),

  setPaneCompList: (paneId, instrumentIds) =>
    set((state) => ({
      panes: state.panes.map((p) =>
        p.id === paneId ? { ...p, compInstrumentIds: instrumentIds } : p,
      ),
    })),

  executeCommand: async (rawCommand, targetPaneId) => {
    const trimmed = rawCommand.trim()
    if (!trimmed) return
    const state = get()
    const paneId = targetPaneId ?? state.activePaneId
    const activePane = state.panes.find((p) => p.id === paneId) ?? state.panes[0]

    try {
      const parsed = await terminalApi.parseCommand(trimmed, activePane.instrumentId)
      if (parsed.error) {
        set({ lastError: parsed.error })
        return
      }

      const fn = (parsed.function || 'DES') as FunctionCode
      const primaryId = parsed.instrument_ids[0] ?? activePane.instrumentId
      const propagateSecurity =
        parsed.instrument_ids.length === 1 && !parsed.is_global && activePane.linkGroup !== 'NONE'

      set((s) => ({
        lastError: null,
        lastExecuted: trimmed,
        commandHistory: [trimmed, ...s.commandHistory.filter((h) => h !== trimmed)].slice(0, 40),
        panes: s.panes.map((p) => {
          if (p.id === paneId) {
            return {
              ...p,
              fn,
              instrumentId: primaryId,
              compInstrumentIds:
                fn === 'COMP' && parsed.instrument_ids.length >= 2
                  ? parsed.instrument_ids
                  : p.compInstrumentIds,
              args: parsed.args,
            }
          }
          if (propagateSecurity && p.linkGroup === activePane.linkGroup) {
            return { ...p, instrumentId: primaryId }
          }
          return p
        }),
      }))
    } catch (err) {
      set({ lastError: err instanceof Error ? err.message : 'Command execution failed' })
    }
  },

  clearError: () => set({ lastError: null }),

  upsertTick: (tick) =>
    set((state) => ({
      liveTicks: { ...state.liveTicks, [tick.instrument_id]: tick },
    })),

  setWsConnected: (connected) => set({ wsConnected: connected }),
}))
