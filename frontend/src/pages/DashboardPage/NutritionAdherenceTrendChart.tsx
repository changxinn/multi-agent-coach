import { TrendSparkline } from './TrendSparkline'
import type { NutritionTrendPoint } from './types'

export function NutritionAdherenceTrendChart({ trend }: { trend: NutritionTrendPoint[] }) {
  const latest = [...trend].reverse().find(point => point.calorie_adherence_pct != null || point.protein_adherence_pct != null)
  const summary = latest
    ? `Last recorded adherence: ${Math.round(latest.calorie_adherence_pct ?? 0)}% calories and ${Math.round(latest.protein_adherence_pct ?? 0)}% protein.`
    : 'No adherence data recorded in the last seven days.'
  return (
    <TrendSparkline
      label="Seven-day nutrition adherence"
      description={summary}
      emptyMessage="No nutrition data recorded in the last 7 days."
      series={[
        { key: 'calories', color: '#d97706', values: trend.map(point => point.calorie_adherence_pct) },
        { key: 'protein', color: '#0f766e', dashed: true, values: trend.map(point => point.protein_adherence_pct) },
      ]}
      suffix={<span>7-day adherence · <span className="dashboard-chart-key-calories">Calories</span> · <span className="dashboard-chart-key-protein">Protein</span></span>}
    />
  )
}