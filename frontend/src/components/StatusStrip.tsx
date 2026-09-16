import { Dot } from './primitives'
import type { SystemState } from '../types'

const GOOD = ['ONLINE', 'READY', 'READY (DEMO)', 'READY (SCRIPTED)', 'ACTIVE', 'CONNECTED', 'OK']
const IDLE = ['IDLE', 'NOT_LOADED', 'OFFLINE', 'EOF']

function tone(value: string): 'go' | 'stop' | 'caution' | 'muted' {
  if (GOOD.includes(value)) return 'go'
  if (IDLE.includes(value)) return 'muted'
  if (value.includes('ERROR')) return 'stop'
  return 'caution'
}

export function StatusStrip({
  state,
  connected,
}: {
  state: SystemState | null
  connected: boolean
}) {
  const health = state?.health ?? {}
  const items: [string, string][] = [
    ['Camera', health.camera ?? 'OFFLINE'],
    ['Model', health.model ?? 'NOT_LOADED'],
    ['Tracker', health.tracker ?? 'IDLE'],
    ['Database', health.database ?? 'ERROR'],
    ['API', health.api ?? 'OFFLINE'],
    ['WebSocket', connected ? 'CONNECTED' : 'OFFLINE'],
  ]
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-rule bg-panel px-4 py-2">
      {items.map(([label, value]) => (
        <span key={label} className="flex items-center gap-1.5 text-xs">
          <Dot tone={tone(value)} />
          <span className="text-muted">{label}</span>
          <span className="readout text-[11px]">{value}</span>
        </span>
      ))}
    </div>
  )
}
