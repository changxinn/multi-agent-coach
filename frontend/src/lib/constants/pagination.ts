/**
 * Pagination settings for tables and lists
 * 
 * Purpose: Consistent pagination across the app
 * Usage: import { Pagination } from '@/lib/constants'
 */

export const Pagination = {
  DefaultPageSize: 10,
  PageSizeOptions: [5, 10, 20, 50, 100],
  MinPageSize: 5,
  MaxPageSize: 100,
  DefaultCurrent: 1,
  ShowSizeChanger: true,
  ShowQuickJumper: true,
  ShowTotal: true,
} as const

// Helper to get page size options
export const getPageSizeOptions = (max?: number): number[] => {
  if (!max) return Pagination.PageSizeOptions
  return Pagination.PageSizeOptions.filter(size => size <= max)
}
