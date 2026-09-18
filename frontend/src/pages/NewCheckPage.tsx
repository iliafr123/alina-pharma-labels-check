import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { api } from '../api/client'
import { errorTitle, errorHint } from '../lib/errors'
import {
  blockers, canSubmit, qualityTone, formatBalance,
  type QualityReport, type PipelineOptions,
} from '../lib/checkGuards'

export default function NewCheckPage() {
  const navigate = useNavigate()
  const [mockupFile, setMockupFile] = useState<File | null>(null)
  const [penFile, setPenFile] = useState<File | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('bad')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [errorFix, setErrorFix] = useState('')
  const [focusPrompt, setFocusPrompt] = useState('')

  const [quality, setQuality] = useState<QualityReport | null>(null)
  const [qualityChecking, setQualityChecking] = useState(false)
  const [qualityError, setQualityError] = useState('')
  const [options, setOptions] = useState<PipelineOptions | null>(null)
  const [balance, setBalance] = useState<any>(null)

  useEffect(() => {
    api.get('/checks/pipeline-options').then((r) => setOptions(r.data)).catch(() => {})
    api.get('/checks/provider-balance').then((r) => setBalance(r.data.balance)).catch(() => {})
  }, [])

  // Judge the mockup as soon as it is chosen: the user finds out about an unusable
  // file while still at the file picker, not after a failed check.
  const runQualityCheck = useCallback(async (file: File) => {
    setQualityChecking(true); setQuality(null); setQualityError('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const { data } = await api.post('/uploads/quality-check', fd)
      setQuality(data)
    } catch (e: any) {
      setQualityError([errorTitle(e, 'Не удалось оценить качество макета'), errorHint(e)]
        .filter(Boolean).join(' '))
    } finally {
      setQualityChecking(false)
    }
  }, [])

  const onDropMockup = useCallback((accepted: File[]) => {
    if (accepted[0]) { setMockupFile(accepted[0]); runQualityCheck(accepted[0]) }
  }, [runQualityCheck])
  const onDropPen = useCallback((accepted: File[]) => { if (accepted[0]) setPenFile(accepted[0]) }, [])
  const onDropRef = useCallback((accepted: File[]) => { if (accepted[0]) setRefFile(accepted[0]) }, [])

  const { getRootProps: getMockupProps, getInputProps: getMockupInput, isDragActive: isDragMockup } = useDropzone({
    onDrop: onDropMockup, accept: { 'application/pdf': ['.pdf'], 'image/jpeg': ['.jpg', '.jpeg'] }, maxFiles: 1,
  })
  const { getRootProps: getPenProps, getInputProps: getPenInput, isDragActive: isDragPen } = useDropzone({
    onDrop: onDropPen, accept: { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] }, maxFiles: 1,
  })
  const { getRootProps: getRefProps, getInputProps: getRefInput, isDragActive: isDragRef } = useDropzone({
    onDrop: onDropRef,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxFiles: 1,
  })

  const formState = {
    productName, mockupFile, penFile, quality, qualityChecking, qualityError,
    options, submitting: loading,
  }
  const reasons = blockers(formState)
  const ready = canSubmit(formState)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ready) return
    setLoading(true); setError(''); setErrorFix('')
    try {
      const { data: product } = await api.post('/products', { name: productName, category })
      const mf = new FormData(); mf.append('file', mockupFile!); mf.append('product_id', product.id)
      const { data: mockup } = await api.post('/uploads/mockup', mf)
      const pf = new FormData(); pf.append('file', penFile!); pf.append('product_id', product.id)
      const { data: pen } = await api.post('/uploads/pen', pf)

      // Optional manual-review reference ("Замечание")
      let referenceText: string | null = null
      if (refFile) {
        const rf = new FormData(); rf.append('file', refFile)
        const { data: ref } = await api.post('/uploads/reference', rf)
        referenceText = ref.text
      }

      const { data: check } = await api.post('/checks', {
        mockup_id: mockup.id, pen_id: pen.id, reference_text: referenceText,
        focus_prompt: focusPrompt || null,
      })
      navigate(`/checks/${check.id}`)
    } catch (e: any) {
      setError(errorTitle(e))
      setErrorFix(errorHint(e))
    } finally {
      setLoading(false)
    }
  }

  const zoneClass = (active: boolean) =>
    `border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${active ? 'border-[#2E75B6] bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-[#2E75B6]'}`

  const tone = quality ? qualityTone(quality.level) : null

  return (
    <div className="max-w-2xl">
      <div className="flex items-start justify-between mb-6 gap-4">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-white">Новая проверка</h1>
        {balance && <BalanceChip balance={balance} />}
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 bg-white dark:bg-gray-800 rounded-2xl p-6 shadow">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Название продукта</label>
          <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Витамин C 1000 мг" className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Категория</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]">
            <option value="bad">БАД</option>
            <option value="sport">Спортивное питание</option>
            <option value="grocery">Бакалея</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Макет (PDF или JPG)</label>
          <div {...getMockupProps()} className={zoneClass(isDragMockup)}>
            <input {...getMockupInput()} />
            {mockupFile ? (
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">✓ {mockupFile.name}</p>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">{isDragMockup ? 'Отпустите файл...' : 'Перетащите PDF или JPG, или нажмите для выбора'}</p>
            )}
          </div>

          {qualityChecking && (
            <p className="text-xs text-gray-400 mt-2">Оцениваем качество макета…</p>
          )}
          {qualityError && (
            <p className="text-xs text-red-500 mt-2">{qualityError}</p>
          )}
          {quality && tone && (
            <div className={`mt-2 rounded-lg border p-3 text-xs dark:bg-opacity-20 ${tone.cls}`}>
              <div className="flex items-center justify-between gap-3 mb-1">
                <span className="font-semibold">
                  {quality.ok ? (quality.level === 'excellent' ? '✓ ' : '⚠ ') : '✗ '}{tone.label}
                </span>
                <span className="opacity-70">
                  {quality.score}/100
                  {quality.metrics?.effective_dpi ? ` · ~${quality.metrics.effective_dpi} dpi` : ''}
                </span>
              </div>
              <p className="opacity-90">{quality.summary}</p>
              {(quality.problems || []).map((p, i) => (
                <div key={i} className="mt-1.5">
                  <p className="font-medium">• {p.message}</p>
                  {p.hint && <p className="opacity-75 pl-3">{p.hint}</p>}
                </div>
              ))}
              {(quality.advice || []).length > 0 && (
                <p className="mt-2 font-medium">Что сделать: {quality.advice!.join('; ')}.</p>
              )}
            </div>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Эталон ПЭН (DOCX)</label>
          <div {...getPenProps()} className={zoneClass(isDragPen)}>
            <input {...getPenInput()} />
            {penFile ? (
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">✓ {penFile.name}</p>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">{isDragPen ? 'Отпустите файл...' : 'Перетащите DOCX файл ПЭН, или нажмите для выбора'}</p>
            )}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Замечание — результат ручной проверки <span className="text-gray-400 font-normal">(необязательно, PDF/DOCX/TXT)</span>
          </label>
          <div {...getRefProps()} className={zoneClass(isDragRef)}>
            <input {...getRefInput()} />
            {refFile ? (
              <div className="flex items-center justify-center gap-3">
                <p className="text-sm text-green-600 dark:text-green-400 font-medium">✓ {refFile.name}</p>
                <button type="button" onClick={(ev) => { ev.stopPropagation(); setRefFile(null) }} className="text-xs text-red-400 hover:text-red-600">убрать</button>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">{isDragRef ? 'Отпустите файл...' : 'Если приложить — система сравнит свой результат с вашей ручной проверкой'}</p>
            )}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Фокус проверки <span className="text-gray-400 font-normal">(необязательно — на чём LLM сделать акцент)</span>
          </label>
          <textarea value={focusPrompt} onChange={(e) => setFocusPrompt(e.target.value)} rows={2}
            placeholder="Напр.: проверь только состав и соответствие номеров ТР ТС; не придирайся к регистру и тире"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]" />
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/30 dark:border-red-800 p-3">
            <p className="text-red-600 dark:text-red-300 text-sm font-medium">{error}</p>
            {errorFix && <p className="text-red-500 dark:text-red-400 text-xs mt-1">{errorFix}</p>}
          </div>
        )}

        {/* Why the button is off - the list and the disabled state come from the same function. */}
        {!ready && reasons.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800 p-3">
            <p className="text-xs font-semibold text-amber-800 dark:text-amber-300 mb-1">
              Проверку пока нельзя запустить:
            </p>
            <ul className="space-y-1">
              {reasons.map((r) => (
                <li key={r.code} className="text-xs text-amber-800 dark:text-amber-200">
                  • {r.text}
                  {r.fix && <span className="block pl-3 opacity-75">{r.fix}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          type="submit"
          disabled={!ready}
          title={ready ? 'Запустить проверку' : reasons.map((r) => r.text).join('\n')}
          className="w-full bg-[#1F4E79] hover:bg-[#2E75B6] text-white font-semibold py-2.5 rounded-lg transition disabled:opacity-40 disabled:cursor-not-allowed text-sm"
        >
          {loading ? 'Загрузка и запуск...' : '▶ Запустить проверку'}
        </button>
      </form>
    </div>
  )
}

/** Remaining balance of the model this check will actually use. */
function BalanceChip({ balance }: { balance: any }) {
  const known = balance.status === 'ok' || balance.status === 'manual'
  const stale = balance.status === 'manual'
  return (
    <div
      className={`rounded-lg border px-3 py-2 text-xs max-w-xs ${
        known ? 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
              : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'}`}
      title={balance.message || ''}
    >
      <p className="text-gray-400">Баланс · {balance.label}</p>
      <p className="font-semibold text-gray-700 dark:text-gray-200">
        {known ? formatBalance(balance) : 'нет данных'}
      </p>
      {stale && balance.as_of && (
        <p className="text-[10px] text-gray-400 mt-0.5">
          указано вручную {new Date(balance.as_of).toLocaleDateString('ru-RU')}
        </p>
      )}
      {!known && (
        <p className="text-[10px] text-gray-400 mt-0.5">
          {balance.status === 'unsupported' ? 'провайдер не отдаёт остаток по API' : balance.message}
        </p>
      )}
    </div>
  )
}
