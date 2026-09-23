import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../lib/authStore'
import { type Role, Routes } from '@/lib/constants'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: Role[]
}

export function ProtectedRoute({ 
  children, 
  allowedRoles 
}: ProtectedRouteProps) {
  const { token, isAuthInitialized, getUserRoles } = useAuthStore()
  const location = useLocation()

  if (!isAuthInitialized) {
    return null
  }

  if (!token) {
    return <Navigate to={Routes.Login} state={{ from: location }} replace />
  }

  if (allowedRoles) {
    const userRoles = getUserRoles()
    const hasAccess = userRoles.some(role => allowedRoles.includes(role))
    
    if (!hasAccess) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return <>{children}</>
}
