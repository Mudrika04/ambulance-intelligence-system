import { Empty, Panel } from './primitives'
import type { TimelineEvent } from '../types'

function clock(ts: string | number) {
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  return d.toLocaleTimeString('en-GB', { hour12: false })
}

const ALERT = ['REQUEST_REJECTED', 'TRANSITION_REJECTED', 'PRIORITY_CONFLICT', 'TRACK_LOST']

export function EventTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <Panel title="Event timeline" className="min-h-0">
      {events.length === 0 ? (
        <Empty>No events recorded yet.</Empty>
      ) : (
        <ul className="max-h-[22rem] space-y-1 overflow-y-auto pr-1">
          {events.map((e, i) => (
            <li key={`${e.id ?? i}-${e.event_type}`} className="flex gap-2 text-[12px]">
              <span className="readout text-muted">{clock(e.timestamp)}</span>
              <span
                className={`readout ${
                  ALERT.includes(e.event_type) || e.level === 'ERROR' ? 'text-stop' : 'text-ink'
                }`}
              >
                {e.event_type}
              </span>
              {e.track_id ? <span className="readout text-muted">#{e.track_id}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
