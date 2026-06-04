import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthUser { id: string; email: string; role: 'admin' | 'specialist' }

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  setAuth: (user: AuthUser, accessToken: string, refreshToken: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem('access_token', accessToken)
        localStorage.setItem('refresh_token', refreshToken)
        set({ user, accessToken })
      },
      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null })
      },
    }),
    { name: 'auth-storage', partialize: (s) => ({ user: s.user, accessToken: s.accessToken }) }
  )
)
