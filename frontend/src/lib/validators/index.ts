/**
 * Central export file for all validation schemas
 * 
 * Purpose: Single import point for all validators
 * Usage: import { emailSchema, passwordSchema } from '@/lib/validators'
 * 
 * This file re-exports:
 * - Common schemas (email, password, name, phone, url)
 * - Login-specific schemas
 * - Type definitions
 */

// Export common validation schemas
export * from './common'

// Re-export login schema for backward compatibility
export { loginSchema, userSchema } from './login'
export type { LoginInput, UserInput } from './login'
