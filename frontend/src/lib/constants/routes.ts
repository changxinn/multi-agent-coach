/**
 * Application route paths
 * 
 * Purpose: Single source of truth for all route paths
 * Usage: import { Routes } from '@/lib/constants'
 */

export const Routes = {
  Dashboard: '/dashboard',
  Forms: '/forms',
  TableListing: '/table-listing',
  CoachData: '/coach-data',
  RecoveryTable: '/recovery-table',
  Timeline: '/timeline',
  Login: '/login',
  QuickLogin: '/quick-login',
  Chat: '/chat',
  Nutrition: '/nutrition',
} as const

export type RoutePath = typeof Routes[keyof typeof Routes]
