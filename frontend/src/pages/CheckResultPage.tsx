import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const STAGE_LABELS: Record<string, string> = {
  ocr: 'Извлечение текста (OCR)',
  spelling: 'Орфография и стилистика',
  pen: 'Сверка с ПЭН',
  regulatory: 'Нормативный чек-лист',
  report: 'Генерация отчёта',
}

const TYPE_COLORS: Record<string, string> = {
  error: 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800',
  warning: 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700',
  info: 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700',
}
const TYPE_BADGES: Record<string, string> = {
  error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
  info: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
}

export default function CheckResultPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<any>(null)
  const [issues, setIssues] = useState<any[]>([])
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    if (!id) return
    const poll = setInterval(async () => {
      try {
        const { data } = await api.get(`/checks/${id}`)
        setTask(data)
        if (['COMPLETED', 'FAILED'].includes(data.status)) {
          clearInterval(poll)
          if (data.status === 'COMPLETED') {
            const issRes = await api.get(`/checks/${id}/issues`)
            setIssues(issRes.data.issues || [])
            try {
              const pdfRes = await api.get(`/checks/${id}/report/pdf`)
              setPdfUrl(pdfRes.data.url)
            } catch {}
          }
        }
      } catch {}
    }, 2500)
    return () => clearInterval(poll)
  }, [id])

  const handleApprove = async () => {
    setApproving(true)
    await api.post(`/checks/${id}/approve`)
    setApproving(false)
    alert('Макет согласован для отправки в типографию')
  }

  const download = async (fmt: 'excel' | 'word' | 'md') => {
    const ext: Record<string, string> = { excel: 'xlsx', word: 'docx', md: 'md' }
    const res = await api.get(`/checks/${id}/export/${fmt}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url; a.download = `report_${id}.${ext[fmt]}`; a.click()
    URL.revokeObjectURL(url)
  }
  const dlBtn = 'text-xs border border-gray-300 dark:border-gray-600 px-3 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700'

  const completedStages = task?.results?.map((r: any) => r.stage) || []
  const allStages = ['ocr', 'spelling', 'pen', 'regulatory', 'report']
  const filteredIssues = filter ? issues.filter((i) => i.type === filter) : issues
  const errorCount = issues.filter((i) => i.type === 'error').length
  const warnCount = issues.filter((i) => i.type === 'warning').length

  if (!task) return <div className="text-gray-400 text-sm">Загрузка...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-800 dark:text-white">Результат проверки</h1>
          <p className="text-xs text-gray-400 mt-0.5">ID: {id}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-semibold px-3 py-1 rounded-full ${task.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : task.status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
            {task.status}
          </span>
          {task.status === 'COMPLETED' && (
            <>
              <button onClick={() => download('word')} className={dlBtn}>Word</button>
              <button onClick={() => download('excel')} className={dlBtn}>Excel</button>
              <button onClick={() => download('md')} className={dlBtn}>MD</button>
              <button onClick={handleApprove} disabled={approving} className="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded-lg transition disabled:opacity-50">
                {approving ? '...' : '✓ Согласовать'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Benchmark verdict vs manual review */}
      {task.benchmark && (
        <div className={`rounded-xl p-4 mb-4 border ${
          task.benchmark.matched === true
            ? 'bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700'
            : task.benchmark.matched === false
            ? 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-300 dark:border-yellow-700'
            : 'bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600'}`}>
          <p className={`font-semibold text-sm mb-1 ${
            task.benchmark.matched === true ? 'text-green-700 dark:text-green-300'
            : task.benchmark.matched === false ? 'text-yellow-700 dark:text-yellow-300'
            : 'text-gray-600 dark:text-gray-300'}`}>
            {task.benchmark.matched === true
              ? '✅ Тест пройден успешно — результаты совпадают с ручной проверкой'
              : task.benchmark.matched === false
              ? '⚠️ Есть расхождения с ручной проверкой'
              : 'ℹ️ Сравнение с ручной проверкой'}
          </p>
          {task.benchmark.summary && <p className="text-sm text-gray-600 dark:text-gray-300">{task.benchmark.summary}</p>}
          {task.benchmark.missing?.length > 0 && (
            <div className="mt-2 text-xs text-gray-600 dark:text-gray-300">
              <p className="font-medium">Система не нашла (есть в ручной проверке):</p>
              <ul className="list-disc list-inside">{task.benchmark.missing.map((m: string, i: number) => <li key={i}>{m}</li>)}</ul>
            </div>
          )}
          {task.benchmark.extra?.length > 0 && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              <p className="font-medium">Дополнительно нашла система (нет в ручной):</p>
              <ul className="list-disc list-inside">{task.benchmark.extra.map((m: string, i: number) => <li key={i}>{m}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {/* Progress steps */}
      {task.status !== 'COMPLETED' && task.status !== 'FAILED' && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 mb-4 shadow">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">Прогресс проверки...</p>
          <div className="space-y-2">
            {allStages.map((stage) => {
              const done = completedStages.includes(stage)
              const current = !done && completedStages.length === allStages.indexOf(stage)
              return (
                <div key={stage} className="flex items-center gap-3">
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${done ? 'bg-green-500 text-white' : current ? 'bg-yellow-400 text-white animate-pulse' : 'bg-gray-200 dark:bg-gray-600'}`}>
                    {done ? '✓' : '·'}
                  </span>
                  <span className={`text-sm ${done ? 'text-gray-400' : current ? 'font-medium text-gray-700 dark:text-white' : 'text-gray-300'}`}>
                    {STAGE_LABELS[stage]}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {task.status === 'FAILED' && (
        <div className="bg-red-50 dark:bg-red-900/30 rounded-xl p-4 mb-4 border border-red-200">
          <p className="text-red-600 font-medium text-sm">Ошибка: {task.error}</p>
          <button onClick={() => navigate('/checks/new')} className="mt-2 text-xs text-red-500 underline">Новая проверка</button>
        </div>
      )}

      {task.status === 'COMPLETED' && (
        <div className="flex gap-4 h-[70vh]">
          {/* PDF viewer */}
          <div className="flex-1 bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
            {pdfUrl ? (
              <iframe src={pdfUrl} className="w-full h-full" title="PDF" />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">PDF не доступен для этого формата</div>
            )}
          </div>

          {/* Issues panel */}
          <div className="w-80 flex flex-col bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
            <div className="p-3 border-b border-gray-100 dark:border-gray-700">
              <div className="flex gap-2 mb-2">
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{errorCount} ошибок</span>
                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">{warnCount} предупреждений</span>
              </div>
              <select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-full text-xs border border-gray-200 dark:border-gray-600 rounded px-2 py-1 dark:bg-gray-700 dark:text-white">
                <option value="">Все замечания</option>
                <option value="error">Только ошибки</option>
                <option value="warning">Только предупреждения</option>
              </select>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {filteredIssues.length === 0 && <p className="text-gray-400 text-xs text-center mt-4">Замечаний нет</p>}
              {filteredIssues.map((issue, i) => (
                <div key={i} className={`rounded-lg border p-2.5 ${TYPE_COLORS[issue.type] || ''}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${TYPE_BADGES[issue.type] || ''}`}>{issue.type}</span>
                    <span className="text-xs text-gray-500">{issue.module}</span>
                  </div>
                  <p className="text-xs text-gray-700 dark:text-gray-200">{issue.description}</p>
                  {issue.suggestion && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">{issue.suggestion}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
