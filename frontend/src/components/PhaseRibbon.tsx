import type { SignalSnapshot } from '../types'

const ORDER = ['NORMAL', 'PREPARE', 'ALL_RED', 'EMERGENCY_GREEN', 'CLEARANCE'] as const

export function PhaseRibbon({ signal }: { signal: SignalSnapshot }) {
  const current = signal.fsm.state
  const index = ORDER.indexOf(current)
  const progress =
    signal.fsm.phase_duration > 0
      ? Math.min(1, signal.fsm.phase_elapsed / signal.fsm.phase_duration)
      : 0
  return (
    <div>
      <div className="flex">
        {ORDER.map((phase, i) => {
          const active = phase === current
          const passed = index > i && index > 0
          return (
            <div
              key={phase}
              className={`relative flex-1 border-r border-rule last:border-r-0 px-2 py-1.5 ${
                active ? 'bg-console text-white' : passed ? 'bg-paper text-ink' : 'text-muted'
              }`}
            >
              <span className="readout text-[10px]">{phase.replace('_', ' ')}</span>
              {active && current !== 'NORMAL' && (
                <span
                  className="absolute left-0 bottom-0 h-0.5 bg-white/80"
                  style={{ width: `${progress * 100}%` }}
                />
              )}
            </div>
          )
        })}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span>
          Priority approach:{' '}
          <span className="readout text-ink">{signal.fsm.priority_approach ?? '—'}</span>
        </span>
        <span>
          {current === 'NORMAL' ? 'No emergency sequence active' : `Remaining ${signal.fsm.remaining.toFixed(1)} s of ${signal.fsm.phase_duration.toFixed(0)} s`}
        </span>
      </div>
    </div>
  )
}
