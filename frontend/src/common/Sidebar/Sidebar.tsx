// import type { RoutePage } from '../routes'
import type { ReactNode } from 'react'
import './Sidebar.css'
import {LayoutDashboard, LogOut} from 'lucide-react';

interface SidebarPage {
  id: string
  path: string
  label: string
  section?: string
  icon?: ReactNode
}

type SidebarProps = {
  pages: SidebarPage[]
  currentPageId: string
  sidebarCollapsed: boolean
  isMobile: boolean
  mobileMenuOpen: boolean
  onNavigate: (path: string) => void
  onToggleSidebar: () => void
  onOpenMobileMenu: () => void
  onCloseMobileMenu: () => void
  onLogout?: () => void
}

function Sidebar({ 
  pages, 
  currentPageId, 
  sidebarCollapsed, 
  isMobile,
  mobileMenuOpen,
  onNavigate, 
  onCloseMobileMenu,
  onLogout
}: SidebarProps) {
  const showFull = isMobile ? mobileMenuOpen : !sidebarCollapsed
  
  // Group pages by section
  const groupedPages = pages.reduce((acc, page) => {
    const section = page.section || 'General'
    if (!acc[section]) {
      acc[section] = []
    }
    acc[section].push(page)
    return acc
  }, {} as Record<string, SidebarPage[]>)

  const renderNavIcon = (page: SidebarPage) => {
    return page.icon || <LayoutDashboard size={20} />
  }

  return (
    <aside className={`sidebar ${
      isMobile 
        ? (mobileMenuOpen ? 'mobile-open' : 'mobile-closed')
        : (sidebarCollapsed ? 'collapsed' : 'open')
    }`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          {showFull && (
            <span className="brand-text">App</span>
          )}
        </div>

        {isMobile && (
          <button
            type="button"
            className="mobile-close"
            onClick={onCloseMobileMenu}
          >
            ✕
          </button>
        )}
      </div>

      <nav className="nav-links">
        {Object.entries(groupedPages).map(([section, sectionPages]) => (
          <div key={section} className="nav-section">
            {showFull && (
              <div className="nav-section-header">{section}</div>
            )}
            {sectionPages.map((page) => (
              <button
                key={page.id}
                type="button"
                className={`nav-item ${currentPageId === page.id ? 'active' : ''}`}
                onClick={() => {
                  onNavigate(page.path)
                  if (isMobile) onCloseMobileMenu()
                }}
              >
                <span className="nav-icon">{renderNavIcon(page)}</span>
                {showFull && (
                  <span className="nav-label">{page.label}</span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button
          type="button"
          className="logout-button"
          onClick={onLogout}
          title="Sign Out"
        >
          <LogOut />
          {showFull && <span>Sign Out</span>}
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
