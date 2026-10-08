import { useEffect, useState } from 'react'
import { desktop } from '../bridge/client'
import { Login } from '../pages/Login'
import { Brand } from '../components/Brand'
import type { AppInfo, DesktopApi, Session } from '../types/bridge'

export default function App() {
  const [info, setInfo] = useState<AppInfo>()
  const [api, setApi] = useState<DesktopApi>()
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
  if (!session || !api) return <Login api={api} version={info?.version} bridgeError={error} onLogin={setSession} />
  return <main className="p-8"><Brand /><h1 className="mt-10 text-3xl">Übersicht</h1><p className="muted mt-3">Angemeldet als {session.username}</p><p className="muted mt-8">Noch kein Datenstand geladen.</p><button className="primary mt-8" onClick={async () => { await api.logout(); setSession(undefined) }}>Logout</button></main>
}
