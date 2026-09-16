import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { Panel, SimulationTag } from './primitives'
import type { SystemState } from '../types'

export function LiveVideo({
  state,
  onChanged,
}: {
  state: SystemState | null
  onChanged: () => void
}) {
  const running = state?.running ?? false
  const [src, setSrc] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSrc(running ? api.streamUrl() : null)
  }, [running])

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      onChanged()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel
      title="Live view"
      right={
        <span className="flex items-center gap-2">
          {state?.simulated && <SimulationTag />}
          <span className="readout text-[11px] text-muted">
            frame {state?.frame_id ?? 0}
          </span>
        </span>
      }
    >
      <div className="relative bg-ink/90 aspect-video flex items-center justify-center overflow-hidden">
        {src ? (
          <img src={src} alt="Annotated intersection camera" className="h-full w-full object-contain" />
        ) : (
          <p className="max-w-sm px-6 text-center text-sm text-white/80">
            No video running. Start the demo pipeline to see detection, tracking and ROI
            overlays.
          </p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          className="border border-console bg-console px-3 py-1.5 text-sm text-white disabled:opacity-50"
          disabled={busy || running}
          onClick={() => run(api.startSimulation)}
        >
          Start demo pipeline
        </button>
        <button
          className="border border-rule px-3 py-1.5 text-sm disabled:opacity-50"
          disabled={busy || running}
          onClick={() => run(() => api.startVideo('real'))}
        >
          Start with trained model
        </button>
        <button
          className="border border-rule px-3 py-1.5 text-sm disabled:opacity-50"
          disabled={busy || !running}
          onClick={() => run(api.stop)}
        >
          Stop
        </button>
        <button
          className="border border-rule px-3 py-1.5 text-sm disabled:opacity-50"
          disabled={busy}
          onClick={() => run(api.reset)}
        >
          Reset
        </button>
      </div>
      {error && (
        <p className="mt-2 text-sm text-stop">
          {error.includes('MODEL NOT FOUND')
            ? 'No trained model found at models/ambulance_yolov8.pt. Place the weights there, or start the demo pipeline instead.'
            : error}
        </p>
      )}
    </Panel>
  )
}
