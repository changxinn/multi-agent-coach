/**
 * Status values used throughout the application
 * 
 * Purpose: Consistent status values across components
 * Usage: import { Status } from '@/lib/constants'
 */

export const Status = {
  Active: 'active',
  Inactive: 'inactive',
  Pending: 'pending',
  Completed: 'completed',
  OnLeave: 'on-leave',
  Processing: 'processing',
  Error: 'error',
} as const

export type Status = typeof Status[keyof typeof Status]

// Status color mapping
export const StatusColors = {
  [Status.Active]: 'green',
  [Status.Inactive]: 'red',
  [Status.Pending]: 'orange',
  [Status.Completed]: 'blue',
  [Status.OnLeave]: 'orange',
  [Status.Processing]: 'blue',
  [Status.Error]: 'red',
} as const

// Helper function to get status color
export const getStatusColor = (status: Status): string => {
  return StatusColors[status] || 'default'
}

// Helper to check if status is active
export const isActiveStatus = (status: Status): boolean => {
  return status === Status.Active
}
