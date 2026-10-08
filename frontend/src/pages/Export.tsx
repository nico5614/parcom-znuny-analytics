import { useEffect, useState } from 'react'
import type { DesktopApi } from '../types/bridge'
import { Card } from '../components/Card'
import { Icon } from '../components/Icon'

export function Export({ api, hasCache, busyChanged }: { api: DesktopApi; hasCache: boolean; busyChanged: (busy: boolean) => void }) {
  const [options, setOptions] = useState<{ id: string; label: string; types: string[] }[]>([])
  const [target, setTarget] = useState('overview')
  const [type, setType] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { let active = true; api.getExportOptions().then(result => { if (active) setOptions(result) }).catch(() => { if (active) setError('Die Exportauswahl konnte nicht geladen werden.') }); return () => { active = false } }, [api])
  async function save() {
    setBusy(true); busyChanged(true); setMessage(''); setError('')
    try { const reply = await api.exportPdf(target, target === 'overview' ? null : type); if (reply.ok) setMessage(reply.data.cancelled ? 'Export abgebrochen.' : `PDF gespeichert: ${reply.data.filename}`); else setError(reply.error.message) }
    catch { setError('Die Desktop-Verbindung wurde unterbrochen.') }
    finally { setBusy(false); busyChanged(false) }
  }
  return <div className="export-grid"><Card title="Auswertung als PDF" className="export-card"><div className="export-symbol"><Icon name="export" size={32} /></div><h2>Ein klarer Bericht.<br />Bereit zum Weitergeben.</h2><p>Übersicht oder einzelne Analyse mit Kennzahlen, Verlauf, Vergleich und Ticketdetails als PDF speichern.</p><label className="export-select">Auswertung<select aria-label="Auswertung" value={target} disabled={busy} onChange={event => setTarget(event.target.value)}><option value="overview">Service Desk – Gesamtübersicht</option>{options.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>{target !== 'overview' && <label className="export-select">Tickettyp<select aria-label="Tickettyp im Export" value={type || ''} disabled={busy} onChange={event => setType(event.target.value || null)}><option value="">Alle Tickettypen</option>{options.find(item => item.id === target)?.types.map(value => <option key={value}>{value}</option>)}</select></label>}<button className="primary export-submit" disabled={busy || !hasCache} onClick={() => void save()}>{busy ? <><span className="spinner" />PDF wird erstellt …</> : <><Icon name="export" size={16} />Als PDF speichern</>}</button>{message && <p className="export-success" role="status">{message}</p>}{error && <p className="error-message" role="alert">{error}</p>}{!hasCache && <p className="chart-note">Zuerst einen Datenstand laden.</p>}</Card><Card title="Im Bericht enthalten" className="export-notes"><ul><li><strong>Vorhandener Datenstand</strong><p>Der Export verwendet den zuletzt vollständig geladenen Zeitraum. Während der Erstellung bleibt die Navigation verfügbar.</p></li><li><strong>Transparente Kennzahlen</strong><p>Fehlende Vergleiche und nicht verfügbare Scores werden mit ihrer Datengrundlage ausgewiesen.</p></li><li><strong>Ticketdetails</strong><p>Breite Tabellen werden im PDF auf mehrere Spaltengruppen verteilt.</p></li></ul><p className="privacy-note"><Icon name="shield" size={17} />Berichte enthalten Ticketdaten. Teilen Sie sie nur mit vorgesehenen Empfängern.</p></Card></div>
}
