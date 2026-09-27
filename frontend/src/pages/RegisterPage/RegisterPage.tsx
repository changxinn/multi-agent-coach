import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons'
import { register } from '@/lib/auth'
import { useAuthStore } from '@/lib/authStore'
import { Routes } from '@/lib/constants'

const { Title, Text } = Typography

type RegisterFormValues = {
  name: string
  email: string
  password: string
  confirmPassword: string
}

export function RegisterPage() {
  const navigate = useNavigate()
  const { login: storeLogin } = useAuthStore()
  const [isRegistering, setIsRegistering] = useState(false)

  const handleRegister = async ({ name, email, password }: RegisterFormValues) => {
    setIsRegistering(true)
    try {
      const response = await register({ name, email, password })
      storeLogin(response.access_token)
      message.success('Account created successfully')
      navigate(Routes.Dashboard, { replace: true })
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : 'Unable to create account'
      message.error(detail)
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md" title={<Title level={3} className="mb-0">Create an account</Title>}>
        <Form layout="vertical" onFinish={handleRegister} autoComplete="on">
          <Form.Item name="name" label="Name" rules={[{ required: true, whitespace: true, message: 'Enter your name' }]}>
            <Input prefix={<UserOutlined />} placeholder="Your name" autoComplete="name" />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Enter your email' }, { type: 'email', message: 'Enter a valid email address' }]}>
            <Input prefix={<MailOutlined />} placeholder="you@example.com" autoComplete="email" />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Enter a password' }, { min: 6, max: 128, message: 'Password must be 6 to 128 characters' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Create a password" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="Confirm password"
            dependencies={['password']}
            rules={[
              { required: true, message: 'Confirm your password' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  return !value || getFieldValue('password') === value
                    ? Promise.resolve()
                    : Promise.reject(new Error('Passwords do not match'))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Confirm your password" autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={isRegistering}>
            Create account
          </Button>
        </Form>
        <Text type="secondary" className="mt-4 block text-center">
          Already have an account?{' '}
          <Button type="link" className="p-0" onClick={() => navigate(Routes.Login)}>
            Sign in
          </Button>
        </Text>
      </Card>
    </div>
  )
}

export default RegisterPage