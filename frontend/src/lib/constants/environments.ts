/**
 * Environment names and configurations
 * 
 * Purpose: Type-safe environment checks
 * Usage: import { Environments } from '@/lib/constants'
 */

export const Environments = {
  Development: 'development',
  QA: 'qa',
  Production: 'production',
} as const

export type Environment = typeof Environments[keyof typeof Environments]

// Helper to check current environment
export const isDevelopment = (env: string): boolean => {
  return env === Environments.Development
}

export const isQA = (env: string): boolean => {
  return env === Environments.QA
}

export const isProduction = (env: string): boolean => {
  return env === Environments.Production
}

export const isTestEnvironment = (env: string): boolean => {
  return isDevelopment(env) || isQA(env)
}
