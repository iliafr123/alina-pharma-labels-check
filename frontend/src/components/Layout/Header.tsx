import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useState, useEffect } from 'react'

export default function Header() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <header className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <button onClick={() => setDark(!dark)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 text-lg" title="Тема">
          {dark ? '☀️' : '🌙'}
        </button>
        <div className="text-sm text-right">
          <p className="font-medium text-gray-800 dark:text-white">{user?.email}</p>
          <p className="text-xs text-gray-400">{user?.role === 'admin' ? 'Администратор' : 'Специалист'}</p>
        </div>
        <button
          onClick={handleLogout}
          className="text-sm text-red-500 hover:text-red-700 font-medium"
        >
          Выйти
        </button>
      </div>
    </header>
  )
}
