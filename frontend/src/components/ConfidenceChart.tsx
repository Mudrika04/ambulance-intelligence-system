import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function ConfidenceChart({
  history,
  label = 'Confidence',
}: {
  history: number[]
  label?: string
}) {
  const data = history.map((v, i) => ({ frame: i + 1, value: Number(v.toFixed(3)) }))
  if (data.length === 0) return <p className="text-sm text-muted">No recorded samples.</p>
  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
          <XAxis dataKey="frame" tick={{ fontSize: 10 }} stroke="#6B7069" />
          <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} stroke="#6B7069" />
          <Tooltip formatter={(v) => [String(v), label]} />
          <Line type="monotone" dataKey="value" stroke="#24485F" dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
