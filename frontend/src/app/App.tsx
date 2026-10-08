import { useEffect, useState } from 'react'
import { desktop } from '../bridge/client'
import { Login } from '../pages/Login'
import { Shell } from './Shell'
import { useAppearance } from '../hooks/useAppearance'
import { AnimationContext } from '../hooks/animations'
import type { AppInfo, DesktopApi, Session } from '../types/bridge'

export default function App() {
  const [info, setInfo] = useState<AppInfo>()
  const [api, setApi] = useState<DesktopApi>()
  const appearance = useAppearance(api)
  const [session, setSession] = useState<Session>()
  const [sequence, setSequence] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const receive = (event: WindowEventMap['parcom:desktop']) => {
      setSequence(event.detail.sequence)
    }
    window.addEventListener('parcom:desktop', receive)
    desktop().then(async bridge => {
      const result = await bridge.getAppInfo()
      if (active) { setApi(bridge); setInfo(result); await bridge.probe() }
    }).catch(error => { if (active) setError(error.message) })
    return () => { active = false; window.removeEventListener('parcom:desktop', receive) }
  }, [])
  useEffect(() => {
    // Acknowledge only after React committed the Python-triggered state update.
    if (sequence) void desktop().then(api => api.confirmProbe(sequence))
  }, [sequence])
  const content = !session || !api ? <Login api={api} version={info?.version} bridgeError={error || appearance.error} onLogin={setSession} theme={appearance.theme} onTheme={appearance.changeTheme} />
    : <Shell api={api} session={session} info={info} onLogout={() => setSession(undefined)} appearance={appearance} />
  return <AnimationContext.Provider value={appearance.animationsEnabled}>{content}</AnimationContext.Provider>
}
