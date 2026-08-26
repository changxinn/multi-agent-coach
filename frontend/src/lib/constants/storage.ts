/**
 * LocalStorage and SessionStorage keys
 * 
 * Purpose: Prevent typos in storage keys
 * Usage: import { StorageKeys } from '@/lib/constants'
 */

export const StorageKeys = {
  Token: 'token',
  User: 'user',
  Theme: 'theme',
  SidebarCollapsed: 'sidebar-collapsed',
  ChatHistory: 'chat-history',
} as const

export type StorageKey = typeof StorageKeys[keyof typeof StorageKeys]
