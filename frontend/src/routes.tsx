import type { ReactElement, ReactNode } from 'react'
import { Roles, PageIds, Routes, Sections, type Role, PageId, RoutePath, type Section } from '@/lib/constants'
import { 
  Bot,
  LayoutDashboard, 
  Table
} from 'lucide-react'

export const DEFAULT_ICON_SIZE = 20

export type RoutePage = {
  id: PageId
  label: string
  path: RoutePath
  component: ReactElement
  section?: Section
  icon?: ReactNode
  allowedRoles?: Role[]
}

export const routePages: RoutePage[] = [
  { 
    id: PageIds.Landing, 
    label: 'Dashboard', 
    path: Routes.Dashboard, 
    component: <></>,
    section: Sections.Overview,
    icon: <LayoutDashboard size={DEFAULT_ICON_SIZE} />,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin] 
  },
  { 
    id: PageIds.TableListing, 
    label: 'Table Listing', 
    path: Routes.TableListing, 
    component: <></>,
    section: Sections.Admin,
    icon: <Table size={DEFAULT_ICON_SIZE} />,
    allowedRoles: [Roles.Admin] 
  },
  { 
    id: PageIds.Chat, 
    label: 'Chat', 
    path: Routes.Chat, 
    component: <></>,
    section: Sections.Overview,
    icon: <Bot size={DEFAULT_ICON_SIZE} />,
    allowedRoles: [Roles.Admin] 
  },
]

export function getVisiblePages(userRoles: Role[]) {
  return routePages.filter((page) => {
    if (!page.allowedRoles) {
      return true
    }
    return userRoles.some(role => page.allowedRoles?.includes(role))
  })
}

export type RouteConfig = {
  path: RoutePath
  element: ReactElement
  allowedRoles?: Role[]
}

export const routeConfigs: RouteConfig[] = [
  {
    path: Routes.Dashboard,
    element: <></>,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin],
  },
  {
    path: Routes.Forms,
    element: <></>,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin],
  },
  {
    path: Routes.TableListing,
    element: <></>,
    allowedRoles: [Roles.Admin],
  },
  {
    path: Routes.Timeline,
    element: <></>,
    allowedRoles: [Roles.Admin],
  },
]

export const getProtectedRoute = (config: RouteConfig) => ({
  path: config.path,
  element: config.element,
})

export { Role }
