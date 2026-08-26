/**
 * User role constants
 * 
 * Purpose: Single source of truth for role values
 * Usage: import { Roles } from '@/lib/constants'
 */

export const Roles = {
  User: 'User',
  Staff: 'Staff',
  Admin: 'Admin',
} as const

export type Role = keyof typeof Roles
export type RoleValue = typeof Roles[keyof typeof Roles]

// Helper functions
export const isRole = (value: string): value is Role => {
  return Object.keys(Roles).includes(value as Role)
}

export const getAllRoles = (): Role[] => {
  return Object.keys(Roles) as Role[]
}

// Role hierarchy (for permissions)
export const RoleHierarchy = {
  [Roles.User]: 1,
  [Roles.Staff]: 2,
  [Roles.Admin]: 3,
} as const

export const hasRolePermission = (userRole: Role, requiredRole: Role): boolean => {
  return RoleHierarchy[userRole] >= RoleHierarchy[requiredRole]
}

// Check if user has any of the required roles
export const hasAnyRolePermission = (userRoles: Role[], requiredRoles: Role[]): boolean => {
  return userRoles.some(userRole => 
    requiredRoles.some(requiredRole => 
      hasRolePermission(userRole, requiredRole)
    )
  )
}
