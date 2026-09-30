import { Alert, Button, Card, Progress, Space, Statistic, Typography } from 'antd'
import { Salad } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Routes } from '@/lib/constants'
import { NutritionAdherenceTrendChart } from './NutritionAdherenceTrendChart'
import type { NutritionSnapshot } from './types'

const { Text } = Typography

function percent(value: number | null, target: number | null) {
  if (value == null || !target) return 0
  return Math.max(0, Math.min((value / target) * 100, 100))
}

export function NutritionStatusCard({ nutrition }: { nutrition: NutritionSnapshot }) {
  const navigate = useNavigate()
  const hasTarget = nutrition.status === 'available'
  return (
    <Card className="dashboard-agent-card" title={<span><Salad size={18} className="dashboard-agent-icon nutrition" /> Nutrition Advisor</span>}>
      <Space className="dashboard-agent-content" orientation="vertical" size="middle" style={{ width: '100%' }}>
        {nutrition.status === 'unavailable' ? <Alert type="warning" showIcon title={nutrition.message} /> : <>
          <div className="dashboard-details-chart-layout">
            <div className="dashboard-details-column">
              {hasTarget ? <div className="dashboard-progress-row">
                <div>
                  <Progress type="circle" size={78} percent={percent(nutrition.calories, nutrition.calorie_target_kcal)} strokeColor="#d97706" format={() => `${Math.round(nutrition.calories ?? 0)}`} />
                  <Text type="secondary">Calories / {Math.round(nutrition.calorie_target_kcal ?? 0)}</Text>
                  <Statistic title="Meals logged" value={nutrition.meal_count ?? 0} />
                </div>
                <div>
                  <Progress type="circle" size={78} percent={percent(nutrition.protein_g, nutrition.protein_target_g)} strokeColor="#0f766e" format={() => `${Math.round(nutrition.protein_g ?? 0)}g`} />
                  <Text type="secondary">Protein / {Math.round(nutrition.protein_target_g ?? 0)}g</Text>
                  <Statistic title="Protein remaining" value={Math.max(0, nutrition.remaining_protein_g ?? 0)} suffix="g" precision={0} />
                </div>
              </div> : <><Alert type="info" showIcon title={nutrition.message ?? 'Set nutrition targets to see today’s progress.'} /><Statistic title="Meals logged" value={nutrition.meal_count ?? 0} /></>}
            </div>
            <NutritionAdherenceTrendChart trend={nutrition.trend} />
          </div>
        </>}
        <Button type="primary" block onClick={() => navigate(Routes.Nutrition)}>{hasTarget ? 'Open Nutrition' : 'Set targets'}</Button>
      </Space>
    </Card>
  )
}