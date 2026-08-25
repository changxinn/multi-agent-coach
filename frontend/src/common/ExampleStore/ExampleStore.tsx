import { useAppStore } from '../../lib/store'
import { Button, Card, Space } from 'antd'
import { UserOutlined, LogoutOutlined } from '@ant-design/icons'

export function ExampleStore() {
  const { user, isAuthenticated, setUser, logout } = useAppStore()

  const handleLogin = () => {
    setUser({
      id: '1',
      name: 'John Doe',
      email: 'john@example.com',
      role: 'admin',
    })
  }

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">Zustand Store Example</h2>
      <Card className="max-w-md">
        {isAuthenticated && user ? (
          <div>
            <p className="mb-4">
              <UserOutlined className="mr-2" />
              Logged in as: <strong>{user.name}</strong> ({user.email})
            </p>
            <Space>
              <Button onClick={logout} icon={<LogoutOutlined />}>
                Logout
              </Button>
            </Space>
          </div>
        ) : (
          <Button type="primary" onClick={handleLogin} icon={<UserOutlined />}>
            Login
          </Button>
        )}
      </Card>
    </div>
  )
}
