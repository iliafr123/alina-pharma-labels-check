/**
 * Why the "Запустить проверку" button is disabled.
 *
 * A disabled button with no explanation is the worst of both worlds: the user
 * cannot proceed and cannot tell what is missing. `blockers()` returns every
 * unmet precondition in the order the user would fix them; the button is disabled
 * exactly when that list is non-empty, so the two can never disagree.
 */

export type QualityReport = {
  ok: boolean
  level: 'excellent' | 'acceptable' | 'poor'
  score: number
  summary: string
  problems?: { code: string; message: string; hint?: string }[]
  advice?: string[]
  metrics?: Record<string, any>
}

export type PipelineOptions = {
  debug_mode?: boolean
  llm_providers?: string[]
  ocr_providers?: string[]
  pipeline_mode?: string
  active_llm?: string
  active_ocr?: string
  configured?: boolean
}

export type Blocker = { code: string; text: string; fix?: string }

export type CheckFormState = {
  productName: string
  mockupFile: File | null
  penFile: File | null
  quality: QualityReport | null
  qualityChecking: boolean
  qualityError: string
  options: PipelineOptions | null
  submitting: boolean
}

export function blockers(s: CheckFormState): Blocker[] {
  const out: Blocker[] = []

  if (!s.productName.trim()) {
    out.push({ code: 'NO_NAME', text: 'Не указано название продукта.' })
  }
  if (!s.mockupFile) {
    out.push({ code: 'NO_MOCKUP', text: 'Не загружен макет этикетки (PDF или JPG).' })
  }
  if (!s.penFile) {
    out.push({ code: 'NO_PEN', text: 'Не загружен эталон ПЭН (DOCX).' })
  }

  if (s.mockupFile && s.qualityChecking) {
    out.push({ code: 'QUALITY_PENDING', text: 'Идёт проверка качества макета — подождите пару секунд.' })
  }
  if (s.mockupFile && s.quality && !s.quality.ok) {
    const problem = s.quality.problems?.[0]
    out.push({
      code: 'QUALITY_TOO_LOW',
      text: problem?.message || 'Качество макета недостаточно для распознавания текста.',
      fix: s.quality.advice?.join('; ') || problem?.hint,
    })
  }

  // The options call itself failing must not silently block the user forever, so a
  // null `options` is only reported once it is known to be loaded and unconfigured.
  if (s.options && s.options.configured === false) {
    const missing: string[] = []
    if (!s.options.active_ocr) missing.push('OCR')
    if (!s.options.active_llm) missing.push('LLM')
    if (!(s.options.llm_providers || []).length) missing.push('ключи провайдеров')
    out.push({
      code: 'PIPELINE_NOT_CONFIGURED',
      text: `Пайплайн не настроен: не заданы ${missing.join(', ') || 'провайдеры'}.`,
      fix: 'Обратитесь к администратору — Администрирование → Провайдеры AI/OCR и Конфигурация пайплайна.',
    })
  }

  if (s.submitting) {
    out.push({ code: 'SUBMITTING', text: 'Идёт загрузка файлов и запуск проверки…' })
  }

  return out
}

export function canSubmit(s: CheckFormState): boolean {
  return blockers(s).length === 0
}

/** Colour/label for the quality badge. */
export function qualityTone(level: string): { label: string; cls: string } {
  switch (level) {
    case 'excellent':
      return { label: 'Качество отличное', cls: 'text-green-700 bg-green-50 border-green-300' }
    case 'acceptable':
      return { label: 'Качество приемлемое', cls: 'text-yellow-700 bg-yellow-50 border-yellow-300' }
    default:
      return { label: 'Качество недостаточное', cls: 'text-red-700 bg-red-50 border-red-300' }
  }
}

/** "≈ 1 392 ₽ (58 ILS)" - the rouble figure the operator actually reasons about. */
export function formatBalance(b: any): string {
  if (!b) return '—'
  if (b.units) {
    const parts = Object.entries(b.units)
      .filter(([, v]) => typeof v === 'number' && v > 0)
      .map(([k, v]) => `${v} ${k === 'pages' ? 'стр.' : k}`)
    return parts.length ? parts.join(', ') : '—'
  }
  if (b.amount === null || b.amount === undefined) return '—'
  const rub = b.amount_rub
  const own = `${Number(b.amount).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${b.currency || ''}`.trim()
  if (b.currency === 'RUB' || rub === null || rub === undefined) {
    return b.currency === 'RUB'
      ? `${Number(b.amount).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`
      : own
  }
  return `≈ ${Number(rub).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽ (${own})`
}
