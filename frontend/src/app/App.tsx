import { useEffect, useState } from 'react'
import { desktop } from '../bridge/client'
import type { AppInfo } from '../types/bridge'

export default function App() {
  const [info, setInfo] = useState<AppInfo>()
  const [message, setMessage] = useState('Desktop-Verbindung wird geprüft …')
  const [sequence, setSequence] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const receive = (event: WindowEventMap['parcom:desktop']) => {
      setSequence(event.detail.sequence)
      setMessage(event.detail.message)
    }
    window.addEventListener('parcom:desktop', receive)
    desktop().then(async api => {
      const result = await api.getAppInfo()
      if (active) { setInfo(result); await api.probe() }
    }).catch(error => { if (active) setError(error.message) })
    return () => { active = false; window.removeEventListener('parcom:desktop', receive) }
  }, [])
  useEffect(() => {
    // Acknowledge only after React committed the Python-triggered state update.
    if (sequence) void desktop().then(api => api.confirmProbe(sequence))
  }, [sequence])
  return <main className="min-h-screen grid place-items-center p-8">
    <section className="spike-card w-full max-w-xl p-10">
      <p className="eyebrow">PARCOM SYSTEMS AG</p>
      <h1 className="text-3xl font-semibold mt-3">ParCom Analytics</h1>
      <p className="muted mt-3">Desktop-Spike · Phase 0</p>
      <div role="status" className="my-8 flex items-center gap-3">
        <span className={sequence ? 'status-dot' : 'spinner'} />{error || message}
      </div>
      {info && <dl className="grid grid-cols-2 gap-4 text-sm">
        <dt>Python</dt><dd>{info.python}</dd><dt>Renderer</dt><dd>{info.renderer}</dd>
        <dt>Version</dt><dd>{info.version}</dd><dt>Build</dt><dd>{info.packaged ? 'Desktop EXE' : 'Quellcode'}</dd>
      </dl>}
      <button className="primary mt-8" onClick={() => void desktop().then(api => api.probe())}>Verbindung erneut prüfen</button>
    </section>
  </main>
}
