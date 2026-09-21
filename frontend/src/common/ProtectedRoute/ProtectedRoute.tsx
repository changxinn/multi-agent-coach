import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../lib/authStore'
import { type Role, Routes } from '@/lib/constants'
import { useEffect } from 'react'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: Role[]
}

export function ProtectedRoute({ 
  children, 
  allowedRoles 
}: ProtectedRouteProps) {
  const { token, checkAuth, getUserRoles } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

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
