import { AmbulancePanel } from '../components/AmbulancePanel'
import { CorridorPanel } from '../components/CorridorPanel'
import { DecisionPanel } from '../components/DecisionPanel'
import { EventTimeline } from '../components/EventTimeline'
import { LiveVideo } from '../components/LiveVideo'
import { MetricsPanel } from '../components/MetricsPanel'
import { SignalPanel } from '../components/SignalPanel'
import type { SystemState, TimelineEvent } from '../types'

export function Operations({
  state,
  events,
  refresh,
}: {
  state: SystemState | null
  events: TimelineEvent[]
  refresh: () => void
}) {
  const ambulances = state?.ambulances ?? []
  return (
    <div className="grid gap-3 p-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-7">
        <LiveVideo state={state} onChanged={refresh} />
        <DecisionPanel decision={state?.decision ?? null} ambulances={ambulances} />
        <MetricsPanel state={state} />
      </div>
      <div className="space-y-3 lg:col-span-5">
        <AmbulancePanel ambulances={ambulances} />
        {state?.signal && <SignalPanel signal={state.signal} />}
        <CorridorPanel nodes={state?.green_corridor?.intersections ?? []} />
        <EventTimeline events={events} />
      </div>
    </div>
  )
}
