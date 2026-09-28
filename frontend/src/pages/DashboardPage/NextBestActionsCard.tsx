import { Alert, Button, Card, List, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { DashboardAction } from './types'

const { Text } = Typography
const colors = { critical: 'red', warning: 'gold', info: 'blue' } as const

export function NextBestActionsCard({ actions }: { actions: DashboardAction[] }) {
  const navigate = useNavigate()
  return (
    <Card title="Next best actions" className="dashboard-actions-card">
      {actions.length === 0 ? <Alert type="success" showIcon message="You’re all caught up for now." /> : <List
        dataSource={actions}
        renderItem={action => <List.Item actions={[<Button key={action.id} type="link" onClick={() => navigate(action.route)}>Open</Button>]}>
          <List.Item.Meta title={<><Tag color={colors[action.severity]}>{action.severity}</Tag> {action.title}</>} description={<Text type="secondary">{action.description}</Text>} />
        </List.Item>}
      />}
    </Card>
  )
}