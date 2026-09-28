import { Alert, Button, Col, Row, Skeleton, Typography } from 'antd'
import { useAuthStore } from '@/lib/authStore'
import { ReloadOutlined } from '@ant-design/icons'
import { DailySummaryCard } from './DailySummaryCard'
import { NextBestActionsCard } from './NextBestActionsCard'
import { NutritionStatusCard } from './NutritionStatusCard'
import { RecoveryStatusCard } from './RecoveryStatusCard'
import { TrainingStatusCard } from './TrainingStatusCard'
import { useDailyCommandCenter } from './useDailyCommandCenter'
import './DashboardPage.css'

const { Title, Text } = Typography

export function DashboardPage() {
  const { user } = useAuthStore()
  const commandCenter = useDailyCommandCenter()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Title level={2}>
          Welcome back, {user?.name}!
        </Title>
        <Text className="!text-lg" type="secondary">Your daily coaching overview across training, nutrition, and recovery.</Text>
      </div>

      <DailySummaryCard />

      <div>
        <Title level={3}>Today with your coaching team</Title>
        <Text type="secondary">Review the signals your coaches use to help you decide what to do next.</Text>
      </div>

      {commandCenter.isLoading || commandCenter.isFetching ? <Row gutter={[16, 16]}>{[1, 2, 3].map(key => <Col key={key} xs={24} sm={24} md={12} lg={8}><Skeleton active paragraph={{ rows: 7 }} /></Col>)}</Row> : commandCenter.isError || !commandCenter.data ? <Alert
        type="warning"
        showIcon
        message="Your daily coaching status is temporarily unavailable."
        action={<Button size="small" icon={<ReloadOutlined />} onClick={() => void commandCenter.refetch()}>Retry</Button>}
      /> : <>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={24} md={12} lg={8}><RecoveryStatusCard recovery={commandCenter.data.recovery} /></Col>
          <Col xs={24} sm={24} md={12} lg={8}><NutritionStatusCard nutrition={commandCenter.data.nutrition} /></Col>
          <Col xs={24} sm={24} md={12} lg={8}><TrainingStatusCard training={commandCenter.data.training} /></Col>
        </Row>
        <NextBestActionsCard actions={commandCenter.data.actions} />
      </>}
    </div>
  )
}

export default DashboardPage
