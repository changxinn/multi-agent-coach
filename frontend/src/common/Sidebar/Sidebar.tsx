import type { ComponentType } from 'react'
import './Sidebar.css'
import { ChevronLeft, ChevronRight, LayoutDashboard, LogOut } from 'lucide-react'

interface SidebarPage {
  id: string
  path: string
  label: string
  section?: string
  icon?: ComponentType<{ size?: number }>
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
  onToggleSidebar,
  onCloseMobileMenu,
  onLogout
}: SidebarProps) {
  const showFull = isMobile ? mobileMenuOpen : !sidebarCollapsed
  const sidebarToggleLabel = sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'
  
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
    const Icon = page.icon ?? LayoutDashboard
    return <Icon size={20} />
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

        {isMobile ? (
          <button
            type="button"
            className="mobile-close"
            onClick={onCloseMobileMenu}
            aria-label="Close navigation menu"
          >
            ✕
          </button>
        ) : (
          <button
            type="button"
            className="collapse-toggle"
            onClick={onToggleSidebar}
            aria-label={sidebarToggleLabel}
            aria-expanded={!sidebarCollapsed}
            title={sidebarToggleLabel}
          >
            {sidebarCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
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
                aria-label={page.label}
                title={showFull ? undefined : page.label}
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
          aria-label="Sign Out"
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
