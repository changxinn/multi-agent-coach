import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Typography, Button, Select, Tag, message, Input } from 'antd'
import { UserOutlined, LoginOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/lib/authStore'
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
      <div className="w-full max-w-2xl flex flex-col gap-4 bg-gray-50 p-5 rounded-lg">
        <Card className="mb-6" size="small">
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
              
              {/* <div>
                <Text type="secondary" className="text-xs">Roles:</Text>
                <div className="mt-1 flex gap-2">
                  {getRoleTags(currentUser.role)}
                </div>
              </div> */}
              
              {/* <div>
                <Text type="secondary" className="text-xs">Description:</Text>
                <p className="mt-1 text-sm text-gray-600">{currentUser.description}</p>
              </div> */}
            </div>
          )}
        </Card>

        <Button
          type="primary"
          size="large"
          block
          className="h-12 text-lg"
          icon={<LoginOutlined />}
          onClick={handleQuickLogin}
          loading={isLoggingIn}
          disabled={quickLoginUsers.length === 0 || !password}
        >
          {quickLoginUsers.length === 0 ? 'No valid users' : `Login as ${currentUser?.name}`}
        </Button>
      </div>
    </div>
  )
}

export default QuickLoginPage
