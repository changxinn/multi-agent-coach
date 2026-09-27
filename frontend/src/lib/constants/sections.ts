/**
 * Page section names for sidebar grouping
 * 
 * Purpose: Single source of truth for navigation sections
 * Usage: import { Sections } from '@/lib/constants'
 */

export const Sections = {
  Overview: 'OVERVIEW',
  Admin: 'ADMIN',
  Coaching: 'Coaching',
} as const

export type Section = typeof Sections[keyof typeof Sections]
