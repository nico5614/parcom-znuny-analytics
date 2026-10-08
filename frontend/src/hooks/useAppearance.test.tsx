import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useAppearance } from './useAppearance'
import type { DesktopApi, Preferences } from '../types/bridge'

describe('shared login/dashboard appearance', () => {
  it('gives system reduced motion priority over an enabled local preference', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const view = renderHook(() => useAppearance())
    expect(view.result.current.animationsEnabled).toBe(false)
    expect(document.documentElement.dataset.reducedMotion).toBe('true')
    act(() => view.result.current.changeMotion(false))
    expect(view.result.current.animationsEnabled).toBe(false)
    view.unmount(); vi.unstubAllGlobals()
  })
  it('defaults to light with animations enabled', () => {
    const { result } = renderHook(() => useAppearance())
    expect(result.current.theme).toBe('light')
    expect(result.current.reducedMotion).toBe(false)
    expect(document.documentElement.dataset.theme).toBe('light')
  })
  it('respects saved dark mode and persists changes across remounts', async () => {
    let saved: Preferences = { theme: 'dark', reducedMotion: true }
    const api = { getPreferences: vi.fn(async () => saved), setPreferences: vi.fn(async (theme, reducedMotion) => { saved = { theme, reducedMotion }; return { ok: true, data: null } }) } as unknown as DesktopApi
    const first = renderHook(() => useAppearance(api))
    await waitFor(() => expect(first.result.current.theme).toBe('dark'))
    act(() => first.result.current.changeTheme())
    await waitFor(() => expect(api.setPreferences).toHaveBeenCalledWith('light', true))
    first.unmount()
    const second = renderHook(() => useAppearance(api))
    await waitFor(() => expect(second.result.current.reducedMotion).toBe(true))
    expect(second.result.current.theme).toBe('light')
  })
})
