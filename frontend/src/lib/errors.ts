/**
 * Rendering for the structured errors the API now returns.
 *
 * The backend answers failures with `{ detail, error: { code, title, hint, ... } }`.
 * Older responses (and FastAPI's own validation errors) only have `detail`, so every
 * helper here degrades to that rather than showing "Произошла ошибка".
 */

export type ApiError = {
  code: string
  title: string
  hint?: string
  detail?: string
  provider?: string
  subsystem?: string
  stage?: string
  context?: Record<string, any>
}

/** Pull the structured error out of an axios failure, if the server sent one. */
export function apiError(e: any): ApiError | null {
  const data = e?.response?.data
  if (data?.error?.code) return data.error as ApiError
  return null
}

/** Short line: what went wrong. Always returns something printable. */
export function errorTitle(e: any, fallback = 'Произошла ошибка'): string {
  const err = apiError(e)
  if (err) return err.title
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  // FastAPI validation errors arrive as a list of {loc, msg, type}.
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: any) => d?.msg).filter(Boolean).join('; ') || fallback
  }
  if (e?.message === 'Network Error') return 'Нет связи с сервером.'
  return e?.message || fallback
}

/** What the operator should do about it. Empty string when the server offered nothing. */
export function errorHint(e: any): string {
  const err = apiError(e)
  if (err?.hint) return err.hint
  if (e?.message === 'Network Error') {
    return 'Сервер недоступен или прерван интернет. Проверьте соединение и повторите.'
  }
  return ''
}

/** One string for places with a single line of room (alert, toast). */
export function errorMessage(e: any, fallback = 'Произошла ошибка'): string {
  const title = errorTitle(e, fallback)
  const hint = errorHint(e)
  return hint ? `${title} ${hint}` : title
}

export const SUBSYSTEM_LABELS: Record<string, string> = {
  storage: 'Хранилище',
  llm: 'LLM',
  ocr: 'OCR',
  file: 'Файл',
  pipeline: 'Пайплайн',
  app: 'Приложение',
}

export const STAGE_LABELS: Record<string, string> = {
  init: 'инициализация',
  storage: 'загрузка файлов из хранилища',
  quality: 'проверка качества макета',
  config: 'конфигурация пайплайна',
  ocr: 'распознавание текста',
  pen_parse: 'разбор ПЭН',
  spelling: 'орфография',
  pen: 'сверка с ПЭН',
  regulatory: 'нормативный чек-лист',
  checklist: 'чек-лист обязательных элементов',
  report: 'формирование отчёта',
}
