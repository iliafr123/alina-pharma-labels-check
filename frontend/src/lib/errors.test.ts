import { describe, it, expect } from 'vitest'
import { apiError, errorTitle, errorHint, errorMessage } from './errors'

const structured = {
  response: {
    data: {
      detail: 'Selectel: доступ приостановлен - оплатите счёт',
      error: {
        code: 'STORAGE_PAYMENT_REQUIRED',
        title: 'Selectel: доступ приостановлен.',
        hint: 'Оплатите счёт в панели Selectel.',
        provider: 'selectel',
        subsystem: 'storage',
      },
    },
  },
}

describe('structured errors', () => {
  it('extracts the typed error', () => {
    expect(apiError(structured)?.code).toBe('STORAGE_PAYMENT_REQUIRED')
  })

  it('shows the cause and the fix separately', () => {
    expect(errorTitle(structured)).toBe('Selectel: доступ приостановлен.')
    expect(errorHint(structured)).toBe('Оплатите счёт в панели Selectel.')
  })

  it('combines them for single-line places', () => {
    const msg = errorMessage(structured)
    expect(msg).toContain('приостановлен')
    expect(msg).toContain('Оплатите')
  })
})

describe('legacy and edge cases', () => {
  it('falls back to a plain string detail', () => {
    const e = { response: { data: { detail: 'Проверка не найдена' } } }
    expect(errorTitle(e)).toBe('Проверка не найдена')
    expect(errorHint(e)).toBe('')
  })

  it('renders FastAPI validation errors instead of [object Object]', () => {
    const e = {
      response: { data: { detail: [{ loc: ['body', 'x'], msg: 'field required', type: 'missing' }] } },
    }
    expect(errorTitle(e)).toBe('field required')
  })

  it('explains a network failure', () => {
    expect(errorTitle({ message: 'Network Error' })).toMatch(/нет связи/i)
    expect(errorHint({ message: 'Network Error' })).toBeTruthy()
  })

  it('never returns an empty string', () => {
    for (const e of [null, undefined, {}, { response: {} }, { response: { data: {} } }]) {
      expect(errorTitle(e).length).toBeGreaterThan(0)
      expect(errorMessage(e).length).toBeGreaterThan(0)
    }
  })

  it('uses the supplied fallback when the server said nothing', () => {
    expect(errorTitle({}, 'Не удалось загрузить журнал')).toBe('Не удалось загрузить журнал')
  })

  it('returns null for a response with no typed error', () => {
    expect(apiError({ response: { data: { detail: 'x' } } })).toBeNull()
  })
})
