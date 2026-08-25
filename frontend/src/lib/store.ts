import { create } from 'zustand'

interface AppState {
  user: {
    id: string
    name: string
    email: string
    role: string
  } | null
  isAuthenticated: boolean
  setUser: (user: AppState['user']) => void
  logout: () => void
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  logout: () => set({ user: null, isAuthenticated: false }),
}))
