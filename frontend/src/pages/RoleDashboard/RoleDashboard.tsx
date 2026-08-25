import { Card, Typography, Tag, Statistic, Row, Col, Table, Badge } from 'antd'
import { useAuthStore } from '@/lib/authStore'
import { UserOutlined, TeamOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { Roles, Status, type Role } from '@/lib/constants'

const { Title, Text } = Typography

interface RoleDashboardProps {
  role: Role
}

const projectData = [
  { key: '1', name: 'Project Alpha', status: Status.Active, progress: 75, deadline: '2024-08-15' },
  { key: '2', name: 'Project Beta', status: Status.Pending, progress: 30, deadline: '2024-09-20' },
  { key: '3', name: 'Project Gamma', status: Status.Completed, progress: 100, deadline: '2024-07-10' },
  { key: '4', name: 'Project Delta', status: Status.Active, progress: 60, deadline: '2024-08-30' },
]

const columns = [
  { title: 'Project Name', dataIndex: 'name', key: 'name' },
  { 
    title: 'Status', 
    dataIndex: 'status', 
    key: 'status',
    render: (status: string) => (
      <Badge 
        status={status === 'active' ? 'success' : status === 'completed' ? 'default' : 'warning'} 
        text={status.charAt(0).toUpperCase() + status.slice(1)} 
      />
    )
  },
  { title: 'Progress', dataIndex: 'progress', key: 'progress', render: (p: number) => `${p}%` },
  { title: 'Deadline', dataIndex: 'deadline', key: 'deadline' },
]

export function RoleDashboard({ role }: RoleDashboardProps) {
  const { user } = useAuthStore()

  const roleConfig = {
    [Roles.User]: {
      title: 'User Dashboard',
      description: 'Your personal workspace',
      stats: [
        { title: 'Chat', value: 8, icon: <CheckCircleOutlined />, color: '#1890ff' },
        { title: 'My progress', value: 3, icon: <ClockCircleOutlined />, color: '#faad14' },
      ],
      focus: 'Chat & Progress Tracking',
    },
    [Roles.Staff]: {
      title: 'Staff Dashboard',
      description: 'Your personal workspace for daily tasks and assignments',
      stats: [
        { title: 'My Tasks', value: 8, icon: <CheckCircleOutlined />, color: '#1890ff' },
        { title: 'In Progress', value: 3, icon: <ClockCircleOutlined />, color: '#faad14' },
        { title: 'Completed', value: 12, icon: <CheckCircleOutlined />, color: '#52c41a' },
      ],
      focus: 'Task Execution & Delivery',
    },
    [Roles.Admin]: {
      title: 'Admin Dashboard',
      description: 'System administration, governance, and strategic oversight',
      stats: [
        { title: 'Total Users', value: 48, icon: <TeamOutlined />, color: '#1890ff' },
        { title: 'Active Systems', value: 12, icon: <CheckCircleOutlined />, color: '#52c41a' },
        { title: 'Pending Reviews', value: 3, icon: <ClockCircleOutlined />, color: '#faad14' },
      ],
      focus: 'System Governance & Strategy',
    },
  }

  const config = roleConfig[role]

  return (
    <div>
      <div className="mb-8">
        <Title level={2} className="mb-2">
          {config.title}
        </Title>
        <Text type="secondary">{config.description}</Text>
        <div className="mt-3">
          <Tag color={role === Roles.Admin ? 'red' : role === Roles.Staff ? 'blue' : 'green'}>
            {role.toUpperCase()}
          </Tag>
          <Tag className="ml-2">{config.focus}</Tag>
        </div>
      </div>

      <Row gutter={[16, 16]} className="mb-8">
        {config.stats.map((stat, index) => (
          <Col xs={24} sm={8} key={index}>
            <Card>
              <Statistic
                title={stat.title}
                value={stat.value}
                prefix={<span style={{ color: stat.color }}>{stat.icon}</span>}
                styles={{ content: { color: stat.color } }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card title="Recent Projects" className="mb-8">
        <Table columns={columns} dataSource={projectData} pagination={false} />
      </Card>

      <Card title="Welcome Message">
        <Text>
          Welcome back, <strong>{user?.name}</strong>! 
          This is your {role.toLowerCase()} dashboard where you can manage your {role === Roles.Staff ? 'tasks and assignments' : role === Roles.User ? 'chat and progress' : 'system and users'}.
        </Text>
      </Card>
    </div>
  )
}

export default RoleDashboard
