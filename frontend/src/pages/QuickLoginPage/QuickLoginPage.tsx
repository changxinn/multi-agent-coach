import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Typography, Button, Select, Alert, Divider, Tag, message, Input } from 'antd'
import { UserOutlined, LoginOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/lib/authStore'
import { envConfig } from '@/lib/envConfig'
import { Routes } from '@/lib/constants'
import { login } from '@/lib/auth'

const { Title, Text } = Typography
const { Option } = Select
const { Password } = Input

interface QuickLoginUser {
  email: string
  password: string
  role: string[]
  name: string
  description: string
}

export function QuickLoginPage() {
  const navigate = useNavigate()
  const { login: storeLogin } = useAuthStore()
  const [selectedUser, setSelectedUser] = useState<string>('admin@example.com')
  const [password, setPassword] = useState<string>('ChangeMe123!')
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [quickLoginUsers, setQuickLoginUsers] = useState<QuickLoginUser[]>([])

  useEffect(() => {
    // Initialize with default admin user
    // The backend creates this user automatically on startup
    setQuickLoginUsers([{
      email: 'admin@example.com',
      password: 'ChangeMe123!',
      role: ['admin'],
      name: 'System Admin',
      description: 'Default admin user - created on backend startup'
    }])
  }, [])

  const handleQuickLogin = async () => {
    setIsLoggingIn(true)
    
    const user = quickLoginUsers.find(u => u.email === selectedUser)
    if (user) {
      try {
        const response = await login({
          email: user.email,
          password: password
        })
        
        if (response.access_token) {
          storeLogin(response.access_token)
          message.success('Login successful')
          navigate(Routes.Dashboard, { replace: true })
        }
      } catch (error: any) {
        console.error('Login error:', error)
        message.error(error.message || 'Login failed: Invalid credentials')
      } finally {
        setIsLoggingIn(false)
      }
    } else {
      setIsLoggingIn(false)
    }
  }

  const currentUser = quickLoginUsers.find(u => u.email === selectedUser)

  const getRoleTags = (roles: string | string[]) => {
    const roleArray = Array.isArray(roles) ? roles : [roles]
    return roleArray.map(role => {
      const color = role.toLowerCase().includes('admin') ? 'red' : role.toLowerCase().includes('manager') || role.toLowerCase().includes('supervisor') ? 'blue' : 'green'
      const label = role.toLowerCase().includes('admin') ? 'Admin' : role.toLowerCase().includes('manager') || role.toLowerCase().includes('supervisor') ? 'Supervisor' : 'Staff'
      return <Tag key={role} color={color}>{label}</Tag>
    })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-2xl shadow-2xl" variant="borderless">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <CheckCircleOutlined className="text-3xl text-blue-600" />
          </div>
          <Title level={2} className="mb-2">
            {envConfig.appName}
          </Title>
          <Text type="secondary">Quick Login - {envConfig.appEnv.toUpperCase()} Environment</Text>
        </div>

        <Alert
          title="Backend Authentication"
          description="Login with email and password. Users are stored in the PostgreSQL database."
          type="info"
          showIcon
          className="mb-6"
        />

        <Card className="mb-6 bg-gray-50" size="small">
          <Title level={5} className="mb-3">Select User to Login As:</Title>
          <Select
            value={selectedUser}
            onChange={setSelectedUser}
            className="w-full mb-4"
            size="large"
            prefix={<UserOutlined />}
            optionLabelProp="label"
            disabled={quickLoginUsers.length === 0}
          >
            {quickLoginUsers.map((user) => (
              <Option 
                key={user.email} 
                value={user.email}
                label={`${user.name} - ${Array.isArray(user.role) ? user.role.length : 1} role(s)`}
              >
                <div className="flex justify-between items-center w-full">
                  <div>
                    <span className="font-medium">{user.name}</span>
                    <div className="text-xs text-gray-500">{user.email}</div>
                  </div>
                  <div className="flex gap-1">
                    {getRoleTags(user.role)}
                  </div>
                </div>
              </Option>
            ))}
          </Select>

          {currentUser && (
            <div className="space-y-3">
              <div>
                <Text type="secondary" className="text-xs">Email:</Text>
                <div className="mt-1">
                  <Text code>{currentUser.email}</Text>
                </div>
              </div>
              
              <div>
                <Text type="secondary" className="text-xs">Password:</Text>
                <Password
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full"
                  placeholder="Enter password"
                />
                <Text type="secondary" className="text-xs mt-1 block">
                  Default: {currentUser.password}
                </Text>
              </div>
              
              <div>
                <Text type="secondary" className="text-xs">Roles:</Text>
                <div className="mt-1 flex gap-2">
                  {getRoleTags(currentUser.role)}
                </div>
              </div>
              
              <div>
                <Text type="secondary" className="text-xs">Description:</Text>
                <p className="mt-1 text-sm text-gray-600">{currentUser.description}</p>
              </div>
            </div>
          )}
        </Card>

        <Button
          type="primary"
          size="large"
          block
          className="h-12 text-lg mb-4"
          icon={<LoginOutlined />}
          onClick={handleQuickLogin}
          loading={isLoggingIn}
          disabled={quickLoginUsers.length === 0 || !password}
        >
          {quickLoginUsers.length === 0 ? 'No valid users' : `Login as ${currentUser?.name}`}
        </Button>

        {quickLoginUsers.length > 0 && (
          <>
            <Divider plain>
              <Text type="secondary" className="text-xs">Role Information</Text>
            </Divider>

            <div className="text-xs text-gray-500 space-y-2">
              <div className="flex items-start gap-2">
                <Tag color="green">Staff</Tag>
                <span>Dashboard, Forms</span>
              </div>
              <div className="flex items-start gap-2">
                <Tag color="blue">Supervisor</Tag>
                <span>Staff pages + Team, Reports</span>
              </div>
              <div className="flex items-start gap-2">
                <Tag color="red">Admin</Tag>
                <span>All pages including Table Listing, Timeline</span>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

export default QuickLoginPage
