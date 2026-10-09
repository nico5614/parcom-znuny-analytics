import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Brand } from '../components/Brand'
import { Icon } from '../components/Icon'
import type { DesktopApi, SavedCredentials, Session } from '../types/bridge'

export function Login({ api, version, onLogin, bridgeError, theme = 'light', onTheme }: { api?: DesktopApi; version?: string; onLogin: (session: Session) => void; bridgeError: string; theme?: 'light' | 'dark'; onTheme?: () => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saveCredentials, setSaveCredentials] = useState(false)
  const [saved, setSaved] = useState<SavedCredentials>({ supported: false, available: false, username: null })
  const usernameInput = useRef<HTMLInputElement>(null), passwordInput = useRef<HTMLInputElement>(null)
  useEffect(() => {
    let active = true
    if (api?.getSavedCredentials) void api.getSavedCredentials().then(value => {
      if (!active) return
      setSaved(value)
      if (value.username && usernameInput.current && !usernameInput.current.value) usernameInput.current.value = value.username
    }).catch(() => { if (active) setSaved({ supported: false, available: false, username: null }) })
    return () => { active = false }
  }, [api])
  async function savedAction(remove = false) {
    if (!api || busy) return
    setBusy(true); setError('')
    if (passwordInput.current) passwordInput.current.value = ''
    try {
      if (remove) {
        const reply = await api.removeSavedCredentials!()
        if (reply.ok) { setSaved({ supported: true, available: false, username: null }); setSaveCredentials(false) }
        else setError(reply.error.message)
      } else {
        const reply = await api.loginSaved!()
        if (reply.ok) onLogin(reply.data)
        else setError(reply.error.message)
      }
    } catch { setError('Der Windows-Schlüsselspeicher ist nicht verfügbar.') }
    finally { setBusy(false) }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!api || busy) return
    const form = event.currentTarget
    const username = form.elements.namedItem('username') as HTMLInputElement
    const password = form.elements.namedItem('password') as HTMLInputElement
    if (!username.value.trim() || !password.value) { setError('Bitte Benutzername und Passwort eingeben.'); return }
    setBusy(true); setError('')
    try {
      const request = saveCredentials ? api.login(username.value.trim(), password.value, true) : api.login(username.value.trim(), password.value)
      password.value = ''
      const response = await request
      if (response.ok) onLogin(response.data)
      else { setError(response.error.message); password.focus() }
    } catch {
      setError('Die Desktop-Verbindung wurde unterbrochen. Bitte erneut versuchen.')
    } finally { password.value = ''; setBusy(false) }
  }
  return <main className="login-layout">
    <section className="login-main">
      <div className="login-topbar"><Brand /><button className="icon-button" type="button" aria-label="Helles oder dunkles Design" aria-pressed={theme === 'dark'} onClick={onTheme}><Icon name="sun" size={18} /></button></div>
      <div className="login-form-wrap">
        <span className="section-kicker">SERVICE DESK ANALYTICS</span>
        <h1>Willkommen zurück.</h1>
        <p className="muted login-intro">Melden Sie sich mit Ihrem persönlichen<br className="desktop-break" /> Znuny-Konto an.</p>
        <form onSubmit={submit} noValidate aria-label="Znuny-Anmeldung">
          <label htmlFor="username">Benutzername</label>
          <input ref={usernameInput} id="username" name="username" autoComplete="off" spellCheck={false} autoCapitalize="none" autoFocus disabled={busy} placeholder="Ihr Znuny-Benutzername" />
          <label htmlFor="password">Passwort</label>
          <input ref={passwordInput} id="password" name="password" type="password" autoComplete="off" disabled={busy} placeholder="Ihr Passwort" aria-describedby={error ? 'login-error' : undefined} />
          <label className="credential-option"><input type="checkbox" checked={saveCredentials} disabled={busy || !saved.supported} onChange={event => setSaveCredentials(event.target.checked)} />Zugangsdaten speichern</label>
          <p className="credential-help">{saved.supported ? 'Optional im geschützten Windows-Schlüsselspeicher.' : 'Der Windows-Schlüsselspeicher ist nicht verfügbar.'}</p>
          {(error || bridgeError) && <div id="login-error" className="error-message" role="alert">{error || bridgeError}</div>}
          <button type="submit" className="primary login-submit" disabled={!api || busy}>{busy ? <><span className="spinner" />Anmeldung läuft …</> : <>Anmelden<Icon name="arrow" size={18} /></>}</button>
        </form>
        {saved.available && <div className="saved-credential-actions"><button className="secondary" disabled={busy} onClick={() => void savedAction()}>Gespeicherte Anmeldung verwenden</button><button className="identity-reset" disabled={busy} onClick={() => void savedAction(true)}>Gespeicherte Zugangsdaten entfernen</button></div>}
        <p className="login-security"><Icon name="shield" size={16} />{saveCredentials ? 'Speichern nur mit Ihrer Zustimmung in Windows.' : 'Ohne Zustimmung wird Ihr Passwort nicht gespeichert.'}</p>
        {api && <button className="offline-link" disabled={busy} onClick={async () => { setBusy(true); try { const reply = await api.continueOffline(); if (reply.ok) onLogin(reply.data); else setError(reply.error.message) } catch { setError('Die Desktop-Verbindung wurde unterbrochen.') } finally { setBusy(false) } }}>Lokalen Datenstand öffnen</button>}
      </div>
      <footer>ParCom Systems AG <span>Analytics {version || '…'}</span></footer>
    </section>
    <aside className="login-art" aria-label="ParCom Analytics">
      <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
      <div className="login-story">
        <span className="story-badge"><span className="status-dot" />ZNUNY · PBX & PBX INTERN</span>
        <h2>Ihr Service Desk.<br /><span>Alles im Blick.</span></h2>
        <p>Tickets verstehen. Entwicklungen erkennen.<br />Mit einem klaren Blick auf das Wesentliche.</p>
        <div className="story-features"><span><Icon name="analysis" />Fundierte Analysen</span><span><Icon name="agents" />Einblick ins Team</span><span><Icon name="shield" />Lokal & vertraulich</span></div>
      </div>
      <span className="art-footer">KLARE DATEN. GUTE ENTSCHEIDUNGEN.</span>
    </aside>
  </main>
}
