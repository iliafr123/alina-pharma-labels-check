import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { api } from '../api/client'

export default function NewCheckPage() {
  const navigate = useNavigate()
  const [mockupFile, setMockupFile] = useState<File | null>(null)
  const [penFile, setPenFile] = useState<File | null>(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('bad')
  const [mode, setMode] = useState('hybrid')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const onDropMockup = useCallback((accepted: File[]) => { if (accepted[0]) setMockupFile(accepted[0]) }, [])
  const onDropPen = useCallback((accepted: File[]) => { if (accepted[0]) setPenFile(accepted[0]) }, [])

  const { getRootProps: getMockupProps, getInputProps: getMockupInput, isDragActive: isDragMockup } = useDropzone({
    onDrop: onDropMockup, accept: { 'application/pdf': ['.pdf'], 'image/jpeg': ['.jpg', '.jpeg'] }, maxFiles: 1,
  })
  const { getRootProps: getPenProps, getInputProps: getPenInput, isDragActive: isDragPen } = useDropzone({
    onDrop: onDropPen, accept: { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] }, maxFiles: 1,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!mockupFile || !penFile || !productName) { setError('Загрузите макет, ПЭН и укажите название продукта'); return }
    setLoading(true); setError('')
    try {
      // Create product
      const { data: product } = await api.post('/products', { name: productName, category })
      // Upload mockup
      const mf = new FormData(); mf.append('file', mockupFile); mf.append('product_id', product.id)
      const { data: mockup } = await api.post('/uploads/mockup', mf)
      // Upload PEN
      const pf = new FormData(); pf.append('file', penFile); pf.append('product_id', product.id)
      const { data: pen } = await api.post('/uploads/pen', pf)
      // Start check
      const { data: check } = await api.post('/checks', { mockup_id: mockup.id, pen_id: pen.id, mode })
      navigate(`/checks/${check.id}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Произошла ошибка')
    } finally {
      setLoading(false)
    }
  }

  const DropZone = ({ props, inputProps, active, file, label }: any) => (
    <div {...props} className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${active ? 'border-[#2E75B6] bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-[#2E75B6]'}`}>
      <input {...inputProps} />
      {file ? (
        <p className="text-sm text-green-600 dark:text-green-400 font-medium">✓ {file.name}</p>
      ) : (
        <p className="text-sm text-gray-500 dark:text-gray-400">{active ? 'Отпустите файл...' : label}</p>
      )}
    </div>
  )

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-6">Новая проверка</h1>
      <form onSubmit={handleSubmit} className="space-y-5 bg-white dark:bg-gray-800 rounded-2xl p-6 shadow">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Название продукта</label>
          <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Витамин C 1000 мг" className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Категория</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]">
              <option value="bad">БАД</option>
              <option value="sport">Спортивное питание</option>
              <option value="grocery">Бакалея</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Режим проверки</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]">
              <option value="hybrid">Гибридный</option>
              <option value="unified">Единый LLM</option>
            </select>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Макет (PDF или JPG)</label>
          <DropZone props={getMockupProps()} inputProps={getMockupInput()} active={isDragMockup} file={mockupFile} label="Перетащите PDF или JPG, или нажмите для выбора" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Эталон ПЭН (DOCX)</label>
          <DropZone props={getPenProps()} inputProps={getPenInput()} active={isDragPen} file={penFile} label="Перетащите DOCX файл ПЭН, или нажмите для выбора" />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" disabled={loading || !mockupFile || !penFile || !productName} className="w-full bg-[#1F4E79] hover:bg-[#2E75B6] text-white font-semibold py-2.5 rounded-lg transition disabled:opacity-40 text-sm">
          {loading ? 'Загрузка и запуск...' : '▶ Запустить проверку'}
        </button>
      </form>
    </div>
  )
}
