import { Typography } from 'antd'
import { useAuthStore } from '@/lib/authStore'
import { DashboardOutlined } from '@ant-design/icons'
import { DailySummaryCard } from './DailySummaryCard'

const { Title, Text } = Typography

export function DashboardPage() {
  const { user } = useAuthStore()

  return (
    <div className="flex flex-col gap-4">      
      <div>
        <Title level={2}>
          <DashboardOutlined className="mr-2" />
          Dashboard
        </Title>
        <Text type="secondary">Welcome back, {user?.name}!</Text>
      </div>

      <DailySummaryCard />
    </div>
  )
}

export default DashboardPage
