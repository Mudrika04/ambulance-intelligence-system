import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ConfidenceChart } from '../components/ConfidenceChart'
import { TrajectoryChart } from '../components/TrajectoryChart'
import { Empty, Panel } from '../components/primitives'
import { api } from '../services/api'

export function Analysis() {
  const [trackIds, setTrackIds] = useState<number[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [replay, setReplay] = useState<Record<string, any> | null>(null)
  const [experiment, setExperiment] = useState<Record<string, any> | null>(null)
  const [ablation, setAblation] = useState<Record<string, any> | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.replayTracks().then((r) => {
      setTrackIds(r.track_ids)
      if (r.track_ids.length) setSelected(r.track_ids[0])
    })
    api.experiments().then((r) => {
      if (r.status === 'OK' && r.experiments.length) setExperiment(r.experiments[0].results)
    })
    api.ablation().then(setAblation).catch(() => setAblation(null))
  }, [])

  useEffect(() => {
    if (selected !== null) api.replay(selected).then(setReplay)
  }, [selected])

  const comparison = experiment
    ? [
        {
          metric: 'Mean wait (s)',
          'Fixed-time': experiment.baseline.mean_wait_s,
          'AI-adaptive': experiment.proposed.mean_wait_s,
        },
        {
          metric: 'Mean clearance (s)',
          'Fixed-time': experiment.baseline.mean_clearance_s,
          'AI-adaptive': experiment.proposed.mean_clearance_s,
        },
      ]
    : []

  return (
    <div className="grid gap-3 p-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-6">
        <Panel
          title="Emergency event replay"
          right={
            <select
              className="border border-rule px-1 py-0.5 text-xs"
              value={selected ?? ''}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {trackIds.map((id) => (
                <option key={id} value={id}>
                  Track #{id}
                </option>
              ))}
            </select>
          }
        >
          {!replay || trackIds.length === 0 ? (
            <Empty>
              No completed emergency event yet. Run the demo pipeline until an ambulance is
              validated, then return here.
            </Empty>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <div className="field-label">Approach</div>
                  <div className="readout">{replay.track?.approach ?? '—'}</div>
                </div>
                <div>
                  <div className="field-label">Frames tracked</div>
                  <div className="readout">{replay.track?.frames ?? 0}</div>
                </div>
                <div>
                  <div className="field-label">Peak confidence</div>
                  <div className="readout">
                    {replay.track?.max_confidence?.toFixed?.(2) ?? '—'}
                  </div>
                </div>
              </div>
              <ol className="max-h-56 space-y-1 overflow-y-auto border-t border-rule pt-2 text-[12px]">
                {replay.timeline.map((e: any, i: number) => (
                  <li key={i} className="flex gap-2">
                    <span className="readout text-muted">
                      {new Date(e.timestamp).toLocaleTimeString('en-GB', { hour12: false })}
                    </span>
                    <span className="readout">{e.event_type}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </Panel>
        <Panel title="Confidence over time">
          <ConfidenceChart
            history={(replay?.trajectory ?? []).map((p: any) => p.confidence)}
          />
        </Panel>
        <Panel title="Recorded trajectory">
          <TrajectoryChart points={replay?.trajectory ?? []} />
        </Panel>
      </div>

      <div className="space-y-3 lg:col-span-6">
        <Panel
          title="Fixed-time versus AI-adaptive control"
          right={
            <button
              className="border border-console bg-console px-2 py-1 text-xs text-white disabled:opacity-50"
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  setExperiment(await api.runExperiment(20))
                } finally {
                  setBusy(false)
                }
              }}
            >
              {busy ? 'Running…' : 'Run experiment'}
            </button>
          }
        >
          {!experiment ? (
            <Empty>Awaiting experiment data. Run an experiment to populate this comparison.</Empty>
          ) : (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparison} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                    <CartesianGrid stroke="#D5D6D0" vertical={false} />
                    <XAxis dataKey="metric" tick={{ fontSize: 11 }} stroke="#6B7069" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#6B7069" />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="Fixed-time" fill="#6B7069" />
                    <Bar dataKey="AI-adaptive" fill="#24485F" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-[11px] text-muted">
                {experiment.note} Arrivals simulated: {experiment.baseline.arrivals}. Mean wait
                reduction: {experiment.comparison.mean_wait_reduction_pct ?? '—'}%.
              </p>
            </>
          )}
        </Panel>

        <Panel title="Ablation study">
          {!ablation || ablation.status === 'AWAITING_EXPERIMENT_DATA' ? (
            <Empty>
              Awaiting ablation data. Run <span className="readout">python scripts/run_ablation.py</span>{' '}
              to generate it.
            </Empty>
          ) : (
            <table className="w-full text-[12px]">
              <thead className="text-muted">
                <tr className="border-b border-rule text-left">
                  <th className="py-1">Variant</th>
                  <th>Activations</th>
                  <th>False activations</th>
                  <th>Frames to decide</th>
                </tr>
              </thead>
              <tbody>
                {ablation.variants?.map((v: any) => (
                  <tr key={v.name} className="border-b border-rule/60">
                    <td className="py-1">{v.name}</td>
                    <td className="readout">{v.activations}</td>
                    <td className="readout">{v.false_activations}</td>
                    <td className="readout">{v.frames_to_decision ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  )
}
