import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Typography, Button, message, Input } from 'antd'
import { UserOutlined, LoginOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/lib/authStore'
import { Routes } from '@/lib/constants'
import { login } from '@/lib/auth'

const { Title, Text } = Typography
const { Password } = Input

const demoAccounts = [
  { label: 'Alex (strength)', email: 'alex.demo@example.com' },
  { label: 'Sam (endurance)', email: 'sam.demo@example.com' },
]
const demoPassword = 'DemoPass123!'

export function QuickLoginPage() {
  const navigate = useNavigate()
  const { login: storeLogin } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoggingIn, setIsLoggingIn] = useState(false)

  const handleQuickLogin = async () => {
    setIsLoggingIn(true)
    try {
      const response = await login({ email, password })
      storeLogin(response.access_token)
      message.success('Login successful')
      navigate(Routes.Dashboard, { replace: true })
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : 'Login failed: Invalid credentials'
      message.error(detail)
    } finally {
      setIsLoggingIn(false)
    }
  }

  const fillDemoCredentials = (demoEmail: string) => {
    setEmail(demoEmail)
    setPassword(demoPassword)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="w-full max-w-2xl flex flex-col gap-4 bg-gray-50 p-5 rounded-lg">
        <Card className="mb-6" size="small">
          <Title level={5} className="mb-3">Sign in</Title>
          <div className="space-y-3">
            <div>
              <Text type="secondary" className="text-xs">Email:</Text>
              <Input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1 w-full"
                prefix={<UserOutlined />}
                type="email"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <Text type="secondary" className="text-xs">Password:</Text>
              <Password
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full"
                placeholder="Enter password"
              />
            </div>
          </div>
          <div className="mt-4 border-t border-gray-200 pt-3">
            <Text type="secondary" className="text-xs">
              Local demo accounts (Docker Compose):
            </Text>
            <div className="mt-2 flex flex-wrap gap-2">
              {demoAccounts.map((account) => (
                <Button
                  key={account.email}
                  size="small"
                  onClick={() => fillDemoCredentials(account.email)}
                >
                  Use {account.label}
                </Button>
              ))}
            </div>
          </div>
        </Card>

        <Button
          type="primary"
          size="large"
          block
          className="h-12 text-lg"
          icon={<LoginOutlined />}
          onClick={handleQuickLogin}
          loading={isLoggingIn}
          disabled={!email || !password}
        >
          Sign in
        </Button>
        <Text type="secondary" className="text-center">
          New here?{' '}
          <Button type="link" className="p-0" onClick={() => navigate(Routes.Register)}>
            Create an account
          </Button>
        </Text>
      </div>
    </div>
  )
}

export default QuickLoginPage
