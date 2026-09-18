import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { errorMessage } from '../lib/errors'

const STATUS_BADGE: Record<string, string> = {
  COMPLETED: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  PENDING: 'bg-yellow-100 text-yellow-700',
  RUNNING: 'bg-blue-100 text-blue-700',
  CANCELLED: 'bg-gray-100 text-gray-500',
}

const STATUS_LABEL: Record<string, string> = {
  COMPLETED: 'Завершено',
  FAILED: 'Ошибка',
  PENDING: 'Ожидает',
  RUNNING: 'В обработке',
  CANCELLED: 'Отменено',
}

const CATEGORY_LABEL: Record<string, string> = {
  bad: 'БАД',
  sport: 'Спортпит',
  grocery: 'Бакалея',
}

export default function HistoryPage() {
  const [checks, setChecks] = useState<any[]>([])
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [loadError, setLoadError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => {
      api.get('/checks/history', { params: { status, product_name: search, limit: 100 } })
        .then((r) => { setChecks(r.data); setLoadError('') })
        .catch((e) => setLoadError(errorMessage(e, 'Не удалось загрузить журнал')))
    }, search ? 300 : 0)   // debounce typing in the search box
    return () => clearTimeout(t)
  }, [status, search])

  return (
    <div>
      <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-white">Журнал проверок</h1>
        <div className="flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию БАДа"
            className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 dark:bg-gray-700 dark:text-white w-64"
          />
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 dark:bg-gray-700 dark:text-white">
            <option value="">Все статусы</option>
            <option value="COMPLETED">Завершено</option>
            <option value="FAILED">Ошибка</option>
            <option value="PENDING">Ожидает</option>
            <option value="RUNNING">В обработке</option>
          </select>
        </div>
      </div>

      {loadError && (
        <p className="mb-3 text-sm text-red-500">{loadError}</p>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Продукт</th>
              <th className="px-4 py-3 text-left">Категория</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3 text-left">Замечаний</th>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {checks.length === 0 && (
              <tr><td colSpan={6} className="text-center py-8 text-gray-400">
                {search ? `По запросу «${search}» ничего не найдено` : 'Проверок не найдено'}
              </td></tr>
            )}
            {checks.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer align-top" onClick={() => navigate(`/checks/${c.id}`)}>
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-800 dark:text-gray-100">{c.product_name}</p>
                  <p className="text-xs text-gray-400">
                    {c.mockup_name}
                    {c.mockup_version ? ` · вер. ${c.mockup_version}` : ''}
                  </p>
                  {/* A failed run explains itself here instead of only inside the check. */}
                  {c.status === 'FAILED' && (c.error_details?.title || c.error) && (
                    <p className="text-xs text-red-500 mt-1">
                      {c.error_details?.title || c.error}
                      {c.error_code && <span className="text-gray-400"> [{c.error_code}]</span>}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                  {CATEGORY_LABEL[c.category] || c.category || '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_BADGE[c.status] || ''}`}>
                    {STATUS_LABEL[c.status] || c.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                  {c.status === 'COMPLETED' ? c.issues_count : '—'}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{new Date(c.created_at).toLocaleString('ru-RU')}</td>
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
