/**
 * Date and time format configurations
 * 
 * Purpose: Consistent date/time formatting across the app
 * Usage: import { DateFormats } from '@/lib/constants'
 */

export const DateFormats = {
  // For toLocaleDateString
  Display: {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  } as const,
  
  // For toLocaleTimeString
  Time: {
    hour: '2-digit',
    minute: '2-digit',
  } as const,
  
  // Full date and time
  DateTime: {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  } as const,
  
  // Short date (MM/DD/YYYY)
  Short: {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  } as const,
  
  // Long date (Monday, January 1, 2024)
  Long: {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  } as const,
} as const

// Helper functions
export const formatDate = (date: Date): string => {
  return date.toLocaleDateString('en-US', DateFormats.Display)
}

export const formatTime = (date: Date): string => {
  return date.toLocaleTimeString([], DateFormats.Time)
}

export const formatDateTime = (date: Date): string => {
  return date.toLocaleString('en-US', DateFormats.DateTime)
}
