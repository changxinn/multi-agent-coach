import { z } from 'zod'

// Reusable validation schemas
export const emailSchema = z.string().email('Invalid email address')
export const passwordSchema = z.string().min(6, 'Password must be at least 6 characters')
export const nameSchema = z.string().min(2, 'Name must be at least 2 characters')
export const phoneSchema = z.string().regex(/^\+?[\d\s-()]+$/, 'Invalid phone number')
export const urlSchema = z.string().url('Invalid URL')

// Password with complexity requirements
export const strongPasswordSchema = z.string()
  .min(8, 'Password must be at least 8 characters')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/[0-9]/, 'Password must contain at least one number')
  .regex(/[^A-Za-z0-9]/, 'Password must contain at least one special character')
