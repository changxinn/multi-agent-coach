import { create } from 'zustand'
import { jwtDecode } from 'jwt-decode'
import { StorageKeys, type Role } from './constants'

interface JwtPayload {
  sub: string
  email: string
  name: string
  role?: string | string[]  // Support single role or array of roles (from backend)
  roles?: string[]         // Alternative field for multiple roles
  exp: number
}

interface AuthState {
  user: JwtPayload | null
  token: string | null
  login: (token: string) => void
  logout: () => void
  checkAuth: () => void
  getUserRoles: () => Role[]
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  login: (token) => {
    localStorage.setItem(StorageKeys.Token, token)
    try {
      const decoded = jwtDecode<JwtPayload>(token)
      set({ user: decoded, token })
    } catch (error) {
      console.error('Invalid token:', error)
      set({ user: null, token })
    }
  },
  logout: () => {
    const email = get().user?.email
    if (email) {
      localStorage.removeItem(`deepchat_history_${email}`)
      localStorage.removeItem(`deepchat_${email}`)
    }
    localStorage.removeItem(StorageKeys.Token)
    set({ user: null, token: null })
  },
  checkAuth: () => {
    const token = localStorage.getItem(StorageKeys.Token)
    if (token) {
      try {
        const decoded = jwtDecode<JwtPayload>(token)
        const now = Date.now() / 1000
        if (decoded.exp > now) {
          set({ user: decoded, token })
        } else {
          localStorage.removeItem(StorageKeys.Token)
          set({ user: null, token: null })
        }
      } catch {
        localStorage.removeItem(StorageKeys.Token)
        set({ user: null, token: null })
      }
    }
  },
  getUserRoles: () => {
    const { user } = get()
    if (!user) {
      console.log('getUserRoles: No user found')
      return []
    }
    
    // console.log('getUserRoles: User object:', user)
    
    const roles: string[] = []
    
    // Handle array of roles
    if (Array.isArray(user.role)) {
      roles.push(...user.role)
      // console.log('getUserRoles: Found roles array:', user.role)
    } else if (user.role) {
      // Handle single role
      roles.push(user.role)
      // console.log('getUserRoles: Found single role:', user.role)
    }
    
    // Also check roles field
    if (Array.isArray(user.roles)) {
      roles.push(...user.roles)
      // console.log('getUserRoles: Found roles field:', user.roles)
    }
    
    // console.log('getUserRoles: All roles before mapping:', roles)
    
    // Map to application roles
    const roleMap: Record<string, Role> = {
      admin: 'Admin',
      staff: 'Staff',
      user: 'User',
    }
    
    const mappedRoles = roles
      .map(r => {
        const mapped = roleMap[r.toLowerCase()]
        // console.log(`getUserRoles: Mapping role "${r}" -> "${mapped}"`)
        return mapped
      })
      .filter((r): r is Role => r !== null)
    
    // console.log('getUserRoles: Mapped roles:', mappedRoles)
    return mappedRoles
  },
}))
