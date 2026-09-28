import type { ReactNode } from 'react'

type Series = {
  key: string
  color: string
  dashed?: boolean
  values: (number | null)[]
}

interface TrendSparklineProps {
  label: string
  description: string
  series: Series[]
  emptyMessage: string
  suffix?: ReactNode
}

const WIDTH = 280
const HEIGHT = 120
const PADDING = 12

function lineSegments(values: (number | null)[], maximum: number) {
  const segments: string[] = []
  let points: string[] = []
  const denominator = Math.max(values.length - 1, 1)

  values.forEach((value, index) => {
    if (value == null) {
      if (points.length > 1) segments.push(points.join(' '))
      points = []
      return
    }
    const x = PADDING + (index / denominator) * (WIDTH - PADDING * 2)
    const y = HEIGHT - PADDING - (Math.max(0, Math.min(value, maximum)) / maximum) * (HEIGHT - PADDING * 2)
    points.push(`${x},${y}`)
  })
  if (points.length > 1) segments.push(points.join(' '))
  return segments
}

export function TrendSparkline({ label, description, series, emptyMessage, suffix }: TrendSparklineProps) {
  const hasData = series.some(item => item.values.some(value => value != null))
  if (!hasData) return <span className="dashboard-chart-empty">{emptyMessage}</span>

  const maximum = Math.max(100, ...series.flatMap(item => item.values.filter((value): value is number => value != null)))
  return (
    <div className="dashboard-chart" role="img" aria-label={`${label}. ${description}`}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true">
        <line x1={PADDING} x2={WIDTH - PADDING} y1={HEIGHT / 2} y2={HEIGHT / 2} className="dashboard-chart-grid" />
        {series.flatMap(item => lineSegments(item.values, maximum).map((points, index) => (
          <polyline
            key={`${item.key}-${index}`}
            points={points}
            fill="none"
            stroke={item.color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={item.dashed ? '6 4' : undefined}
          />
        )))}
      </svg>
      <div className="dashboard-chart-caption">{suffix}</div>
    </div>
  )
}