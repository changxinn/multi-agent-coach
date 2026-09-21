import type { ReactNode } from 'react'
import { Menu } from 'lucide-react'
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
  userName: string
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
  userName,
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
        <header className="top-navigation">
          {isMobile && !mobileMenuOpen ? (
            <button
              type="button"
              className="mobile-navigation-toggle"
              onClick={onOpenMobileMenu}
              aria-label="Open navigation menu"
              title="Open navigation menu"
            >
              <Menu size={24} aria-hidden="true" />
            </button>
          ) : (
            <div className="top-navigation-spacer" aria-hidden="true" />
          )}
          <span className="top-navigation-user" title={userName}>{userName}</span>
        </header>
        <main className="main-panel">{children}</main>
      </div>
    </div>
  )
}

export default AppShell
