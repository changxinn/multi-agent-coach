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
        <Text className="!text-lg" type="secondary">Review the signals your coaches use to help you decide what to do next.</Text>
      </div>

      {commandCenter.isLoading || commandCenter.isFetching ? <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}><div className="dashboard-coaching-stack"><Skeleton active paragraph={{ rows: 7 }} /><Skeleton active paragraph={{ rows: 7 }} /></div></Col>
        <Col xs={24} lg={12}><Skeleton active paragraph={{ rows: 14 }} /></Col>
      </Row> : commandCenter.isError || !commandCenter.data ? <Alert
        type="warning"
        showIcon
        title="Your daily coaching status is temporarily unavailable."
        action={<Button size="small" icon={<ReloadOutlined />} onClick={() => void commandCenter.refetch()}>Retry</Button>}
      /> : <>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12} className="dashboard-coaching-column">
            <div className="dashboard-coaching-stack">
              <RecoveryStatusCard recovery={commandCenter.data.recovery} />
              <NutritionStatusCard nutrition={commandCenter.data.nutrition} />
            </div>
          </Col>
          <Col xs={24} lg={12} className="dashboard-training-column"><TrainingStatusCard /></Col>
        </Row>
        <NextBestActionsCard actions={commandCenter.data.actions} />
      </>}
    </div>
  )
}

export default DashboardPage
