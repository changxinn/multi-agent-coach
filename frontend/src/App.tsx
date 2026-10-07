import { Routes as RouterRoutes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { QuickLoginPage } from '@/pages/QuickLoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { TableListingPage } from '@/pages/TableListingPage'
import { CoachDataPage } from '@/pages/CoachDataPage'
import { RecoveryTablePage } from '@/pages/RecoveryTablePage'
import { ChatPage } from '@/pages/ChatPage'
import { NutritionPage } from '@/pages/NutritionPage'
import { TrainingPage } from '@/pages/TrainingPage'
import { MyProfilePage } from '@/pages/MyProfilePage'
import { ProtectedRoute } from '@/common/ProtectedRoute'
import { MainLayout } from '@/common/MainLayout'
import { ErrorBoundary } from '@/common/ErrorBoundary'
import { UnauthorizedPage } from '@/pages/UnauthorizedPage'
import { useAuthStore } from './lib/authStore'
import { useEffect } from 'react'
import { LibraryExamples } from '@/common/LibraryExamples'
import { Routes } from '@/lib/constants'

function App() {
  const { checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <ErrorBoundary>
      <RouterRoutes>
        <Route path={Routes.Login} element={<LoginPage />} />
        <Route path={Routes.Register} element={<RegisterPage />} />
        <Route path={Routes.QuickLogin} element={<QuickLoginPage />} />
        
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        
        <Route
          path={Routes.Dashboard}
          element={
            <ProtectedRoute>
              <MainLayout>
                <DashboardPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Forms}
          element={
            <ProtectedRoute>
              <MainLayout>
                <LibraryExamples />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.TableListing}
          element={
            <ProtectedRoute>
              <MainLayout>
                <TableListingPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.CoachData}
          element={
            <ProtectedRoute>
              <MainLayout>
                <CoachDataPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Chat}
          element={
            <ProtectedRoute>
              <MainLayout>
                <ChatPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.MyProfile}
          element={
            <ProtectedRoute>
              <MainLayout>
                <MyProfilePage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Nutrition}
          element={
            <ProtectedRoute>
              <MainLayout>
                <NutritionPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.Training}
          element={
            <ProtectedRoute>
              <MainLayout>
                <TrainingPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path={Routes.RecoveryTable}
          element={
            <ProtectedRoute>
              <MainLayout>
                <RecoveryTablePage />
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
