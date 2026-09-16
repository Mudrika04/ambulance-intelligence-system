import type { SystemState, TimelineEvent } from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${res.status} ${detail}`)
  }
  return (await res.json()) as T
}

export const api = {
  status: () => request<SystemState>('/api/status'),
  health: () => request<{ status: string; components: Record<string, string>; mode: string }>('/api/health'),
  events: (limit = 60) => request<{ events: TimelineEvent[] }>(`/api/events?limit=${limit}`),
  metrics: () => request<Record<string, unknown>>('/api/metrics'),
  startSimulation: () => request('/api/simulation/start', { method: 'POST', body: '{}' }),
  startVideo: (mode?: string) =>
    request('/api/video/start', { method: 'POST', body: JSON.stringify({ mode }) }),
  stop: () => request('/api/video/stop', { method: 'POST' }),
  reset: () => request('/api/simulation/reset', { method: 'POST' }),
  replayTracks: () => request<{ track_ids: number[] }>('/api/replay/tracks'),
  replay: (id: number) => request<Record<string, any>>(`/api/replay/${id}`),
  runExperiment: (arrivals = 20) =>
    request<Record<string, any>>('/api/experiments/run', {
      method: 'POST',
      body: JSON.stringify({ scenario: 'dashboard', arrivals, seed: 42 }),
    }),
  experiments: () => request<{ experiments: any[]; status: string }>('/api/experiments'),
  ablation: () => request<Record<string, any>>('/api/ablation'),
  streamUrl: () => `${BASE}/api/video/stream?t=${Date.now()}`,
}

export const wsUrl = () => {
  if (BASE.startsWith('http')) return BASE.replace(/^http/, 'ws') + '/ws/live'
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/live`
}
