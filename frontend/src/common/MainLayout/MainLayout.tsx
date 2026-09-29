import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import AppShell from '@/common/AppShell'
import { useAuthStore } from '@/lib/authStore'
import { routePages } from '@/routes'
import { ErrorBoundary } from '@/common/ErrorBoundary'
import { PageIds } from '@/lib/constants'
import { api } from '@/lib/api'

interface MainLayoutProps {
  children: React.ReactNode
}

type AuthProfile = {
  is_nutrition_compatibility_admin: boolean
}

export function MainLayout({ children }: MainLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const profile = useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: () => api.get<AuthProfile>('/auth/profile'),
  })
  
  const [menuOpen, setMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (!mobile) {
        setMobileMenuOpen(false)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleNavigate = (path: string) => {
    navigate(path)
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const currentPage = routePages.find((page) => page.path === location.pathname) ?? routePages[0]
  const visiblePages = routePages.filter((page) => (
    page.id !== PageIds.CompatibilityReviews || profile.data?.is_nutrition_compatibility_admin === true
  ))

  return (
    <AppShell
      pages={visiblePages}
      currentPageId={currentPage.id}
      currentPageLabel={currentPage.label}
      menuOpen={menuOpen}
      sidebarCollapsed={sidebarCollapsed}
      mobileMenuOpen={mobileMenuOpen}
      isMobile={isMobile}
      userName={user?.name ?? 'User'}
      onNavigate={handleNavigate}
      onToggleMenu={() => setMenuOpen(!menuOpen)}
      onCloseMenu={() => setMenuOpen(false)}
      onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
      onOpenMobileMenu={() => setMobileMenuOpen(true)}
      onCloseMobileMenu={() => setMobileMenuOpen(false)}
      onLogout={handleLogout}
    >
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </AppShell>
  )
}

export default MainLayout
