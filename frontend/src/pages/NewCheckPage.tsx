import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { api } from '../api/client'

export default function NewCheckPage() {
  const navigate = useNavigate()
  const [mockupFile, setMockupFile] = useState<File | null>(null)
  const [penFile, setPenFile] = useState<File | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('bad')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [focusPrompt, setFocusPrompt] = useState('')
  const [opts, setOpts] = useState<{ debug_mode: boolean; llm_providers: string[]; ocr_providers: string[] }>({ debug_mode: false, llm_providers: [], ocr_providers: [] })
  const [pmode, setPmode] = useState('') // '' = настройки админки
  const [unifiedLlm, setUnifiedLlm] = useState('')
  const [ocrProvider, setOcrProvider] = useState('')
  const [llmProvider, setLlmProvider] = useState('')

  useEffect(() => { api.get('/checks/pipeline-options').then(({ data }) => setOpts(data)).catch(() => {}) }, [])

  const onDropMockup = useCallback((accepted: File[]) => { if (accepted[0]) setMockupFile(accepted[0]) }, [])
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!mockupFile || !penFile || !productName) { setError('Загрузите макет, ПЭН и укажите название продукта'); return }
    setLoading(true); setError('')
    try {
      const { data: product } = await api.post('/products', { name: productName, category })
      const mf = new FormData(); mf.append('file', mockupFile); mf.append('product_id', product.id)
      const { data: mockup } = await api.post('/uploads/mockup', mf)
      const pf = new FormData(); pf.append('file', penFile); pf.append('product_id', product.id)
      const { data: pen } = await api.post('/uploads/pen', pf)

      // Optional manual-review reference ("Замечание")
      let referenceText: string | null = null
      if (refFile) {
        const rf = new FormData(); rf.append('file', refFile)
        const { data: ref } = await api.post('/uploads/reference', rf)
        referenceText = ref.text
      }

      let pipeline_config: any = null
      if (opts.debug_mode && pmode) {
        pipeline_config = pmode === 'unified'
          ? { pipeline_mode: 'unified', unified_llm: unifiedLlm }
          : { pipeline_mode: 'hybrid', ocr_provider: ocrProvider, llm_provider: llmProvider }
      }
      const { data: check } = await api.post('/checks', {
        mockup_id: mockup.id, pen_id: pen.id, reference_text: referenceText,
        focus_prompt: focusPrompt || null, pipeline_config,
      })
      navigate(`/checks/${check.id}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Произошла ошибка')
    } finally {
      setLoading(false)
    }
  }

  const zoneClass = (active: boolean) =>
    `border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${active ? 'border-[#2E75B6] bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-[#2E75B6]'}`

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-6">Новая проверка</h1>
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

        {opts.debug_mode && (
          <div className="border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-amber-700 dark:text-amber-300">⚙ DEBUG MODE — выбор связки (только из настроенных в админке ключей)</p>
            <select value={pmode} onChange={(e) => setPmode(e.target.value)} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white">
              <option value="">По настройкам админки</option>
              <option value="unified">LLM-only (модель сама читает и проверяет)</option>
              <option value="hybrid">OCR + LLM</option>
            </select>
            {pmode === 'unified' && (
              <select value={unifiedLlm} onChange={(e) => setUnifiedLlm(e.target.value)} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white">
                <option value="">— выберите LLM —</option>
                {opts.llm_providers.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            )}
            {pmode === 'hybrid' && (
              <div className="grid grid-cols-2 gap-2">
                <select value={ocrProvider} onChange={(e) => setOcrProvider(e.target.value)} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white">
                  <option value="">— OCR —</option>
                  {opts.ocr_providers.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <select value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white">
                  <option value="">— LLM —</option>
                  {opts.llm_providers.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            )}
          </div>
        )}

        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" disabled={loading || !mockupFile || !penFile || !productName} className="w-full bg-[#1F4E79] hover:bg-[#2E75B6] text-white font-semibold py-2.5 rounded-lg transition disabled:opacity-40 text-sm">
          {loading ? 'Загрузка и запуск...' : '▶ Запустить проверку'}
        </button>
      </form>
    </div>
  )
}
