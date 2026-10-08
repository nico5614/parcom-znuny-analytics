import { describe, expect, it } from 'vitest'
import { needsRangeConfirmation } from './Shell'
import type { Period } from '../types/bridge'
const base = { start: '2026-10-01T12:00:00+02:00', end: '2026-10-08T12:00:00+02:00' } as Period
describe('long range confirmation policy', () => {
  it.each(['1M', '3M', '6M', '1J'])('confirms the %s preset', preset => { expect(needsRangeConfirmation({ ...base, preset })).toBe(true) })
  it.each(['1T', '1W'])('does not warn for %s', preset => { expect(needsRangeConfirmation({ ...base, preset })).toBe(false) })
  it('does not warn at exactly seven days, but warns beyond seven days', () => {
    expect(needsRangeConfirmation({ ...base, preset: null })).toBe(false)
    expect(needsRangeConfirmation({ ...base, preset: null, start: '2026-09-30T12:00:00+02:00' })).toBe(true)
  })
})
