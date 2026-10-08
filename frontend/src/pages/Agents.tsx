import { useCallback, useEffect, useRef, useState } from 'react'
import type { Agents as AgentsDto, DataState, DesktopApi } from '../types/bridge'
import { useResource } from '../hooks/useResource'
import { Card, Empty, MetricCard, Skeleton } from '../components/Card'
import { Chart } from '../charts/Chart'
import { DataTable } from '../components/DataTable'
import { Icon } from '../components/Icon'

function TeamDialog({ api, data, onClose, onSave }: { api: DesktopApi; data: AgentsDto; onClose: () => void; onSave: (state: DataState) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [selected, setSelected] = useState(new Set(data.selected))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { const current = dialog.current!; current.showModal(); return () => current.close() }, [])
  async function save() { setBusy(true); try { const reply = await api.setTeam([...selected]); if (reply.ok) { onSave(reply.data); onClose() } else setError(reply.error.message) } catch { setError('Die Teamauswahl konnte nicht gespeichert werden.') } finally { setBusy(false) } }
  return <dialog className="ticket-dialog team-dialog" ref={dialog} onCancel={onClose}><div className="dialog-header"><h2>Team verwalten</h2><button className="icon-button" onClick={onClose} aria-label="Schliessen"><Icon name="close" /></button></div><p className="chart-note">Techniker für die Teamauswertung auswählen. Neue IDs bleiben zunächst abgewählt.</p><div className="team-list">{data.registry.map(item => <label key={item.id}><input type="checkbox" checked={selected.has(item.id)} onChange={event => setSelected(previous => { const next = new Set(previous); if (event.target.checked) next.add(item.id); else next.delete(item.id); return next })} /><span>{item.name}<small>{item.code.startsWith('ID ') ? `${item.login || item.code} · Kürzel nicht zugeordnet` : `${item.code} · ${item.login}`}</small></span></label>)}</div>{error && <p role="alert" className="error-message">{error}</p>}<footer className="dialog-footer"><button className="secondary" onClick={onClose}>Abbrechen</button><button className="primary" disabled={busy} onClick={() => void save()}>{busy ? 'Wird gespeichert …' : 'Speichern'}</button></footer></dialog>
}
export function Agents({ api, revision, theme, onTicket, onState }: { api: DesktopApi; revision: number; theme: string; onTicket: (id: string) => void; onState: (state: DataState) => void }) {
  const [agent, setAgent] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [manage, setManage] = useState(false)
  const load = useCallback(() => api.getAgents(agent, page), [api, agent, page])
  const { value: data, loading, error } = useResource(api, `agents:${agent}:${page}`, load, revision)
  if (!data) return loading ? <Skeleton /> : <Empty message={error || undefined} />
  return <div className="agents-page"><div className="agents-toolbar"><p>{data.note}</p><label className="inline-select">Techniker<select aria-label="Techniker" value={agent || ''} onChange={event => { setAgent(event.target.value || null); setPage(0) }}><option value="">Gesamtes Team</option>{data.registry.filter(item => data.selected.includes(item.id)).map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><button className="secondary" onClick={() => setManage(true)}><Icon name="agents" size={16} />Team verwalten</button></div>
    <div className="kpi-row">{data.metrics.map(metric => <MetricCard key={metric.label} metric={metric} />)}</div><div className="agents-grid"><Card title="Geschlossene Tickets nach Techniker" className="agents-chart"><Chart dto={data.chart} theme={theme} height={240} /><p className="chart-note">{data.rankingNote}</p></Card><Card title="Team im Zeitraum" className="agents-ranking" aside={<span className="metadata">Informelles Ranking</span>}><ol>{data.rows.filter(row => (row.Geschlossen ?? 0) > 0).slice(0, 5).map(row => <li key={row.id}><span className="agent-avatar">{row.label.slice(0, 3)}</span><span>{row.label}<small>{row.Erstantworten} Erstantworten</small></span><strong>{row.Geschlossen}<small>Abschlüsse</small></strong></li>)}</ol>{!data.rows.some(row => (row.Geschlossen ?? 0) > 0) && <p className="chart-note">{data.historyLoaded ? 'Keine Abschlüsse in der Auswahl.' : 'Historie noch nicht verfügbar.'}</p>}<p className="ranking-explanation">Abschlüsse und Erstantworten stammen aus der Ticket-Historie. Das Ranking beschreibt Aktivität; es bewertet keine Arbeitsqualität.</p></Card>
      <Card title="Aktivität und aktueller Besitz" className="agents-details"><DataTable dto={data.table} onTicket={onTicket} onPage={setPage} /></Card></div>
    {manage && <TeamDialog api={api} data={data} onClose={() => setManage(false)} onSave={next => { setAgent(null); setPage(0); onState(next) }} />}
  </div>
}
