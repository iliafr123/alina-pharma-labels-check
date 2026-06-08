import { useState, useRef } from 'react'
import { api } from '../api/client'

type Row = { name: string; mockup: File | null; pen: File | null }

const ST_COLOR: Record<string, string> = {
  COMPLETED: 'bg-green-100 text-green-700', FAILED: 'bg-red-100 text-red-700',
  RUNNING: 'bg-blue-100 text-blue-700', PENDING: 'bg-yellow-100 text-yellow-700',
}

export default function BatchCheckPage() {
  const [rows, setRows] = useState<Row[]>([{ name: '', mockup: null, pen: null }])
  const [focus, setFocus] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [batchId, setBatchId] = useState('')
  const [tasks, setTasks] = useState<any[]>([])
  const pollRef = useRef<any>(null)

  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const addRow = () => setRows((rs) => (rs.length < 20 ? [...rs, { name: '', mockup: null, pen: null }] : rs))
  const delRow = (i: number) => setRows((rs) => rs.filter((_, j) => j !== i))

  const poll = (bid: string) => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/checks/batch/${bid}`)
        setTasks(data)
        if (data.length && data.every((x: any) => ['COMPLETED', 'FAILED', 'CANCELLED'].includes(x.status))) clearInterval(pollRef.current)
      } catch {}
    }, 3000)
  }

  const submit = async () => {
    const valid = rows.filter((r) => r.name && r.mockup && r.pen)
    if (!valid.length) { setError('Заполните хотя бы одну строку: название, макет, ПЭН'); return }
    setLoading(true); setError('')
    try {
      const items: any[] = []
      for (const r of valid) {
        const { data: product } = await api.post('/products', { name: r.name, category: 'bad' })
        const mf = new FormData(); mf.append('file', r.mockup!); mf.append('product_id', product.id)
        const { data: mockup } = await api.post('/uploads/mockup', mf)
        const pf = new FormData(); pf.append('file', r.pen!); pf.append('product_id', product.id)
        const { data: pen } = await api.post('/uploads/pen', pf)
        items.push({ mockup_id: mockup.id, pen_id: pen.id })
      }
      const { data } = await api.post('/checks/batch', { items, focus_prompt: focus || null })
      setBatchId(data.batch_id)
      poll(data.batch_id)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка при запуске пакета')
    } finally { setLoading(false) }
  }

  const download = async (fmt: 'md' | 'word') => {
    const res = await api.get(`/checks/batch/${batchId}/export/${fmt}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a'); a.href = url; a.download = `batch_${batchId}.${fmt === 'word' ? 'docx' : 'md'}`; a.click()
    URL.revokeObjectURL(url)
  }

  const done = tasks.length && tasks.every((x) => ['COMPLETED', 'FAILED', 'CANCELLED'].includes(x.status))
  const fileInput = 'text-xs text-gray-600 dark:text-gray-300 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:bg-gray-200 dark:file:bg-gray-600 file:text-xs'

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">Пакетная проверка</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">До 20 этикеток за раз. По завершении — один сводный файл (Word/MD).</p>

      {!batchId && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow space-y-3">
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center border-b dark:border-gray-700 pb-2">
              <span className="col-span-1 text-xs text-gray-400">#{i + 1}</span>
              <input value={r.name} onChange={(e) => setRow(i, { name: e.target.value })} placeholder="Название продукта"
                className="col-span-4 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-white" />
              <div className="col-span-3">
                <label className="block text-[10px] text-gray-400">Макет (PDF/JPG)</label>
                <input type="file" accept=".pdf,.jpg,.jpeg" onChange={(e) => setRow(i, { mockup: e.target.files?.[0] || null })} className={fileInput} />
              </div>
              <div className="col-span-3">
                <label className="block text-[10px] text-gray-400">ПЭН (DOCX)</label>
                <input type="file" accept=".docx" onChange={(e) => setRow(i, { pen: e.target.files?.[0] || null })} className={fileInput} />
              </div>
              <button onClick={() => delRow(i)} className="col-span-1 text-xs text-red-400 hover:text-red-600">✕</button>
            </div>
          ))}
          <button onClick={addRow} disabled={rows.length >= 20} className="text-sm text-[#2E75B6] hover:underline disabled:opacity-40">+ Добавить этикетку ({rows.length}/20)</button>

          <div className="pt-2">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Фокус проверки <span className="text-gray-400 font-normal">(необязательно, общий для пакета)</span></label>
            <textarea value={focus} onChange={(e) => setFocus(e.target.value)} rows={2} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white" />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button onClick={submit} disabled={loading} className="w-full bg-[#1F4E79] hover:bg-[#2E75B6] text-white font-semibold py-2.5 rounded-lg transition disabled:opacity-40 text-sm">
            {loading ? 'Загрузка и запуск...' : '▶ Запустить пакет'}
          </button>
        </div>
      )}

      {batchId && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-gray-500">Пакет: {batchId} · {tasks.length} этикеток</p>
            <div className="flex gap-2">
              <button onClick={() => download('word')} disabled={!done} className="text-xs border border-gray-300 dark:border-gray-600 px-3 py-1 rounded-lg disabled:opacity-40">Сводный Word</button>
              <button onClick={() => download('md')} disabled={!done} className="text-xs border border-gray-300 dark:border-gray-600 px-3 py-1 rounded-lg disabled:opacity-40">Сводный MD</button>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-gray-400 uppercase border-b dark:border-gray-700"><tr><th className="text-left py-2">#</th><th className="text-left py-2">Проверка</th><th className="text-left py-2">Статус</th></tr></thead>
            <tbody>
              {tasks.map((t, i) => (
                <tr key={t.id} className="border-b dark:border-gray-700">
                  <td className="py-2 text-gray-400">{i + 1}</td>
                  <td className="py-2"><a href={`/checks/${t.id}`} className="text-[#2E75B6] hover:underline">{t.id.slice(0, 8)}</a></td>
                  <td className="py-2"><span className={`text-xs px-2 py-0.5 rounded-full ${ST_COLOR[t.status] || ''}`}>{t.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!done && <p className="text-xs text-gray-400 mt-3 animate-pulse">Идёт обработка...</p>}
        </div>
      )}
    </div>
  )
}
