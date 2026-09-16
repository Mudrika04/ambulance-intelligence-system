import { Panel } from './primitives'
import type { CorridorNode } from '../types'

const TONE: Record<string, string> = {
  ACTIVE_PRIORITY: 'border-go text-go',
  PREPARE: 'border-caution text-caution',
  CLEARED: 'border-console text-console',
  MONITOR: 'border-rule text-muted',
}

export function CorridorPanel({ nodes }: { nodes: CorridorNode[] }) {
  return (
    <Panel
      title="Green corridor"
      right={<span className="readout text-[10px] text-muted">PROTOTYPE SIMULATION</span>}
    >
      <ol className="space-y-2">
        {nodes.map((n, i) => (
          <li key={n.id} className={`border-l-2 pl-2 ${TONE[n.status] ?? TONE.MONITOR}`}>
            <div className="flex items-baseline justify-between">
              <span className="readout text-sm text-ink">{n.id}</span>
              <span className="readout text-[11px]">{n.status.replace('_', ' ')}</span>
            </div>
            <div className="text-[11px] text-muted">
              {n.name}
              {i === 0 ? ' · primary intersection' : ' · downstream'}
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] text-muted">
        Downstream states are simulated coordination only, with no connection to real traffic
        infrastructure.
      </p>
    </Panel>
  )
}
