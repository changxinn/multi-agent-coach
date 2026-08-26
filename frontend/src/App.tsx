import { Routes as RouterRoutes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { QuickLoginPage } from '@/pages/QuickLoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { RoleDashboard } from '@/pages/RoleDashboard'
import { TableListingPage } from '@/pages/TableListingPage'
import { ChatPage } from '@/pages/ChatPage'
import { ProtectedRoute } from '@/common/ProtectedRoute'
import { MainLayout } from '@/common/MainLayout'
import { ErrorBoundary } from '@/common/ErrorBoundary'
import { UnauthorizedPage } from '@/pages/UnauthorizedPage'
import { useAuthStore } from './lib/authStore'
import { useEffect } from 'react'
import { LibraryExamples } from '@/common/LibraryExamples'
import { Roles, Routes } from '@/lib/constants'

function App() {
  const { checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <ErrorBoundary>
      <RouterRoutes>
        <Route path={Routes.Login} element={<LoginPage />} />
        <Route path={Routes.QuickLogin} element={<QuickLoginPage />} />
        
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        
        <Route
          path={Routes.Dashboard}
          element={
            <ProtectedRoute allowedRoles={[Roles.User, Roles.Staff, Roles.Admin]}>
              <MainLayout>
                <DashboardPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/staff-dashboard"
          element={
            <ProtectedRoute allowedRoles={[Roles.User, Roles.Staff, Roles.Admin]}>
              <MainLayout>
                <RoleDashboard role={Roles.Staff} />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin-dashboard"
          element={
            <ProtectedRoute allowedRoles={[Roles.Admin]}>
              <MainLayout>
                <RoleDashboard role={Roles.Admin} />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Forms}
          element={
            <ProtectedRoute allowedRoles={[Roles.User, Roles.Staff, Roles.Admin]}>
              <MainLayout>
                <LibraryExamples />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.TableListing}
          element={
            <ProtectedRoute allowedRoles={[Roles.Admin]}>
              <MainLayout>
                <TableListingPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Chat}
          element={
            <ProtectedRoute allowedRoles={[Roles.User, Roles.Staff, Roles.Admin]}>
              <MainLayout>
                <ChatPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to={Routes.Dashboard} replace />} />
        <Route path="*" element={<Navigate to={Routes.Dashboard} replace />} />
      </RouterRoutes>
    </ErrorBoundary>
  )
}

export default App
