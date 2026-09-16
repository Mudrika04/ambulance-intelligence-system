import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function TrajectoryChart({ points }: { points: { cx: number; cy: number }[] }) {
  if (points.length === 0) return <p className="text-sm text-muted">No trajectory recorded.</p>
  const data = points.map((p, i) => ({ step: i, x: Math.round(p.cx), y: Math.round(p.cy) }))
  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
          <XAxis dataKey="x" type="number" tick={{ fontSize: 10 }} stroke="#6B7069" />
          <YAxis dataKey="y" reversed tick={{ fontSize: 10 }} stroke="#6B7069" />
          <Tooltip />
          <Line type="monotone" dataKey="y" stroke="#C0342B" dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
