import { useCallback, useEffect, useRef, useState } from 'react'
import type { AppInfo, DataState, DesktopApi, Period, Session } from '../types/bridge'
import { Brand } from '../components/Brand'
import { Icon, type IconName } from '../components/Icon'
import { Overview } from '../pages/Overview'
import { Timeline, selection } from '../components/Timeline'
import { TicketDialog } from '../components/TicketDialog'
import { clearResources } from '../hooks/useResource'

const pages: { id: string; label: string; icon: IconName }[] = [{ id: 'overview', label: 'Übersicht', icon: 'overview' }, { id: 'analysis', label: 'Analysen', icon: 'analysis' }, { id: 'agents', label: 'Agenten', icon: 'agents' }, { id: 'export', label: 'Export', icon: 'export' }, { id: 'info', label: 'Info', icon: 'info' }]
const initial: DataState = { connection: 'offline', busy: false, newData: false, revision: 0, capturedAt: null, hasCache: false, warning: '' }
export function Shell({ api, session, info, onLogout }: { api: DesktopApi; session: Session; info?: AppInfo; onLogout: () => void }) {
  const [page, setPage] = useState('overview')
  const [state, setState] = useState(initial)
  const [period, setPeriod] = useState<Period>()
  const [loadedLabel, setLoadedLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [reducedMotion, setReducedMotion] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [ticket, setTicket] = useState<string>()
  const active = useRef(true)
  const refreshing = useRef(false)
  const refresh = useCallback(async (chosen: Period) => {
    if (refreshing.current) return
    refreshing.current = true; setBusy(true); setError('')
    try {
      const reply = await api.refresh(selection(chosen))
      if (!active.current) return
      const actual = await api.getPeriod()
      if (!active.current) return
      if (reply.ok) { setState(reply.data); setPeriod({ ...actual, preset: chosen.preset }); setLoadedLabel(actual.label) }
      else { setError(reply.error.message); setState(await api.getState()); setPeriod(actual) }
    } catch { if (active.current) setError('Die Desktop-Verbindung wurde unterbrochen.') }
    finally { refreshing.current = false; if (active.current) setBusy(false) }
  }, [api])
  useEffect(() => {
    active.current = true
    Promise.all([api.getState(), api.getPeriod(), api.getPreferences()]).then(async ([current, cachedPeriod, prefs]) => {
      if (!active.current) return
      setState(current); setPeriod(cachedPeriod); setLoadedLabel(current.hasCache ? cachedPeriod.label : '')
      setTheme(prefs.theme); setReducedMotion(prefs.reducedMotion)
      if (current.connection === 'online') {
        const next = await api.resolvePeriod({ preset: '1W' })
        if (active.current && next.ok) { setPeriod(next.data); void refresh(next.data) }
      }
    }).catch(() => setError('Die Desktop-Verbindung wurde unterbrochen.'))
    const timer = setInterval(() => { void api.checkChanges().then(next => { if (active.current) setState(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next) }).catch(() => { if (active.current) setError('Die Verbindungsprüfung ist fehlgeschlagen.') }) }, 120000)
    return () => { active.current = false; clearInterval(timer) }
  }, [api, refresh])
  useEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.dataset.reducedMotion = String(reducedMotion) }, [theme, reducedMotion])
  async function changeTheme() { const next = theme === 'dark' ? 'light' : 'dark'; setTheme(next); const reply = await api.setPreferences(next, reducedMotion); if (!reply.ok) setError(reply.error.message) }
  async function logout() { clearResources(api); onLogout(); await api.logout() }
  const statusLabel = state.connection === 'online' ? 'Verbunden' : state.connection === 'cached' ? 'Lokaler Datenstand' : 'Offline'
  return <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <aside className="sidebar"><Brand /><div className="nav-kicker">ARBEITSBEREICH</div><nav aria-label="Hauptnavigation">{pages.map(item => <button key={item.id} aria-current={page === item.id ? 'page' : undefined} title={item.label} onClick={() => setPage(item.id)}><Icon name={item.icon} /><span>{item.label}</span>{page === item.id && <span className="nav-indicator" />}</button>)}</nav><div className="sidebar-bottom"><div className="sidebar-source"><span className="status-dot" />PBX · PBX Intern<small>Znuny Analytics {info?.version}</small></div><button className="nav-logout" onClick={() => void logout()} title="Logout"><Icon name="logout" /><span>Logout</span></button><button className="sidebar-collapse" aria-label="Sidebar ein- oder ausklappen" onClick={() => setCollapsed(!collapsed)}><Icon name="chevron" size={16} /></button></div></aside>
    <div className="main-shell"><header className="topbar"><div className="header-context"><button className="icon-button mobile-menu" aria-label="Navigation einblenden" onClick={() => setCollapsed(!collapsed)}><Icon name="menu" /></button><span>Service Desk</span><span className="context-separator">/</span><strong>{pages.find(item => item.id === page)?.label}</strong></div><div className="header-actions"><span className={`connection ${state.connection}`}><span />{statusLabel}</span><button className="icon-button" aria-label="Helles oder dunkles Design" onClick={() => void changeTheme()}><Icon name="sun" size={18} /></button><span className="header-divider" /><span className="user-avatar">{session.username.slice(0, 2).toUpperCase()}</span><span className="user-name">{session.username}</span></div></header>
      <main className="main-content"><div className="page-heading"><div><span className="section-kicker">PARCOM ANALYTICS</span><h1>{pages.find(item => item.id === page)?.label}</h1></div><div className="heading-actions">{state.connection !== 'online' && <button className="secondary" onClick={onLogout}>Neu verbinden</button>}{period && page !== 'info' && <button className="primary refresh-button" disabled={busy || state.connection !== 'online'} onClick={() => void refresh(period)}>{busy ? <span className="spinner" /> : <Icon name="refresh" size={16} />}{busy ? 'Wird aktualisiert …' : 'Aktualisieren'}</button>}</div></div>
        {state.newData && <div className="new-data-banner" role="status"><span>Neuer Datenstand verfügbar</span><button onClick={() => period && void refresh(period)} disabled={busy}>Jetzt aktualisieren <Icon name="arrow" size={16} /></button></div>}
        {error && <div className="error-message global-error" role="alert">{error}<button aria-label="Meldung schliessen" onClick={() => setError('')}><Icon name="close" size={16} /></button></div>}
        {state.warning && <p className="warning-note">{state.warning}</p>}
        {period && ['overview', 'analysis', 'agents'].includes(page) && <Timeline api={api} period={period} onChange={next => { setPeriod(next); if (state.connection === 'online') void refresh(next); else { setPeriod(period); setError('Offline: Der zuletzt geladene Zeitraum bleibt sichtbar. Bitte mit Znuny verbinden.') } }} />}
        <div className="data-caption"><span>{loadedLabel ? `Datenzeitraum: ${loadedLabel}` : 'Noch kein Datenstand geladen'}</span>{busy ? <span className="refresh-caption" role="status"><span className="spinner" />Znuny-Daten werden geladen …</span> : state.capturedAt && <span>Datenstand: {new Date(state.capturedAt).toLocaleString('de-CH', { timeZone: 'Europe/Zurich', dateStyle: 'short', timeStyle: 'short' })}</span>}</div>
        {page === 'overview' ? <Overview api={api} revision={state.revision} theme={theme} onTicket={setTicket} /> : <div className="empty-state"><h2>{pages.find(item => item.id === page)?.label}</h2><p>Die nächste Migrationsstufe wird verbunden.</p></div>}
      </main><footer className="app-footer"><span>ParCom Systems AG</span><span>Lokale Verarbeitung · Europe/Zurich</span></footer>
    </div>{ticket && <TicketDialog api={api} id={ticket} revision={state.revision} onClose={() => setTicket(undefined)} />}
  </div>
}
