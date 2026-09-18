import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { errorMessage, SUBSYSTEM_LABELS, STAGE_LABELS } from '../lib/errors'
import { formatBalance } from '../lib/checkGuards'

type Tab = 'users' | 'providers' | 'pipeline' | 'storage' | 'references' | 'balances' | 'errors' | 'logs'

const CURRENCIES = ['RUB', 'USD', 'EUR', 'ILS']

const QUALITY_LABELS: Record<string, string> = {
  px_per_mm_min: 'Минимум пикс/мм (ниже — проверка блокируется)',
  px_per_mm_good: 'Пикс/мм для оценки «отлично»',
  sharpness_min: 'Минимальная резкость (ниже — размыто)',
  sharpness_good: 'Резкость для оценки «отлично»',
  contrast_min: 'Минимальный контраст (ниже — пустая страница)',
  jpg_side_min: 'Минимум пикселей по длинной стороне (JPG без dpi)',
  jpg_side_good: 'Рекомендуемый размер JPG по длинной стороне',
}

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
  const [extras, setExtras] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<Record<string, string>>({})
  const [debugMode, setDebugMode] = useState(false)
  const [importMsg, setImportMsg] = useState<Record<string, string>>({})
  const [quality, setQuality] = useState<Record<string, any>>({})
  const [qualityDefaults, setQualityDefaults] = useState<Record<string, any>>({})
  const [errors, setErrors] = useState<any[]>([])
  const [errSummary, setErrSummary] = useState<any>(null)
  const [errFilter, setErrFilter] = useState({ subsystem: '', source: '', search: '' })
  const [errLoading, setErrLoading] = useState(false)
  const [balances, setBalances] = useState<any[]>([])
  const [rates, setRates] = useState<Record<string, number>>({})
  const [balLoading, setBalLoading] = useState(false)
  const [manual, setManual] = useState<Record<string, { amount: string; currency: string; note: string }>>({})
  const [banner, setBanner] = useState('')

  useEffect(() => {
    api.get('/users').then((r) => setUsers(r.data)).catch(() => {})
    api.get('/admin/config').then((r) => {
      setConfig(r.data)
      setApiKeys(r.data.api_keys || {})
      setPipeline(r.data.pipeline || {})
      setS3(r.data.s3 || {})
      setExtras(r.data.extras || {})
      setDebugMode(r.data.debug_mode || false)
      setQuality(r.data.quality || {})
      setQualityDefaults(r.data.quality_defaults || {})
    }).catch(() => {})
    api.get('/admin/logs').then((r) => setLogs(r.data)).catch(() => {})
  }, [])

  const loadErrors = async () => {
    setErrLoading(true)
    try {
      const [list, summary] = await Promise.all([
        api.get('/admin/errors', { params: { ...errFilter, limit: 200 } }),
        api.get('/admin/errors/summary', { params: { hours: 24 } }),
      ])
      setErrors(list.data); setErrSummary(summary.data)
    } catch (e: any) { setBanner(errorMessage(e, 'Не удалось загрузить журнал ошибок')) }
    finally { setErrLoading(false) }
  }

  const loadBalances = async () => {
    setBalLoading(true)
    try {
      const { data } = await api.get('/admin/balances')
      setBalances(data.balances || []); setRates(data.rates || {})
      const seed: Record<string, any> = {}
      for (const b of data.balances || []) {
        seed[b.provider] = {
          amount: b.manual?.amount != null ? String(b.manual.amount) : '',
          currency: b.manual?.currency || 'RUB',
          note: b.manual?.note || '',
        }
      }
      setManual(seed)
    } catch (e: any) { setBanner(errorMessage(e, 'Не удалось получить балансы')) }
    finally { setBalLoading(false) }
  }

  useEffect(() => { if (tab === 'errors') loadErrors() }, [tab])
  useEffect(() => { if (tab === 'balances') loadBalances() }, [tab])

  const saveManualBalance = async (provider: string) => {
    const m = manual[provider] || { amount: '', currency: 'RUB', note: '' }
    try {
      await api.put(`/admin/balances/${provider}`, {
        amount: m.amount === '' ? null : Number(m.amount),
        currency: m.currency, note: m.note,
      })
      await loadBalances()
      setBanner('Баланс сохранён')
    } catch (e: any) { setBanner(errorMessage(e, 'Не удалось сохранить')) }
  }

  const clearErrors = async () => {
    if (!window.confirm('Очистить журнал ошибок? Действие необратимо.')) return
    try { await api.delete('/admin/errors'); await loadErrors() }
    catch (e: any) { setBanner(errorMessage(e, 'Не удалось очистить')) }
  }

  const createUser = async () => {
    const { data } = await api.post('/users', newUser)
    setUsers([...users, data])
    setNewUser({ email: '', password: '', role: 'specialist' })
  }
  const deactivateUser = async (id: string) => {
    await api.delete(`/users/${id}`)
    setUsers(users.map((u) => u.id === id ? { ...u, is_active: false } : u))
  }
  const setUserPassword = async (id: string, email: string) => {
    const p = window.prompt(`Новый пароль для ${email} (не короче 6 символов):`)
    if (!p) return
    try { await api.put(`/users/${id}`, { password: p }); alert('Пароль изменён') }
    catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка') }
  }

  const saveConfig = async () => {
    setSaving(true)
    try {
      await api.put('/admin/config', { api_keys: apiKeys, pipeline, s3, extras, debug_mode: debugMode, quality })
      setBanner('Конфигурация сохранена')
    } catch (e: any) {
      setBanner(errorMessage(e, 'Не удалось сохранить конфигурацию'))
    } finally {
      setSaving(false)
    }
  }

  const importRef = async (kind: string, file: File) => {
    setImportMsg((p) => ({ ...p, [kind]: '...' }))
    try {
      const fd = new FormData(); fd.append('file', file)
      const { data } = await api.post(`/admin/import/${kind}`, fd)
      setImportMsg((p) => ({ ...p, [kind]: `✓ Добавлено ${data.added} из ${data.rows} строк` }))
    } catch (e: any) {
      setImportMsg((p) => ({ ...p, [kind]: `✗ ${e?.response?.data?.detail || 'Ошибка'}` }))
    }
  }

  const testConn = async (type: string, name: string) => {
    setTestResult((prev) => ({ ...prev, [name]: '...' }))
    try {
      // Persist current keys/config first — the server-side test reads the SAVED key from the DB.
      await api.put('/admin/config', { api_keys: apiKeys, pipeline, s3, extras })
      const { data } = await api.post('/admin/config/test-connection', { provider_type: type, provider_name: name })
      setTestResult((prev) => ({ ...prev, [name]: data.success ? '✓ OK' : `✗ ${data.message}` }))
    } catch (e: any) {
      setTestResult((prev) => ({ ...prev, [name]: `✗ ${e?.response?.data?.detail || e?.message || 'Ошибка'}` }))
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'users', label: 'Пользователи' },
    { key: 'providers', label: 'Провайдеры AI/OCR' },
    { key: 'pipeline', label: 'Конфигурация пайплайна' },
    { key: 'storage', label: 'Хранилище (Selectel)' },
    { key: 'references', label: 'Справочники' },
    { key: 'balances', label: 'Балансы' },
    { key: 'errors', label: 'Ошибки' },
    { key: 'logs', label: 'Действия' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-5">Администрирование</h1>
      {banner && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-800 px-3 py-2 flex items-start justify-between gap-3">
          <p className="text-sm text-blue-800 dark:text-blue-200">{banner}</p>
          <button onClick={() => setBanner('')} className="text-xs text-blue-400">x</button>
        </div>
      )}
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
                      <div className="flex gap-3">
                        <button onClick={() => setUserPassword(u.id, u.email)} className="text-xs text-[#2E75B6] hover:underline">Сменить пароль</button>
                        {u.is_active && <button onClick={() => deactivateUser(u.id)} className="text-xs text-red-400 hover:text-red-600">Деактивировать</button>}
                      </div>
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
                        <input value={apiKeys[name] || ''} onChange={(e) => setApiKeys({ ...apiKeys, [name]: e.target.value })} placeholder={name === 'abbyy' ? 'Application ID' : 'API ключ'} type={name === 'abbyy' ? 'text' : 'password'} className="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                        <button onClick={() => testConn(group.type, name)} className="text-xs bg-gray-100 dark:bg-gray-600 hover:bg-gray-200 px-2 py-1 rounded">Тест</button>
                      </div>
                      {name === 'yandex_vision' && (
                        <input value={extras.yandex_folder_id || ''} onChange={(e) => setExtras({ ...extras, yandex_folder_id: e.target.value })} placeholder="Folder ID (каталог, напр. b1g...)" className="w-full mt-2 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                      )}
                      {name === 'abbyy' && (
                        <input value={extras.abbyy_password || ''} onChange={(e) => setExtras({ ...extras, abbyy_password: e.target.value })} placeholder="Application Password" type="password" className="w-full mt-2 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                      )}
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
                      {key === 'ocr_provider' ? (
                        <>
                          <option value="yandex_vision">Yandex Vision</option>
                          <option value="abbyy">ABBYY Cloud OCR</option>
                          <option value="gemini">Google Gemini (vision)</option>
                          <option value="openai">OpenAI GPT-4o (vision)</option>
                          <option value="anthropic_vision">Claude (vision)</option>
                        </>
                      ) : (
                        <>
                          <option value="gemini">Google Gemini</option>
                          <option value="openai">OpenAI GPT-4o</option>
                          <option value="anthropic">Anthropic Claude</option>
                          <option value="grok">xAI Grok</option>
                        </>
                      )}
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
            <div className="border-t dark:border-gray-700 pt-4 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={debugMode} onChange={(e) => setDebugMode(e.target.checked)} className="w-4 h-4" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">DEBUG MODE</span>
              </label>
              <p className="text-xs text-gray-400 mt-1">Когда включён — в экране «Новая проверка» можно выбрать любую связку OCR+LLM (только из настроенных здесь ключей). Для подбора и тестов.</p>
            </div>
            <div className="border-t dark:border-gray-700 pt-4 mt-2">
              <p className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1">Порог качества макета</p>
              <p className="text-xs text-gray-400 mb-3">
                Значения откалиброваны по реальным этикеткам «Алина Фарма»: все макеты,
                которые распознавались корректно, проходят с запасом. Меняйте, только если
                проверка начала отклонять нормальные файлы. Пустое поле — значение по умолчанию.
              </p>
              <div className="grid grid-cols-2 gap-3">
                {Object.keys(QUALITY_LABELS).map((key) => (
                  <div key={key}>
                    <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">{QUALITY_LABELS[key]}</label>
                    <input
                      value={quality[key] ?? ''}
                      onChange={(e) => setQuality({ ...quality, [key]: e.target.value })}
                      placeholder={String(qualityDefaults[key] ?? '')}
                      className="w-full border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                    <p className="text-[10px] text-gray-400 mt-0.5">по умолчанию {String(qualityDefaults[key] ?? '—')}</p>
                  </div>
                ))}
              </div>
            </div>
            <button onClick={saveConfig} disabled={saving} className="bg-[#1F4E79] text-white px-5 py-2 rounded-lg text-sm">{saving ? 'Сохранение...' : 'Сохранить конфигурацию'}</button>
          </div>
        )}

        {tab === 'balances' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Остаток средств у провайдеров. Курсы ЦБ РФ:{' '}
                {Object.entries(rates).filter(([k]) => k !== 'RUB')
                  .map(([k, v]) => `${k} ${Number(v).toFixed(2)} Р`).join(' · ') || '—'}
              </p>
              <button onClick={loadBalances} className="text-xs border border-gray-300 dark:border-gray-600 px-3 py-1 rounded-lg">
                {balLoading ? '...' : 'Обновить'}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {balances.map((b) => (
                <div key={b.provider} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-100">{b.label}</p>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap ${
                      b.status === 'ok' ? 'bg-green-100 text-green-700'
                      : b.status === 'manual' ? 'bg-blue-100 text-blue-700'
                      : b.status === 'error' ? 'bg-red-100 text-red-700'
                      : 'bg-gray-100 text-gray-500'}`}>
                      {b.status === 'ok' ? 'из API'
                        : b.status === 'manual' ? 'вручную'
                        : b.status === 'error' ? 'ошибка'
                        : b.status === 'not_configured' ? 'не настроено' : 'нет API'}
                    </span>
                  </div>

                  <p className="text-xl font-bold text-gray-800 dark:text-white mt-1">
                    {b.status === 'ok' || b.status === 'manual' ? formatBalance(b) : '—'}
                  </p>
                  {b.as_of && (
                    <p className="text-[10px] text-gray-400">
                      на {new Date(b.as_of).toLocaleString('ru-RU')}
                    </p>
                  )}
                  {b.message && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{b.message}</p>}
                  {b.hint && <p className="text-xs text-gray-400 mt-1">{b.hint}</p>}
                  {b.console_url && (
                    <a href={b.console_url} target="_blank" rel="noreferrer" className="text-xs text-[#2E75B6] hover:underline">
                      Открыть консоль провайдера
                    </a>
                  )}

                  {/* Manual entry for providers that expose no balance API. */}
                  {b.status !== 'ok' && (
                    <div className="mt-3 pt-2 border-t dark:border-gray-700">
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-1">Указать остаток вручную:</p>
                      <div className="flex gap-1">
                        <input
                          value={manual[b.provider]?.amount ?? ''}
                          onChange={(e) => setManual({ ...manual, [b.provider]: { ...(manual[b.provider] || { currency: 'RUB', note: '' }), amount: e.target.value } })}
                          placeholder="58"
                          className="w-20 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-white" />
                        <select
                          value={manual[b.provider]?.currency ?? 'RUB'}
                          onChange={(e) => setManual({ ...manual, [b.provider]: { ...(manual[b.provider] || { amount: '', note: '' }), currency: e.target.value } })}
                          className="border border-gray-300 dark:border-gray-600 rounded px-1 py-1 text-xs dark:bg-gray-700 dark:text-white">
                          {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <button onClick={() => saveManualBalance(b.provider)} className="text-xs bg-[#1F4E79] text-white px-2 py-1 rounded">
                          OK
                        </button>
                      </div>
                      <p className="text-[10px] text-gray-400 mt-1">
                        Пустое поле + OK — убрать значение. Пересчёт в рубли по курсу ЦБ.
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'errors' && (
          <div className="space-y-3">
            {errSummary && (
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  За 24 часа: <b>{errSummary.total}</b>
                </span>
                {(errSummary.by_code || []).slice(0, 6).map((c: any) => (
                  <button key={`${c.code}-${c.provider}`} onClick={() => setErrFilter({ ...errFilter, search: c.code })}
                    className="text-[11px] bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 rounded-full px-2 py-0.5 font-mono">
                    {c.code} x {c.count}
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-2 flex-wrap">
              <input value={errFilter.search} onChange={(e) => setErrFilter({ ...errFilter, search: e.target.value })}
                placeholder="Поиск по коду или тексту"
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white w-64" />
              <select value={errFilter.subsystem} onChange={(e) => setErrFilter({ ...errFilter, subsystem: e.target.value })}
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                <option value="">Все подсистемы</option>
                {Object.entries(SUBSYSTEM_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <select value={errFilter.source} onChange={(e) => setErrFilter({ ...errFilter, source: e.target.value })}
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 text-sm dark:bg-gray-700 dark:text-white">
                <option value="">Везде</option>
                <option value="api">API</option>
                <option value="worker">Worker</option>
              </select>
              <button onClick={loadErrors} className="text-sm border border-gray-300 dark:border-gray-600 px-3 py-1.5 rounded-lg">
                {errLoading ? '...' : 'Показать'}
              </button>
              <button onClick={clearErrors} className="text-sm text-red-500 border border-red-200 px-3 py-1.5 rounded-lg ml-auto">
                Очистить журнал
              </button>
            </div>

            <div className="space-y-2 max-h-[60vh] overflow-y-auto">
              {errors.length === 0 && (
                <p className="text-center text-gray-400 text-sm py-8">Ошибок не зафиксировано</p>
              )}
              {errors.map((e) => (
                <div key={e.id} className={`rounded-lg border p-3 ${
                  e.severity === 'warning'
                    ? 'border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20 dark:border-yellow-800'
                    : 'border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-100">{e.title}</p>
                    <span className="text-[10px] font-mono text-gray-400 whitespace-nowrap">{e.code}</span>
                  </div>
                  {e.hint && <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">{e.hint}</p>}
                  <p className="text-[11px] text-gray-400 mt-1">
                    {[
                      new Date(e.created_at).toLocaleString('ru-RU'),
                      e.source === 'worker' ? 'worker' : 'API',
                      e.subsystem && SUBSYSTEM_LABELS[e.subsystem],
                      e.provider,
                      e.stage && `этап: ${STAGE_LABELS[e.stage] || e.stage}`,
                      e.path,
                      e.task_id && `проверка ${String(e.task_id).slice(0, 8)}`,
                    ].filter(Boolean).join(' · ')}
                  </p>
                  {(e.detail || e.traceback) && (
                    <details className="mt-2">
                      <summary className="text-[11px] text-gray-400 cursor-pointer select-none">Подробности</summary>
                      {e.detail && <pre className="mt-1 text-[10px] whitespace-pre-wrap break-all text-gray-500">{e.detail}</pre>}
                      {e.traceback && <pre className="mt-1 text-[10px] whitespace-pre-wrap break-all text-gray-400">{e.traceback}</pre>}
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'references' && (
          <div className="space-y-5 max-w-xl">
            <p className="text-sm text-gray-500 dark:text-gray-400">Загрузка справочников файлом (.xlsx или .csv). Дубликаты пропускаются.</p>
            {[
              { kind: 'dictionary', label: 'Словарь терминов', hint: 'Колонки: термин [, категория]' },
              { kind: 'brands', label: 'Бренды (whitelist)', hint: 'Колонка: название бренда' },
              { kind: 'checklist', label: 'Нормативный чек-лист', hint: 'Колонки: ключ, описание [, категория: all/bad/sport/grocery]' },
            ].map((r) => (
              <div key={r.kind} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{r.label}</p>
                <p className="text-xs text-gray-400 mb-2">{r.hint}</p>
                <input type="file" accept=".xlsx,.xlsm,.csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) importRef(r.kind, f); e.target.value = '' }}
                  className="text-xs text-gray-600 dark:text-gray-300 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-[#1F4E79] file:text-white file:text-xs" />
                {importMsg[r.kind] && <p className={`text-xs mt-2 ${importMsg[r.kind].startsWith('✓') ? 'text-green-500' : 'text-red-500'}`}>{importMsg[r.kind]}</p>}
              </div>
            ))}
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
            <div className="pt-2 border-t dark:border-gray-700">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                API-токен Selectel <span className="text-gray-400 font-normal">(только для показа баланса)</span>
              </label>
              <input value={extras.selectel_api_token || ''} onChange={(e) => setExtras({ ...extras, selectel_api_token: e.target.value })} type="password"
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm dark:bg-gray-700 dark:text-white" />
              <p className="text-xs text-gray-400 mt-1">
                Панель Selectel → Профиль и настройки → Ключи API. Загрузку файлов не затрагивает:
                для неё используются Access Key / Secret Key выше.
              </p>
            </div>
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
