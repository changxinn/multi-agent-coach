import { create } from 'zustand'
import { jwtDecode } from 'jwt-decode'
import { StorageKeys } from './constants'

interface JwtPayload {
  sub: string
  email: string
  name: string
  exp: number
}

interface AuthState {
  user: JwtPayload | null
  token: string | null
  isAuthInitialized: boolean
  login: (token: string) => void
  logout: () => void
  checkAuth: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthInitialized: false,
  login: (token) => {
    localStorage.setItem(StorageKeys.Token, token)
    try {
      const decoded = jwtDecode<JwtPayload>(token)
      set({ user: decoded, token, isAuthInitialized: true })
    } catch (error) {
      console.error('Invalid token:', error)
      set({ user: null, token: null, isAuthInitialized: true })
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
          set({ user: decoded, token, isAuthInitialized: true })
        } else {
          localStorage.removeItem(StorageKeys.Token)
          set({ user: null, token: null, isAuthInitialized: true })
        }
      } catch {
        localStorage.removeItem(StorageKeys.Token)
        set({ user: null, token: null, isAuthInitialized: true })
      }
    } else {
      set({ user: null, token: null, isAuthInitialized: true })
    }
  },
}))
