import { Empty, Panel } from './primitives'
import type { Ambulance, Decision } from '../types'

const NEGATIVE = [
  'NOT_VALIDATED',
  'SINGLE_FRAME_ONLY',
  'LOW_CONFIDENCE',
  'OUTSIDE_ROI',
  'APPROACH_UNKNOWN',
  'BELOW_THRESHOLD',
  'TRACK_NOT_CONFIRMED',
  'APPROACH_CHANGED',
]

function isNegative(code: string) {
  return NEGATIVE.includes(code) || code.startsWith('MOTION_')
}

export function DecisionPanel({
  decision,
  ambulances,
}: {
  decision: Decision | null
  ambulances: Ambulance[]
}) {
  const focus = decision ?? ambulances[0]?.decision ?? null
  const headline =
    focus?.decision === 'PRIORITY_REQUESTED'
      ? 'Priority requested'
      : focus?.decision === 'MONITORING'
        ? 'Monitoring, priority not requested'
        : 'No priority'
  return (
    <Panel title="Why this decision" right={<span className="readout text-[11px]">{focus?.decision ?? '—'}</span>}>
      {!focus ? (
        <Empty>Nothing to explain yet. Reasons appear as soon as a track is evaluated.</Empty>
      ) : (
        <>
          <p className="text-sm font-semibold">{headline}</p>
          <ul className="mt-2 space-y-1">
            {focus.reason_codes.map((code, i) => (
              <li key={code} className="flex items-start gap-2 text-sm">
                <span className={isNegative(code) ? 'text-stop' : 'text-go'}>
                  {isNegative(code) ? '×' : '✓'}
                </span>
                <span>
                  {focus.reasons[i]}
                  <span className="readout ml-2 text-[10px] text-muted">{code}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">
            Score {focus.priority_score.toFixed(2)} against threshold {focus.threshold.toFixed(2)}.
          </p>
        </>
      )}
    </Panel>
  )
}
