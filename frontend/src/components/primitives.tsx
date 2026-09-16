import type { ReactNode } from 'react'

export function Panel({
  title,
  right,
  children,
  className = '',
}: {
  title: string
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel flex flex-col ${className}`}>
      <header className="panel-title flex items-center justify-between gap-2">
        <span>{title}</span>
        {right}
      </header>
      <div className="p-3 flex-1 min-h-0">{children}</div>
    </section>
  )
}

export function Field({
  label,
  value,
  tone = 'ink',
  small = false,
}: {
  label: string
  value: ReactNode
  tone?: 'ink' | 'go' | 'stop' | 'caution' | 'muted'
  small?: boolean
}) {
  const toneClass = {
    ink: 'text-ink',
    go: 'text-go',
    stop: 'text-stop',
    caution: 'text-caution',
    muted: 'text-muted',
  }[tone]
  return (
    <div>
      <div className="field-label">{label}</div>
      <div className={`readout ${small ? 'text-sm' : 'text-readout'} ${toneClass}`}>{value}</div>
    </div>
  )
}

export function Dot({ tone }: { tone: 'go' | 'stop' | 'caution' | 'muted' }) {
  const bg = { go: 'bg-go', stop: 'bg-stop', caution: 'bg-caution', muted: 'bg-muted' }[tone]
  return <span className={`inline-block h-2 w-2 rounded-full ${bg}`} aria-hidden />
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>
}

export function SimulationTag({ note }: { note?: string }) {
  return (
    <span
      title={note}
      className="readout text-[10px] border border-console/40 text-console px-1.5 py-0.5"
    >
      DEMO / SIMULATION
    </span>
  )
}
