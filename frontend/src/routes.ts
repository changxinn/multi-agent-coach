import { Roles, PageIds, Routes, Sections, type Role, type PageId, type RoutePath, type Section } from '@/lib/constants'
import { Bot, ClipboardList, LayoutDashboard, Salad, Table, type LucideIcon } from 'lucide-react'

export const DEFAULT_ICON_SIZE = 20

export type RoutePage = {
  id: PageId
  label: string
  path: RoutePath
  section?: Section
  icon?: LucideIcon
  allowedRoles?: Role[]
}

export const routePages: RoutePage[] = [
  { 
    id: PageIds.Landing, 
    label: 'Dashboard', 
    path: Routes.Dashboard, 
    section: Sections.Overview,
    icon: LayoutDashboard,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin] 
  },
  {
    id: PageIds.Chat, 
    label: 'Chat', 
    path: Routes.Chat, 
    section: Sections.Overview,
    icon: Bot,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin] 
  },
  { 
    id: PageIds.CoachData, 
    label: 'Coach Data', 
    path: Routes.CoachData, 
    section: Sections.Admin,
    icon: ClipboardList,
    allowedRoles: [Roles.Admin] 
  },
  { 
    id: PageIds.RecoveryTable,
    label: 'Recovery Table',
    path: Routes.RecoveryTable,
    section: Sections.Admin,
    icon: Table,
    allowedRoles: [Roles.Admin]
  },
  { 
    id: PageIds.Nutrition,
    label: 'Nutrition',
    path: Routes.Nutrition,
    section: Sections.Admin,
    icon: Salad,
    allowedRoles: [Roles.User, Roles.Staff, Roles.Admin]
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

export { Role }
