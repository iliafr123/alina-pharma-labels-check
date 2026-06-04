import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Tab = 'dictionary' | 'brands' | 'checklist'

export default function ReferencesPage() {
  const [tab, setTab] = useState<Tab>('dictionary')
  const [dict, setDict] = useState<any[]>([])
  const [brands, setBrands] = useState<any[]>([])
  const [rules, setRules] = useState<any[]>([])
  const [newTerm, setNewTerm] = useState('')
  const [newBrand, setNewBrand] = useState('')

  useEffect(() => {
    api.get('/references/dictionary').then((r) => setDict(r.data)).catch(() => {})
    api.get('/references/brands').then((r) => setBrands(r.data)).catch(() => {})
    api.get('/references/checklist').then((r) => setRules(r.data)).catch(() => {})
  }, [])

  const addTerm = async () => {
    if (!newTerm.trim()) return
    const { data } = await api.post('/references/dictionary', { term: newTerm, category: 'general' })
    setDict([...dict, data]); setNewTerm('')
  }
  const deleteTerm = async (id: string) => {
    await api.delete(`/references/dictionary/${id}`)
    setDict(dict.filter((e) => e.id !== id))
  }
  const addBrand = async () => {
    if (!newBrand.trim()) return
    const { data } = await api.post('/references/brands', { brand_name: newBrand })
    setBrands([...brands, data]); setNewBrand('')
  }
  const deleteBrand = async (id: string) => {
    await api.delete(`/references/brands/${id}`)
    setBrands(brands.filter((b) => b.id !== id))
  }
  const toggleRule = async (id: string, is_active: boolean) => {
    await api.put(`/references/checklist/${id}`, { is_active: !is_active })
    setRules(rules.map((r) => r.id === id ? { ...r, is_active: !is_active } : r))
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'dictionary', label: 'Отраслевой словарь' },
    { key: 'brands', label: 'Бренды и ТЗ' },
    { key: 'checklist', label: 'Нормативный чек-лист' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-5">Справочники</h1>
      <div className="flex gap-2 mb-5">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === t.key ? 'bg-[#1F4E79] text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
        {tab === 'dictionary' && (
          <>
            <div className="flex gap-2 mb-4">
              <input value={newTerm} onChange={(e) => setNewTerm(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addTerm()} placeholder="Добавить термин..." className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]" />
              <button onClick={addTerm} className="bg-[#1F4E79] text-white px-4 py-1.5 rounded-lg text-sm">Добавить</button>
            </div>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {dict.map((e) => (
                <div key={e.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <span className="text-sm text-gray-700 dark:text-gray-200">{e.term}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{e.category}</span>
                    <button onClick={() => deleteTerm(e.id)} className="text-xs text-red-400 hover:text-red-600">удалить</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === 'brands' && (
          <>
            <div className="flex gap-2 mb-4">
              <input value={newBrand} onChange={(e) => setNewBrand(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addBrand()} placeholder="Добавить бренд..." className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2E75B6]" />
              <button onClick={addBrand} className="bg-[#1F4E79] text-white px-4 py-1.5 rounded-lg text-sm">Добавить</button>
            </div>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {brands.map((b) => (
                <div key={b.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <span className="text-sm text-gray-700 dark:text-gray-200">{b.brand_name}</span>
                  <button onClick={() => deleteBrand(b.id)} className="text-xs text-red-400 hover:text-red-600">удалить</button>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === 'checklist' && (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {rules.map((r) => (
              <div key={r.id} className="flex items-start gap-3 py-2 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <input type="checkbox" checked={r.is_active} onChange={() => toggleRule(r.id, r.is_active)} className="mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-gray-700 dark:text-gray-200">{r.description}</p>
                  <p className="text-xs text-gray-400">{r.category} · {r.rule_key}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
