import { TrendSparkline } from './TrendSparkline'
import type { RecoveryTrendPoint } from './types'

function formatHours(minutes: number) {
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

export function RecoverySleepTrendChart({ trend }: { trend: RecoveryTrendPoint[] }) {
  const latest = [...trend].reverse().find(point => point.sleep_duration_minutes != null)?.sleep_duration_minutes
  return (
    <TrendSparkline
      label="Seven-day sleep duration"
      description={latest == null ? 'No sleep data recorded in the last seven days.' : `Latest logged sleep duration: ${formatHours(latest)}.`}
      emptyMessage="No sleep logs recorded in the last 7 days."
      series={[{ key: 'sleep', color: '#0f766e', values: trend.map(point => point.sleep_duration_minutes) }]}
      suffix={<span>7-day sleep duration</span>}
    />
  )
}