import { PageIds, Routes, Sections, type PageId, type RoutePath, type Section } from '@/lib/constants'
import { Bot, CircleUser, ClipboardCheck, ClipboardList, Dumbbell, LayoutDashboard, Salad, Table, type LucideIcon } from 'lucide-react'

export const DEFAULT_ICON_SIZE = 20

export type RoutePage = {
  id: PageId
  label: string
  path: RoutePath
  section?: Section
  icon?: LucideIcon
}

export const routePages: RoutePage[] = [
  { 
    id: PageIds.Landing, 
    label: 'Dashboard', 
    path: Routes.Dashboard, 
    section: Sections.Overview,
    icon: LayoutDashboard,
  },
  {
    id: PageIds.Chat, 
    label: 'Chat', 
    path: Routes.Chat, 
    section: Sections.Overview,
    icon: Bot,
  },
  {
    id: PageIds.MyProfile,
    label: 'My Profile',
    path: Routes.MyProfile,
    section: Sections.Overview,
    icon: CircleUser,
  },
  { 
    id: PageIds.Nutrition,
    label: 'Nutrition',
    path: Routes.Nutrition,
    section: Sections.Coaching,
    icon: Salad,
  },
  {
    id: PageIds.Training,
    label: 'Training',
    path: Routes.Training,
    section: Sections.Coaching,
    icon: Dumbbell,
  },
  { 
    id: PageIds.CoachData, 
    label: 'Coach Data', 
    path: Routes.CoachData, 
    section: Sections.Review,
    icon: ClipboardList,
  },
  { 
    id: PageIds.RecoveryTable,
    label: 'Recovery Table',
    path: Routes.RecoveryTable,
    section: Sections.Review,
    icon: Table,
  },
  {
    id: PageIds.CompatibilityReviews,
    label: 'Compatibility Reviews',
    path: Routes.CompatibilityReviews,
    section: Sections.Review,
    icon: ClipboardCheck,
  },
]

export const getVisiblePages = () => routePages
