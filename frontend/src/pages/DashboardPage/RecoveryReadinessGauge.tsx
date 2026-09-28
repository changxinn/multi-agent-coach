import { Progress, Space, Tag, Typography } from 'antd'
import type { RecoveryStatus } from './types'

const { Text } = Typography

const statusMeta: Record<Exclude<RecoveryStatus, 'no_assessment' | 'unavailable'>, { label: string; color: string }> = {
  green: { label: 'Ready / stable', color: '#389e0d' },
  amber: { label: 'Take care', color: '#d97706' },
  red: { label: 'Recovery needs attention', color: '#cf1322' },
  escalate: { label: 'Seek appropriate professional care', color: '#cf1322' },
}

export function RecoveryReadinessGauge({ status, score }: { status: RecoveryStatus; score: number | null }) {
  if (status === 'no_assessment' || status === 'unavailable' || score == null) return null
  const meta = statusMeta[status]
  return (
    <Space align="center" size="middle">
      <Progress type="circle" percent={Math.max(0, Math.min(score, 100))} size={88} strokeColor={meta.color} format={() => `${score}`} aria-label={`Recovery score ${score}`} />
      <Space orientation="vertical" size={2}>
        <Tag color={status === 'amber' ? 'gold' : status === 'green' ? 'green' : 'red'}>{meta.label}</Tag>
        <Text type="secondary">Persisted recovery assessment</Text>
      </Space>
    </Space>
  )
}