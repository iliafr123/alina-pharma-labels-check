import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

const links = [
  { to: '/', label: 'Дашборд', icon: '📊' },
  { to: '/checks/new', label: 'Новая проверка', icon: '➕' },
  { to: '/checks/batch', label: 'Пакетная проверка', icon: '🗂️' },
  { to: '/history', label: 'Журнал проверок', icon: '📋' },
  { to: '/references', label: 'Справочники', icon: '📚' },
]

const adminLinks = [
  { to: '/admin', label: 'Администрирование', icon: '⚙️' },
]

export default function Sidebar() {
  const user = useAuthStore((s) => s.user)
  const allLinks = user?.role === 'admin' ? [...links, ...adminLinks] : links

  return (
    <aside className="w-56 bg-[#1F4E79] text-white flex flex-col py-6 px-3 min-h-screen shrink-0">
      <div className="mb-8 px-2">
        <p className="text-xs uppercase tracking-widest text-blue-300 font-semibold">Алина Фарма</p>
        <p className="text-xs text-blue-200 mt-1">v1.0</p>
      </div>
      <nav className="flex-1 space-y-1">
        {allLinks.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                isActive ? 'bg-[#2E75B6] text-white' : 'text-blue-100 hover:bg-[#2E75B6]/60'
              }`
            }
          >
            <span>{link.icon}</span>
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
