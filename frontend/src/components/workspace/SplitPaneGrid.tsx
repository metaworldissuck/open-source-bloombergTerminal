import { getVisiblePaneCount, useWorkspaceStore } from '../../store/workspaceStore'
import { PaneShell } from './PaneShell'

export function SplitPaneGrid() {
  const layout = useWorkspaceStore((s) => s.layout)
  const panes = useWorkspaceStore((s) => s.panes)
  const activePaneId = useWorkspaceStore((s) => s.activePaneId)

  const visibleCount = getVisiblePaneCount(layout)
  const visiblePanes =
    layout === '1x1'
      ? [panes.find((p) => p.id === activePaneId) ?? panes[0]]
      : panes.slice(0, visibleCount)

  const gridClass =
    layout === '1x1'
      ? 'grid-cols-1 grid-rows-1'
      : layout === '1x2'
        ? 'grid-cols-2 grid-rows-1'
        : layout === '2x1'
          ? 'grid-cols-1 grid-rows-2'
          : 'grid-cols-1 md:grid-cols-2 grid-rows-2'

  return (
    <main className={`flex-1 min-h-0 grid ${gridClass} gap-1.5 p-1.5 bg-[#06090e]`}>
      {visiblePanes.map((pane) => (
        <PaneShell key={pane.id} pane={pane} isActive={pane.id === activePaneId} />
      ))}
    </main>
  )
}
