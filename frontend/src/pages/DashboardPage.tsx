import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface Stats { total_checks: number; completed: number; failed: number; pending: number }

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/admin/stats').then((r) => setStats(r.data)).catch(() => {})
  }, [])

  const cards = [
    { label: 'Всего проверок', value: stats?.total_checks ?? '—', color: 'bg-blue-50 dark:bg-blue-900/30 text-[#1F4E79] dark:text-blue-300' },
    { label: 'Завершено', value: stats?.completed ?? '—', color: 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300' },
    { label: 'Ошибок обработки', value: stats?.failed ?? '—', color: 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-300' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-white">Дашборд</h1>
        <button
          onClick={() => navigate('/checks/new')}
          className="bg-[#1F4E79] hover:bg-[#2E75B6] text-white font-semibold px-5 py-2 rounded-lg transition text-sm"
        >
          ➕ Новая проверка
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-xl p-5 ${c.color}`}>
            <p className="text-3xl font-bold">{c.value}</p>
            <p className="text-sm mt-1 opacity-80">{c.label}</p>
          </div>
        ))}
      </div>
      <p className="text-gray-400 text-sm">Для начала работы выберите «Новая проверка» или откройте «Журнал проверок».</p>
    </div>
  )
}
