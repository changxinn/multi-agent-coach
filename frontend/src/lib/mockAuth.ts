import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
})

export type LoginInput = z.infer<typeof loginSchema>

interface LoginResponse {
  token: string
  user: {
    id: string
    email: string
    name: string
    role: string
  }
}

function b64EncodeUnicode(str: string): string {
  return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => String.fromCharCode(parseInt(p1, 16))))
}

function createMockJWT(email: string, role: string): string {
  const header = { alg: 'HS256', typ: 'JWT' }
  const payload = {
    sub: 'user-123',
    email,
    name: email.split('@')[0],
    role,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24,
  }

  const encodedHeader = b64EncodeUnicode(JSON.stringify(header)).replace(/=/g, '')
  const encodedPayload = b64EncodeUnicode(JSON.stringify(payload)).replace(/=/g, '')
  const signature = b64EncodeUnicode('mock-signature').replace(/=/g, '')

  return `${encodedHeader}.${encodedPayload}.${signature}`
}

export async function mockLogin(data: LoginInput): Promise<LoginResponse> {
  await new Promise((resolve) => setTimeout(resolve, 800))

  console.log('Mock login called with:', data)

  // Accept any email with password "password123" or any 6+ char password
  if (data.password !== 'password123' && data.password.length < 6) {
    throw new Error('Invalid email or password. Try: password123')
  }

  // Determine role from email
  const emailLower = data.email.toLowerCase()
  let role = 'user'
  if (emailLower.includes('admin')) role = 'admin'
  else if (emailLower.includes('manager')) role = 'manager'

  console.log('Login successful, role:', role)

  const token = createMockJWT(data.email, role)

  return {
    token,
    user: {
      id: 'user-123',
      email: data.email,
      name: data.email.split('@')[0],
      role,
    },
  }
}

export async function mockRefreshToken(token: string): Promise<{ token: string }> {
  await new Promise((resolve) => setTimeout(resolve, 500))
  const newToken = createMockJWT('user@example.com', 'user')
  return { token: newToken }
}
