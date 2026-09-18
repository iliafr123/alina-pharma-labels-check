import { describe, it, expect } from 'vitest'
import { blockers, canSubmit, qualityTone, formatBalance, type CheckFormState } from './checkGuards'

const READY: CheckFormState = {
  productName: 'Витамин D3',
  mockupFile: { name: 'label.pdf' } as File,
  penFile: { name: 'pen.docx' } as File,
  quality: { ok: true, level: 'excellent', score: 98, summary: 'ок' },
  qualityChecking: false,
  qualityError: '',
  options: { configured: true, active_llm: 'gemini', active_ocr: 'gemini', llm_providers: ['gemini'] },
  submitting: false,
}

describe('blockers', () => {
  it('allows submitting when everything is in place', () => {
    expect(blockers(READY)).toEqual([])
    expect(canSubmit(READY)).toBe(true)
  })

  it('names a missing product name', () => {
    const b = blockers({ ...READY, productName: '   ' })
    expect(b.map((x) => x.code)).toContain('NO_NAME')
    expect(b[0].text).toMatch(/название/i)
  })

  it('names a missing mockup', () => {
    expect(blockers({ ...READY, mockupFile: null }).map((x) => x.code)).toContain('NO_MOCKUP')
  })

  it('names a missing ПЭН', () => {
    expect(blockers({ ...READY, penFile: null }).map((x) => x.code)).toContain('NO_PEN')
  })

  it('reports every missing item at once, not just the first', () => {
    const b = blockers({ ...READY, productName: '', mockupFile: null, penFile: null })
    expect(b.map((x) => x.code)).toEqual(['NO_NAME', 'NO_MOCKUP', 'NO_PEN'])
  })

  it('blocks while the quality check is still running', () => {
    const b = blockers({ ...READY, qualityChecking: true, quality: null })
    expect(b.map((x) => x.code)).toContain('QUALITY_PENDING')
  })

  it('blocks on a poor-quality mockup and repeats the reason from the server', () => {
    const b = blockers({
      ...READY,
      quality: {
        ok: false, level: 'poor', score: 30, summary: 'плохо',
        problems: [{ code: 'LOW_RESOLUTION', message: 'Низкое разрешение макета: 4 пикс/мм' }],
        advice: ['пришлите исходный PDF'],
      },
    })
    const q = b.find((x) => x.code === 'QUALITY_TOO_LOW')!
    expect(q.text).toMatch(/Низкое разрешение/)
    expect(q.fix).toMatch(/исходный PDF/)
  })

  it('does not block on merely acceptable quality', () => {
    const b = blockers({
      ...READY,
      quality: { ok: true, level: 'acceptable', score: 70, summary: 'сойдёт' },
    })
    expect(b).toEqual([])
  })

  it('blocks when the pipeline has no providers configured', () => {
    const b = blockers({
      ...READY,
      options: { configured: false, active_llm: '', active_ocr: '', llm_providers: [] },
    })
    const p = b.find((x) => x.code === 'PIPELINE_NOT_CONFIGURED')!
    expect(p.text).toMatch(/OCR/)
    expect(p.text).toMatch(/LLM/)
    expect(p.fix).toMatch(/Администрирование/)
  })

  it('does not block while the options call has not answered yet', () => {
    expect(blockers({ ...READY, options: null })).toEqual([])
  })

  it('blocks while submitting', () => {
    expect(blockers({ ...READY, submitting: true }).map((x) => x.code)).toContain('SUBMITTING')
  })

  it('never returns an empty explanation', () => {
    const states: CheckFormState[] = [
      { ...READY, productName: '' },
      { ...READY, mockupFile: null },
      { ...READY, qualityChecking: true },
      { ...READY, submitting: true },
      { ...READY, quality: { ok: false, level: 'poor', score: 1, summary: '' } },
    ]
    for (const s of states) {
      for (const b of blockers(s)) expect(b.text.length).toBeGreaterThan(5)
    }
  })
})

describe('qualityTone', () => {
  it('has a distinct look per level', () => {
    const levels = ['excellent', 'acceptable', 'poor'].map(qualityTone)
    expect(new Set(levels.map((l) => l.cls)).size).toBe(3)
    for (const l of levels) expect(l.label).toBeTruthy()
  })
})

describe('formatBalance', () => {
  // toLocaleString('ru-RU') groups digits with a non-breaking space (U+00A0),
  // so compare against normalised text rather than a plain space.
  const plain = (s: string) => s.replace(/[  ]/g, ' ')

  it('shows roubles directly', () => {
    expect(plain(formatBalance({ amount: 1500, currency: 'RUB', amount_rub: 1500 }))).toContain('1 500')
  })

  it('converts a foreign currency and keeps the original alongside', () => {
    const out = plain(formatBalance({ amount: 58, currency: 'ILS', amount_rub: 1392 }))
    expect(out).toContain('1 392')
    expect(out).toContain('58 ILS')
  })

  it('renders a page quota rather than money', () => {
    expect(formatBalance({ units: { pages: 1500, fields: 0 } })).toBe('1500 стр.')
  })

  it('handles the no-data case', () => {
    expect(formatBalance(null)).toBe('—')
    expect(formatBalance({ amount: null })).toBe('—')
  })
})
