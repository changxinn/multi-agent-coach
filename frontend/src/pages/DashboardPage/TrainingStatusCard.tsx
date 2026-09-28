import { Button, Card, Space, Typography } from 'antd'
import { Dumbbell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Routes } from '@/lib/constants'
import type { TrainingSnapshot } from './types'

const { Text } = Typography

export function TrainingStatusCard({ training }: { training: TrainingSnapshot }) {
  const navigate = useNavigate()
  return (
    <Card className="dashboard-agent-card" title={<span><Dumbbell size={18} className="dashboard-agent-icon training" /> Training Planner</span>}>
      <Space className="dashboard-agent-content" orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Text>{training.message}</Text>
        <Text type="secondary">Ask the Training Planner for today&apos;s session, form guidance, or a program adjustment.</Text>
        <Button type="primary" block onClick={() => navigate(Routes.Chat)}>Ask Training Coach</Button>
      </Space>
    </Card>
  )
}