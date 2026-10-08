import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import type { DesktopApi, Result } from '../types/bridge'
import { clearResources, useResource } from './useResource'

describe('cached page resources', () => {
  it('reuses a page immediately and keeps the rendered data during a new revision', async () => {
    const api = {} as DesktopApi
    let finish!: (result: Result<number>) => void
    const load = vi.fn().mockResolvedValueOnce({ ok: true, data: 0 }).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const first = renderHook(({ revision }) => useResource(api, 'overview', load, revision), { initialProps: { revision: 0 } })
    await waitFor(() => expect(first.result.current.value).toBe(0))
    first.unmount()
    const next = renderHook(({ revision }) => useResource(api, 'overview', load, revision), { initialProps: { revision: 0 } })
    expect(next.result.current.value).toBe(0)
    expect(load).toHaveBeenCalledTimes(1)
    next.rerender({ revision: 1 })
    expect(next.result.current.value).toBe(0)
    expect(next.result.current.loading).toBe(true)
    await act(async () => finish({ ok: true, data: 5 }))
    expect(next.result.current.value).toBe(5)
    clearResources(api)
    next.unmount()
    const pending = () => new Promise<Result<number>>(() => {})
    const loggedOut = renderHook(() => useResource(api, 'overview', pending, 1))
    expect(loggedOut.result.current.value).toBeUndefined()
  })
  it('discards an older completion when the selected analysis changes', async () => {
    const api = {} as DesktopApi
    let finish!: (result: Result<string>) => void
    const pending = () => new Promise<Result<string>>(resolve => { finish = resolve })
    const loaded = vi.fn().mockResolvedValue({ ok: true, data: 'selected' })
    const result = renderHook(({ key, load }) => useResource(api, key, load, 0), { initialProps: { key: 'first', load: pending } })
    result.rerender({ key: 'second', load: loaded })
    await waitFor(() => expect(result.result.current.value).toBe('selected'))
    await act(async () => finish({ ok: true, data: 'older' }))
    expect(result.result.current.value).toBe('selected')
  })
})
