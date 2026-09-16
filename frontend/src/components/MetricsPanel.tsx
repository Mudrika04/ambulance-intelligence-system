import { Panel } from './primitives'
import type { MetricSummary, SystemState } from '../types'

function value(m: unknown, unit: string) {
  const s = m as MetricSummary | undefined
  if (!s || s.mean === null || s.mean === undefined) return 'not measured'
  return `${s.mean.toFixed(s.mean < 10 ? 2 : 1)} ${unit}`
}

export function MetricsPanel({ state }: { state: SystemState | null }) {
  const m = state?.metrics ?? {}
  const rows: [string, string][] = [
    ['Processing rate', value(m.fps, 'fps')],
    ['Detection latency', value(m.detection_ms, 'ms')],
    ['Tracking latency', value(m.tracking_ms, 'ms')],
    ['Decision latency', value(m.decision_ms, 'ms')],
    ['End-to-end latency', value(m.end_to_end_ms, 'ms')],
  ]
  return (
    <Panel
      title="Measured performance"
      right={<span className="readout text-[11px] text-muted">{String(m.frames_processed ?? 0)} frames</span>}
    >
      <dl className="space-y-1 text-sm">
        {rows.map(([label, v]) => (
          <div key={label} className="flex justify-between border-b border-rule/60 py-1">
            <dt className="text-muted">{label}</dt>
            <dd className="readout">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-muted">
        Values are measured on this machine while the pipeline runs. Detection accuracy metrics
        require a labelled dataset and a trained model.
      </p>
    </Panel>
  )
}
