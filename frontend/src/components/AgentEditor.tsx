import { useState } from 'react'
import type { AgentIdentity, DesktopApi } from '../types/bridge'

export function AgentEditor({ api, identity, onChange }: { api: DesktopApi; identity: AgentIdentity; onChange: (identity: AgentIdentity) => void }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(identity.name), [code, setCode] = useState(identity.code)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const supported = Boolean(api.setAgentDisplayName && api.setAgentAbbreviation && api.resetAgentOverride)
  async function save(reset = false) {
    setBusy(true); setError('')
    try {
      if (reset) {
        const reply = await api.resetAgentOverride!(identity.id)
        if (!reply.ok) { setError(reply.error.message); return }
        onChange(reply.data); setName(reply.data.name); setCode(reply.data.code)
      } else {
        const named = await api.setAgentDisplayName!(identity.id, name.trim())
        if (!named.ok) { setError(named.error.message); return }
        onChange(named.data)
        const coded = await api.setAgentAbbreviation!(identity.id, code.trim())
        if (!coded.ok) { setError(coded.error.message); return }
        onChange(coded.data)
      }
      setEditing(false)
    } catch { setError('Die lokale Änderung konnte nicht gespeichert werden.') }
    finally { setBusy(false) }
  }
  return <div className="agent-editor">{editing ? <><div className="identity-fields"><label>Anzeigename<input value={name} onChange={event => setName(event.target.value)} /></label><label>Kürzel<input value={code} onChange={event => setCode(event.target.value)} /></label></div><div className="identity-actions"><button className="secondary" disabled={busy || !name.trim() || !code.trim()} onClick={() => void save()}>Änderung speichern</button><button className="secondary" disabled={busy} onClick={() => setEditing(false)}>Abbrechen</button></div></> : <button className="identity-edit" disabled={!supported || busy} title={supported ? 'Namen und Kürzel lokal bearbeiten' : 'Backend-Unterstützung für lokale Änderungen fehlt'} onClick={() => { setName(identity.name); setCode(identity.code); setEditing(true) }}>Bearbeiten</button>}<button className="identity-reset" disabled={!supported || busy} onClick={() => void save(true)}>Zurücksetzen auf automatisch</button>{error && <p className="error-message" role="alert">{error}</p>}</div>
}
