import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../lib/authStore'
import { Spin } from 'antd'
import { Roles, type Role } from '@/lib/constants'
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
  }, [])

  if (!token) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" description="Loading..." />
      </div>
    )
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
