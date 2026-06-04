import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const STATUS_BADGE: Record<string, string> = {
  COMPLETED: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  PENDING: 'bg-yellow-100 text-yellow-700',
  RUNNING: 'bg-blue-100 text-blue-700',
  CANCELLED: 'bg-gray-100 text-gray-500',
}

export default function HistoryPage() {
  const [checks, setChecks] = useState<any[]>([])
  const [status, setStatus] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/checks/history', { params: { status, limit: 100 } })
      .then((r) => setChecks(r.data))
      .catch(() => {})
  }, [status])

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-white">Журнал проверок</h1>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 dark:bg-gray-700 dark:text-white">
          <option value="">Все статусы</option>
          <option value="COMPLETED">Завершено</option>
          <option value="FAILED">Ошибка</option>
          <option value="PENDING">Ожидает</option>
          <option value="RUNNING">В обработке</option>
        </select>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">ID</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3 text-left">Режим</th>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {checks.length === 0 && (
              <tr><td colSpan={5} className="text-center py-8 text-gray-400">Проверок не найдено</td></tr>
            )}
            {checks.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer" onClick={() => navigate(`/checks/${c.id}`)}>
                <td className="px-4 py-3 font-mono text-xs text-gray-400">{c.id.slice(0, 8)}...</td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[c.status] || ''}`}>{c.status}</span>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{c.mode === 'hybrid' ? 'Гибридный' : 'Единый LLM'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{new Date(c.created_at).toLocaleString('ru-RU')}</td>
                <td className="px-4 py-3">
                  <button onClick={(e) => { e.stopPropagation(); navigate(`/checks/${c.id}`) }} className="text-xs text-[#2E75B6] hover:underline">Открыть</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
