import { describe, it, expect, vi, afterEach } from 'vitest'
import { desktop } from './client'
import type { DesktopApi } from '../types/bridge'

afterEach(() => { delete window.pywebview; vi.useRealTimers() })
describe('desktop readiness', () => {
  it('resolves an already available API', async () => {
    const api = {} as DesktopApi
    window.pywebview = { api }
    expect(await desktop()).toBe(api)
  })
  it('waits for the actual pywebviewready event', async () => {
    const result = desktop()
    const api = {} as DesktopApi
    window.pywebview = { api }
    window.dispatchEvent(new Event('pywebviewready'))
    expect(await result).toBe(api)
  })
  it('reports a missing desktop instead of leaving an endless spinner', async () => {
    vi.useFakeTimers()
    const result = expect(desktop()).rejects.toThrow('Desktop-Anwendung')
    await vi.advanceTimersByTimeAsync(12000)
    await result
  })
})
