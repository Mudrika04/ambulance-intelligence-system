import { useCallback, useEffect, useRef, useState } from 'react'
import { api, wsUrl } from '../services/api'
import type { SystemState, TimelineEvent } from '../types'

const MAX_EVENTS = 120

export function useLiveState() {
  const [state, setState] = useState<SystemState | null>(null)
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [connected, setConnected] = useState(false)
  const socket = useRef<WebSocket | null>(null)
  const retry = useRef<number>()

  const pushEvent = useCallback((event: TimelineEvent) => {
    setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS))
  }, [])

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl())
    socket.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      retry.current = window.setTimeout(connect, 2000)
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (raw) => {
      const msg = JSON.parse(raw.data)
      if (msg.type === 'state' || msg.type === 'hello') setState(msg.payload)
      else if (msg.type === 'event') pushEvent(msg.payload as TimelineEvent)
      else if (msg.type === 'system_health')
        setState((prev) => (prev ? { ...prev, ...msg.payload } : prev))
    }
  }, [pushEvent])

  useEffect(() => {
    api.status().then(setState).catch(() => undefined)
    api
      .events(60)
      .then((r) => setEvents(r.events))
      .catch(() => undefined)
    connect()
    return () => {
      window.clearTimeout(retry.current)
      socket.current?.close()
    }
  }, [connect])

  return { state, events, connected, setState }
}
