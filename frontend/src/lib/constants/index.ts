/**
 * Central export file for all application constants
 * 
 * Purpose: Single import point for all constants
 * Usage: import { Roles, Routes, Status } from '@/lib/constants'
 */

// Core constants
export * from './roles'

// Navigation
export * from './routes'
export * from './pages'
export * from './sections'

// Data & State
export * from './storage'
export * from './status'

// API
export * from './api'

// Utilities
export * from './date-formats'
export * from './pagination'
export * from './environments'

// Test data (only in dev/QA)
export * from './test-data'
