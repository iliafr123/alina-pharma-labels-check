import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Tab = 'users' | 'providers' | 'pipeline' | 'storage' | 'logs'

const PROVIDERS_OCR = ['yandex_vision', 'abbyy']
const PROVIDERS_LLM = ['openai', 'anthropic', 'gemini', 'grok']

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>('users')
  const [users, setUsers] = useState<any[]>([])
  const [, setConfig] = useState<any>({})
  const [logs, setLogs] = useState<any[]>([])
  const [newUser, setNewUser] = useState({ email: '', password: '', role: 'specialist' })
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [pipeline, setPipeline] = useState<Record<string, string>>({})
  const [s3, setS3] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<Record<string, string>>({})

  useEffect(() => {
    api.get('/users').then((r) => setUsers(r.data)).catch(() => {})
    api.get('/admin/config').then((r) => {
      setConfig(r.data)
      setApiKeys(r.data.api_keys || {})
      setPipeline(r.data.pipeline || {})
      setS3(r.data.s3 || {})
    }).catch(() => {})
    api.get('/admin/logs').then((r) => setLogs(r.data)).catch(() => {})
  }, [])

  const createUser = async () => {
    const { data } = await api.post('/users', newUser)
    setUsers([...users, data])
    setNewUser({ email: '', password: '', role: 'specialist' })
  }
  const deactivateUser = async (id: string) => {
    await api.delete(`/users/${id}`)
    setUsers(users.map((u) => u.id === id ? { ...u, is_active: false } : u))
  }

  const saveConfig = async () => {
    setSaving(true)
    await api.put('/admin/config', { api_keys: apiKeys, pipeline, s3 })
    setSaving(false)
    alert('Конфигурация сохранена')
  }

  const testConn = async (type: string, name: string) => {
    setTestResult((prev) => ({ ...prev, [name]: '...' }))
    const { data } = await api.post('/admin/config/test-connection', { provider_type: type, provider_name: name })
    setTestResult((prev) => ({ ...prev, [name]: data.success ? '✓ OK' : `✗ ${data.message}` }))
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'users', label: 'Пользователи' },
    { key: 'providers', label: 'Провайдеры AI/OCR' },
    { key: 'pipeline', label: 'Конфигурация пайплайна' },
    { key: 'storage', label: 'Хранилище (Selectel)' },
    { key: 'logs', label: 'Логи' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-5">Администрирование</h1>
      <div className="flex gap-2 mb-5 flex-wrap">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === t.key ? 'bg-[#1F4E79] text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
        {tab === 'users' && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-5">
              <input value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} placeholder="Email" className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white" />
              <input value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} placeholder="Пароль" type="password" className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white" />
              <div className="flex gap-2">
                <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                  <option value="specialist">Специалист</option>
                  <option value="admin">Администратор</option>
                </select>
                <button onClick={createUser} className="bg-[#1F4E79] text-white px-3 py-1.5 rounded-lg text-sm">Создать</button>
              </div>
            </div>
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-400 uppercase border-b dark:border-gray-700">
                <tr>
                  <th className="text-left py-2">Email</th>
                  <th className="text-left py-2">Роль</th>
                  <th className="text-left py-2">Статус</th>
                  <th className="text-left py-2">Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b dark:border-gray-700">
                    <td className="py-2">{u.email}</td>
                    <td className="py-2 text-gray-500">{u.role}</td>
                    <td className="py-2"><span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{u.is_active ? 'Активен' : 'Деактивирован'}</span></td>
                    <td className="py-2">
                      {u.is_active && <button onClick={() => deactivateUser(u.id)} className="text-xs text-red-400 hover:text-red-600">Деактивировать</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === 'providers' && (
          <div className="space-y-6">
            {[{ label: 'OCR-провайдеры', items: PROVIDERS_OCR, type: 'ocr' }, { label: 'LLM-провайдеры', items: PROVIDERS_LLM, type: 'llm' }].map((group) => (
              <div key={group.label}>
                <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-300 mb-3">{group.label}</h3>
                <div className="grid grid-cols-2 gap-3">
                  {group.items.map((name) => (
                    <div key={name} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                      <p className="text-sm font-medium mb-2 capitalize">{name.replace('_', ' ')}</p>
                      <div className="flex gap-2">
                        <input value={apiKeys[name] || ''} onChange={(e) => setApiKeys({ ...apiKeys, [name]: e.target.value })} placeholder="API ключ" type="password" className="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                        <button onClick={() => testConn(group.type, name)} className="text-xs bg-gray-100 dark:bg-gray-600 hover:bg-gray-200 px-2 py-1 rounded">Тест</button>
                      </div>
                      {testResult[name] && <p className={`text-xs mt-1 ${testResult[name].startsWith('✓') ? 'text-green-500' : 'text-red-500'}`}>{testResult[name]}</p>}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <button onClick={saveConfig} disabled={saving} className="bg-[#1F4E79] text-white px-5 py-2 rounded-lg text-sm">{saving ? 'Сохранение...' : 'Сохранить ключи'}</button>
          </div>
        )}

        {tab === 'pipeline' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Режим пайплайна</label>
              <select value={pipeline.pipeline_mode || 'hybrid'} onChange={(e) => setPipeline({ ...pipeline, pipeline_mode: e.target.value })} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                <option value="hybrid">Гибридный режим</option>
                <option value="unified">Единый LLM</option>
              </select>
            </div>
            {pipeline.pipeline_mode !== 'unified' ? (
              <>
                {[['ocr_provider', 'Этап 1: OCR'], ['llm_provider', 'Этап 2–4: LLM (орфография, ПЭН, нормативный)']].map(([key, label]) => (
                  <div key={key}>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
                    <select value={pipeline[key] || ''} onChange={(e) => setPipeline({ ...pipeline, [key]: e.target.value })} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                      <option value="">Выбрать...</option>
                      <option value="yandex_vision">Yandex Vision</option>
                      <option value="anthropic_vision">Claude Vision (OCR)</option>
                      <option value="openai">OpenAI GPT-4o</option>
                      <option value="anthropic">Anthropic Claude</option>
                      <option value="gemini">Google Gemini</option>
                      <option value="grok">xAI Grok</option>
                    </select>
                  </div>
                ))}
              </>
            ) : (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Единая модель LLM</label>
                <select value={pipeline.unified_llm || ''} onChange={(e) => setPipeline({ ...pipeline, unified_llm: e.target.value })} className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                  <option value="">Выбрать...</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="openai">OpenAI GPT-4o</option>
                  <option value="gemini">Google Gemini</option>
                  <option value="grok">xAI Grok</option>
                </select>
              </div>
            )}
            <button onClick={saveConfig} disabled={saving} className="bg-[#1F4E79] text-white px-5 py-2 rounded-lg text-sm">{saving ? 'Сохранение...' : 'Сохранить конфигурацию'}</button>
          </div>
        )}

        {tab === 'storage' && (
          <div className="space-y-3 max-w-md">
            {[['endpoint_url', 'Endpoint URL'], ['bucket', 'Bucket'], ['access_key', 'Access Key'], ['secret_key', 'Secret Key'], ['region', 'Регион']].map(([key, label]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
                <input value={s3[key] || ''} onChange={(e) => setS3({ ...s3, [key]: e.target.value })} type={['access_key', 'secret_key'].includes(key) ? 'password' : 'text'} className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white" />
              </div>
            ))}
            <div className="flex gap-3">
              <button onClick={() => testConn('storage', 'storage')} className="text-sm border border-gray-300 dark:border-gray-600 px-4 py-1.5 rounded-lg">Проверить подключение</button>
              <button onClick={saveConfig} disabled={saving} className="bg-[#1F4E79] text-white px-5 py-1.5 rounded-lg text-sm">{saving ? '...' : 'Сохранить'}</button>
            </div>
            {testResult['storage'] && <p className={`text-sm ${testResult['storage'].startsWith('✓') ? 'text-green-500' : 'text-red-500'}`}>{testResult['storage']}</p>}
          </div>
        )}

        {tab === 'logs' && (
          <div className="space-y-1 max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-400 uppercase border-b dark:border-gray-700">
                <tr>
                  <th className="text-left py-2">Время</th>
                  <th className="text-left py-2">Действие</th>
                  <th className="text-left py-2">Ресурс</th>
                  <th className="text-left py-2">IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b dark:border-gray-700">
                    <td className="py-1.5 text-gray-400">{new Date(l.created_at).toLocaleString('ru-RU')}</td>
                    <td className="py-1.5 font-medium">{l.action}</td>
                    <td className="py-1.5 text-gray-500">{l.resource_type}</td>
                    <td className="py-1.5 text-gray-400">{l.ip || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
