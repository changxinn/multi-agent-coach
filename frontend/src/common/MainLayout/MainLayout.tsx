import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import AppShell from '@/common/AppShell'
import { useAuthStore } from '@/lib/authStore'
import { routePages, getVisiblePages, type Role } from '@/routes'
import { Roles } from '@/lib/constants'
import { ErrorBoundary } from '@/common/ErrorBoundary'

interface MainLayoutProps {
  children: React.ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, getUserRoles } = useAuthStore()
  
  const [menuOpen, setMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [userRoles, setUserRoles] = useState<Role[]>([])

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

  useEffect(() => {
    const roles = getUserRoles()
    setUserRoles(roles)
  }, [user, getUserRoles])

  const handleNavigate = (path: string) => {
    navigate(path)
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const visiblePages = getVisiblePages(userRoles)
  const primaryRole = userRoles.length > 0 ? userRoles[userRoles.length - 1] : Roles.Admin
  const currentPage = routePages.find((page) => page.path === location.pathname) ?? visiblePages[0] ?? routePages[0]

  return (
    <AppShell
      pages={visiblePages}
      currentPageId={currentPage.id}
      currentPageLabel={currentPage.label}
      role={primaryRole}
      menuOpen={menuOpen}
      sidebarCollapsed={sidebarCollapsed}
      mobileMenuOpen={mobileMenuOpen}
      isMobile={isMobile}
      onNavigate={handleNavigate}
      onToggleMenu={() => setMenuOpen(!menuOpen)}
      onCloseMenu={() => setMenuOpen(false)}
      onSelectRole={() => {}}
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
