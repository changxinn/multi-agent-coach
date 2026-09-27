import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../lib/authStore'
import { Routes } from '@/lib/constants'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { token, isAuthInitialized } = useAuthStore()
  const location = useLocation()

  if (!isAuthInitialized) {
    return null
  }

  if (!token) {
    return <Navigate to={Routes.Login} state={{ from: location }} replace />
  }

  return <>{children}</>
}
