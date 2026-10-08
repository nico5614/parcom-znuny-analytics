import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { DesktopApi, Preferences } from '../types/bridge'

const defaults: Preferences = { theme: 'light', reducedMotion: false }
export function useAppearance(api?: DesktopApi) {
  const [preferences, setPreferences] = useState(defaults)
  const [error, setError] = useState('')
  const latest = useRef(defaults)
  const writes = useRef(Promise.resolve())
  useEffect(() => {
    let active = true
    if (api) void api.getPreferences().then(value => {
      if (active) { latest.current = value; setPreferences(value) }
    }).catch(() => { if (active) setError('Die Darstellungseinstellung konnte nicht geladen werden.') })
    return () => { active = false }
  }, [api])
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = preferences.theme
    document.documentElement.dataset.reducedMotion = String(preferences.reducedMotion)
  }, [preferences])
  function update(next: Preferences) {
    latest.current = next; setPreferences(next)
    if (api) writes.current = writes.current.then(async () => {
      const reply = await api.setPreferences(next.theme, next.reducedMotion)
      if (!reply.ok) setError(reply.error.message)
    }).catch(() => setError('Die Darstellungseinstellung konnte nicht gespeichert werden.'))
  }
  return { ...preferences, error,
    changeTheme: () => update({ ...latest.current, theme: latest.current.theme === 'light' ? 'dark' : 'light' }),
    changeMotion: (reducedMotion: boolean) => update({ ...latest.current, reducedMotion }) }
}
