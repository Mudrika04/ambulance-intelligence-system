import { Panel } from './primitives'
import { PhaseRibbon } from './PhaseRibbon'
import type { Direction, Lamp, SignalSnapshot } from '../types'

const DIRECTIONS: Direction[] = ['NORTH', 'SOUTH', 'EAST', 'WEST']

function Head({ direction, lamp }: { direction: Direction; lamp: Lamp }) {
  const lamps: Lamp[] = ['RED', 'YELLOW', 'GREEN']
  const colour: Record<Lamp, string> = {
    RED: 'bg-stop',
    YELLOW: 'bg-caution',
    GREEN: 'bg-go',
  }
  return (
    <div className="flex items-center gap-2 border border-rule px-2 py-1.5">
      <div className="flex flex-col gap-1">
        {lamps.map((l) => (
          <span
            key={l}
            aria-label={`${direction} ${l} ${lamp === l ? 'on' : 'off'}`}
            className={`h-2.5 w-2.5 rounded-full ${lamp === l ? colour[l] : 'bg-rule'}`}
          />
        ))}
      </div>
      <div>
        <div className="text-[11px] text-muted">{direction}</div>
        <div className="readout text-sm">{lamp}</div>
      </div>
    </div>
  )
}

export function SignalPanel({ signal }: { signal: SignalSnapshot }) {
  return (
    <Panel
      title="Traffic control"
      right={<span className="readout text-[11px]">{signal.fsm.state}</span>}
    >
      <PhaseRibbon signal={signal} />
      <div className="mt-3 grid grid-cols-2 gap-2">
        {DIRECTIONS.map((d) => (
          <Head key={d} direction={d} lamp={signal.lights?.[d] ?? 'RED'} />
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted">
        Simulated signal heads. The AI layer only requests priority; the deterministic state
        machine decides whether the transition is permitted.
      </p>
    </Panel>
  )
}
