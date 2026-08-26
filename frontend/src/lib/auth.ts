import { StorageKeys } from './constants'
import { fetcher } from './api'

export function setToken(token: string) {
  localStorage.setItem(StorageKeys.Token, token)
}

export function getToken(): string | null {
  return localStorage.getItem(StorageKeys.Token)
}

export function removeToken() {
  localStorage.removeItem(StorageKeys.Token)
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: number
    email: string
    name: string
    user_image: string | null
  }
}

export async function login(request: LoginRequest): Promise<AuthResponse> {
  const response = await fetcher<AuthResponse>('/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })
  return response
}

export async function register(request: RegisterRequest): Promise<AuthResponse> {
  const response = await fetcher<AuthResponse>('/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })
  return response
}

export async function refreshToken(): Promise<AuthResponse> {
  const token = getToken()
  const response = await fetcher<AuthResponse>('/auth/refresh', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })
  return response
}
