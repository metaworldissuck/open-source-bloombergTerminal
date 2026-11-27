import { useEffect, useRef } from 'react'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { LiveTick } from '../types/terminal'

const TAPE_IDS = [
  'EQ:US:AAPL',
  'EQ:US:NVDA',
  'EQ:SSE:600519',
  'EQ:SZSE:300750',
  'CR:SPOT:BTC-USD',
  'CR:SPOT:ETH-USD',
]

export function useRealtimeStream() {
  const panes = useWorkspaceStore((s) => s.panes)
  const upsertTick = useWorkspaceStore((s) => s.upsertTick)
  const setWsConnected = useWorkspaceStore((s) => s.setWsConnected)
  const wsRef = useRef<WebSocket | null>(null)
  const subIdsRef = useRef<string[]>([])

  const targetIds = Array.from(
    new Set([...TAPE_IDS, ...panes.map((p) => p.instrumentId)]),
  ).sort()
  const targetKey = targetIds.join(',')

  useEffect(() => {
    subIdsRef.current = targetIds
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ action: 'subscribe', instrument_ids: targetIds }),
      )
    }
  }, [targetKey])

  useEffect(() => {
    let closed = false
    let reconnectTimer: number | undefined

    function connect() {
      if (closed) return
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${window.location.host}/ws/stream`)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
        ws.send(
          JSON.stringify({ action: 'subscribe', instrument_ids: subIdsRef.current }),
        )
      }

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data) as LiveTick
          if (msg.type === 'tick' && msg.instrument_id) {
            upsertTick(msg)
          }
        } catch {
          // ignore malformed frames
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        if (!closed) {
          reconnectTimer = window.setTimeout(connect, 2500)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    return () => {
      closed = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [setWsConnected, upsertTick])
}
