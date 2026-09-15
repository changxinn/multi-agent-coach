/**
 * Page IDs for navigation and menu items
 * 
 * Purpose: Single source of truth for page identifiers
 * Usage: import { PageIds } from '@/lib/constants'
 */

export const PageIds = {
  Landing: 'landing',
  Forms: 'forms',
  TableListing: 'table-listing',
  RecoveryTable: 'recovery-table',
  Timeline: 'timeline',
  Chat: 'chat',
} as const

export type PageId = typeof PageIds[keyof typeof PageIds]
