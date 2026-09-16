import { Empty, Field, Panel } from './primitives'
import type { Ambulance } from '../types'

function Bar({ value, threshold }: { value: number; threshold: number }) {
  return (
    <div className="relative mt-1 h-2 w-full bg-paper border border-rule">
      <div
        className={`h-full ${value >= threshold ? 'bg-go' : 'bg-console/60'}`}
        style={{ width: `${Math.min(100, value * 100)}%` }}
      />
      <div
        className="absolute top-0 h-full border-l border-ink"
        style={{ left: `${threshold * 100}%` }}
        title={`threshold ${threshold}`}
      />
    </div>
  )
}

export function AmbulancePanel({ ambulances }: { ambulances: Ambulance[] }) {
  const focus = [...ambulances].sort((a, b) => b.priority.score - a.priority.score)[0]
  return (
    <Panel
      title="Ambulance intelligence"
      right={<span className="readout text-[11px] text-muted">{ambulances.length} tracked</span>}
    >
      {!focus ? (
        <Empty>No ambulance is currently tracked.</Empty>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Field label="Detection" value="YES" tone="go" />
            <Field label="Track" value={`#${focus.track_id}`} />
            <Field label="Confidence" value={focus.confidence.toFixed(2)} />
            <Field label="Approach" value={focus.approach} />
            <Field label="Direction" value={focus.direction} />
            <Field label="Proximity" value={focus.proximity} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Relative ETA"
              value={focus.relative_eta_s === null ? '—' : `${focus.relative_eta_s.toFixed(1)} s`}
              small
            />
            <Field
              label="Temporal validation"
              value={`${focus.validation.frames}/${focus.validation.required_frames} frames`}
              tone={focus.validated ? 'go' : 'muted'}
              small
            />
          </div>
          <p className="text-[11px] text-muted">{focus.proximity_note}</p>
          <div>
            <div className="flex items-baseline justify-between">
              <span className="field-label">Priority score</span>
              <span className="readout text-readout">{focus.priority.score.toFixed(2)}</span>
            </div>
            <Bar value={focus.priority.score} threshold={focus.priority.threshold} />
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
              {Object.entries(focus.priority.contributions).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-rule/60 py-0.5">
                  <dt className="text-muted">{k.replace(/_/g, ' ')}</dt>
                  <dd className="readout">{v.toFixed(2)}</dd>
                </div>
              ))}
            </dl>
          </div>
          {ambulances.length > 1 && (
            <div className="border-t border-rule pt-2 text-[11px]">
              <div className="field-label mb-1">Other tracked ambulances</div>
              {ambulances
                .filter((a) => a.track_id !== focus.track_id)
                .map((a) => (
                  <div key={a.track_id} className="flex justify-between">
                    <span className="readout">
                      #{a.track_id} {a.approach} {a.direction}
                    </span>
                    <span className="readout">{a.priority.score.toFixed(2)}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}
