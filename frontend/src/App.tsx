import { useCallback, useState } from 'react'
import { StatusStrip } from './components/StatusStrip'
import { useLiveState } from './hooks/useLiveState'
import { Analysis } from './pages/Analysis'
import { Operations } from './pages/Operations'
import { api } from './services/api'

type Tab = 'operations' | 'analysis'

export default function App() {
  const { state, events, connected, setState } = useLiveState()
  const [tab, setTab] = useState<Tab>('operations')

  const refresh = useCallback(() => {
    api.status().then(setState).catch(() => undefined)
  }, [setState])

  return (
    <div className="min-h-full">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule bg-panel px-4 pt-3 pb-2">
        <div>
          <h1 className="text-base font-semibold tracking-tight">
            Ambulance intelligence · traffic control console
          </h1>
          <p className="text-[11px] text-muted">
            Project 27_CSAI_4B_04 · Pranveer Singh Institute of Technology, Kanpur
          </p>
        </div>
        <nav className="flex items-center gap-1">
          {(['operations', 'analysis'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-sm capitalize ${
                tab === t ? 'bg-console text-white' : 'border border-rule'
              }`}
            >
              {t}
            </button>
          ))}
          <span className="readout ml-2 border border-rule px-2 py-1 text-[11px]">
            {(state?.mode ?? 'demo').toUpperCase()} MODE
          </span>
        </nav>
      </header>
      <StatusStrip state={state} connected={connected} />
      {tab === 'operations' ? (
        <Operations state={state} events={events} refresh={refresh} />
      ) : (
        <Analysis />
      )}
      <footer className="border-t border-rule px-4 py-3 text-[11px] text-muted">
        Prototype for academic demonstration. Signal control, green corridor and any value marked
        demo or simulation are simulated and are not connected to real traffic infrastructure.
      </footer>
    </div>
  )
}
