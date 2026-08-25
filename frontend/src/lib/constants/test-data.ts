/**
 * Test data and mock credentials
 * 
 * Purpose: Centralize test data for development/QA
 * Usage: import { TestCredentials } from '@/lib/constants'
 */

export const TestCredentials = {
  DefaultPassword: 'password123',
  
  Admin: {
    Email: 'admin@example.com',
    Name: 'Admin User',
  },
  
  Manager: {
    Email: 'manager@example.com',
    Name: 'Manager User',
  },
  
  Supervisor: {
    Email: 'supervisor@example.com',
    Name: 'Supervisor User',
  },
  
  Staff: {
    Email: 'staff@example.com',
    Name: 'Staff User',
  },
  
  User: {
    Email: 'user@example.com',
    Name: 'Regular User',
  },
} as const

// Helper to get all test users
export const getAllTestUsers = () => [
  { ...TestCredentials.Admin, role: 'admin' },
  { ...TestCredentials.Manager, role: 'manager' },
  { ...TestCredentials.Supervisor, role: 'manager' },
  { ...TestCredentials.Staff, role: 'user' },
  { ...TestCredentials.User, role: 'user' },
]
