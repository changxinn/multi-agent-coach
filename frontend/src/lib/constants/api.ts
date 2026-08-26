/**
 * API configuration and endpoints
 * 
 * Purpose: Centralize API configuration
 * Usage: import { ApiConfig, ApiEndpoints } from '@/lib/constants'
 */

export const ApiConfig = {
  BaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  Timeout: 30000, // 30 seconds
  MaxRetries: 3,
} as const

export const ApiEndpoints = {
  Auth: {
    Login: '/auth/login',
    Register: '/auth/register',
    Refresh: '/auth/refresh',
  },
  Chat: {
    Send: '/chat',
    Stream: '/chat/stream',
    Summary: '/chat/summary',
    History: '/chat/history',
  },
  Session: {
    Create: '/session',
    Get: '/session',
    Delete: '/session',
    Clear: '/session/clear',
  },
} as const

export type ApiEndpoint = typeof ApiEndpoints[keyof typeof ApiEndpoints]
