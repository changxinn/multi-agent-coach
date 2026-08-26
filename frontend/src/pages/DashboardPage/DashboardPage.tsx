import { Card, Typography, Table, Tag, Statistic, Row, Col } from 'antd'
import { useAuthStore } from '@/lib/authStore'
import { DashboardOutlined, UserOutlined } from '@ant-design/icons'

const { Title, Text } = Typography

const getRoleTags = (role: string | string[]) => {
  const roles = Array.isArray(role) ? role : [role]
  const roleMap: Record<string, { label: string, color: string }> = {
    admin: { label: 'Admin', color: 'red' },
    staff: { label: 'Staff', color: '' },
    user: { label: 'User', color: 'green' },
  }

  return roles.map(r => {
    const info = roleMap[r.toLowerCase()] || { label: r, color: 'default' }
    return <Tag key={r} color={info.color}>{info.label}</Tag>
  })
}

interface DataType {
  key: string
  name: string
  status: string
  date: string
  role: string
}

const data: DataType[] = [
  { key: '1', name: 'Project Alpha', status: 'Active', date: '2024-01-15', role: 'Admin' },
  { key: '2', name: 'Project Beta', status: 'Pending', date: '2024-02-20', role: 'User' },
  { key: '3', name: 'Project Gamma', status: 'Completed', date: '2024-03-10', role: 'Manager' },
  { key: '4', name: 'Project Delta', status: 'Active', date: '2024-04-05', role: 'Admin' },
]

const columns = [
  { title: 'Project Name', dataIndex: 'name', key: 'name' },
  {
    title: 'Status',
    dataIndex: 'status',
    key: 'status',
    render: (status: string) => {
      const color = status === 'Active' ? 'green' : status === 'Pending' ? 'orange' : 'blue'
      return <Tag color={color}>{status.toUpperCase()}</Tag>
    },
  },
  { title: 'Created Date', dataIndex: 'date', key: 'date' },
  { title: 'Role', dataIndex: 'role', key: 'role' },
]

export function DashboardPage() {
  const { user } = useAuthStore()

  return (
    <div className="flex flex-col gap-4">
      {/* <DeepChatbotWrapper/> */}
      
      <div>
        <Title level={2}>
          <DashboardOutlined className="mr-2" />
          Dashboard
        </Title>
        <Text type="secondary">Welcome back, {user?.name}!</Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Projects"
              value={12}
              prefix={<UserOutlined />}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Active Tasks"
              value={28}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Pending Reviews"
              value={5}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Recent Projects">
        <Table columns={columns} dataSource={data} pagination={{ pageSize: 5 }} />
      </Card>

      <Card title="User Information">
        <div className="space-y-4">
          <div className="flex justify-between py-2 border-b">
            <Text strong>Name:</Text>
            <Text>{user?.name}</Text>
          </div>
          <div className="flex justify-between py-2 border-b">
            <Text strong>Email:</Text>
            <Text>{user?.email}</Text>
          </div>
          <div className="flex justify-between py-2 border-b">
            <Text strong>Role{user?.role && Array.isArray(user.role) ? 's' : ''}:</Text>
            <div className="flex gap-1">
              {user?.role && getRoleTags(user.role)}
            </div>
          </div>
          <div className="flex justify-between py-2">
            <Text strong>User ID:</Text>
            <Text code>{user?.sub}</Text>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default DashboardPage
