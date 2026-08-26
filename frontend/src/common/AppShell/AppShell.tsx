import type { ReactNode } from 'react'
import Sidebar from '../Sidebar/Sidebar'
import './AppShell.css'
import { RoutePage } from '@/routes'

type AppShellProps = {
  pages: RoutePage[]
  currentPageId: string
  currentPageLabel: string
  menuOpen: boolean
  sidebarCollapsed: boolean
  mobileMenuOpen: boolean
  isMobile: boolean
  onNavigate: (path: string) => void
  onToggleMenu: () => void
  onCloseMenu: () => void
  onToggleSidebar: () => void
  onOpenMobileMenu: () => void
  onCloseMobileMenu: () => void
  onLogout: () => void
  children: ReactNode
}

function AppShell({
  pages,
  currentPageId,
  sidebarCollapsed,
  mobileMenuOpen,
  isMobile,
  onNavigate,
  onToggleSidebar,
  onOpenMobileMenu,
  onCloseMobileMenu,
  onLogout,
  children,
}: AppShellProps) {
  return (
    <div className={`app-shell ${isMobile ? 'mobile' : ''}`}>
      {isMobile && mobileMenuOpen && (
        <div 
          className="sidebar-overlay"
          onClick={onCloseMobileMenu}
        />
      )}
      <Sidebar
        pages={pages}
        currentPageId={currentPageId}
        sidebarCollapsed={sidebarCollapsed}
        isMobile={isMobile}
        mobileMenuOpen={mobileMenuOpen}
        onNavigate={onNavigate}
        onToggleSidebar={onToggleSidebar}
        onOpenMobileMenu={onOpenMobileMenu}
        onCloseMobileMenu={onCloseMobileMenu}
        onLogout={onLogout}
      />

      <div className="main-column">
        <main className="main-panel">{children}</main>
      </div>
    </div>
  )
}

export default AppShell
