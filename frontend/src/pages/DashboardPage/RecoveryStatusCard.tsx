import { Alert, Button, Card, Descriptions, Space, Typography } from 'antd'
import { HeartPulse } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Routes } from '@/lib/constants'
import { RecoveryReadinessGauge } from './RecoveryReadinessGauge'
import { RecoverySleepTrendChart } from './RecoverySleepTrendChart'
import type { RecoverySnapshot } from './types'

const { Text } = Typography

function formatSleep(minutes: number | null) {
  if (minutes == null) return 'No recent sleep log'
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export function RecoveryStatusCard({ recovery }: { recovery: RecoverySnapshot }) {
  const navigate = useNavigate()
  const isUnavailable = recovery.status === 'unavailable'
  const isNoAssessment = recovery.status === 'no_assessment'
  return (
    <Card className="dashboard-agent-card" title={<span><HeartPulse size={18} className="dashboard-agent-icon recovery" /> Recovery Coach</span>}>
      <Space className="dashboard-agent-content" orientation="vertical" size="middle" style={{ width: '100%' }}>
        {isUnavailable ? <Alert type="warning" showIcon message={recovery.message} /> : <>
          {isNoAssessment ? <Alert type="info" showIcon message={recovery.message} /> : <RecoveryReadinessGauge status={recovery.status} score={recovery.assessment_score} />}
          <Descriptions size="small" column={1} className="dashboard-recovery-details">
            <Descriptions.Item label="Latest sleep">{formatSleep(recovery.sleep_duration_minutes)}{recovery.sleep_quality != null ? ` · quality ${recovery.sleep_quality}/5` : ''}</Descriptions.Item>
            {recovery.energy != null && <Descriptions.Item label="Latest check-in"><Text>Energy {recovery.energy}/10 · Soreness {recovery.soreness}/10 · Stress {recovery.stress}/10</Text></Descriptions.Item>}
          </Descriptions>
          <RecoverySleepTrendChart trend={recovery.trend} />
        </>}
        <Button type="primary" danger={recovery.status === 'red' || recovery.status === 'escalate'} block onClick={() => navigate(Routes.RecoveryTable)}>Open Recovery</Button>
      </Space>
    </Card>
  )
}