import { useCallback, useEffect, useRef, useState } from 'react'
import type { DesktopApi } from '../types/bridge'
import { useResource } from '../hooks/useResource'
import { Icon } from './Icon'
export function TicketDialog({ api, id, revision, onClose }: { api: DesktopApi; id: string; revision: number; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState('')
  const [opening, setOpening] = useState(false)
  const load = useCallback(() => api.getTicketDetails(id), [api, id])
  const { value: data, loading, error: loadError } = useResource(api, `ticket:${id}`, load, revision)
  useEffect(() => { const current = dialog.current; current?.showModal(); return () => current?.close() }, [])
  return <dialog ref={dialog} className="ticket-dialog" onCancel={onClose}><div className="dialog-header"><div><span className="section-kicker">TICKETDETAILS</span><h2>{data ? `Ticket ${data.number}` : 'Ticket wird geladen …'}</h2></div><button className="icon-button" aria-label="Schliessen" onClick={onClose}><Icon name="close" /></button></div>{data && <><p className="ticket-title">{data.title}</p><dl className="ticket-fields">{data.fields.map(field => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl><div className="dialog-footer"><span className="metadata">Geladener Datenstand · Europe/Zurich</span><button className="primary" disabled={opening} onClick={async () => { setOpening(true); try { const reply = await api.openTicket(id); if (!reply.ok) setError(reply.error.message) } catch { setError('Das Ticket konnte nicht geöffnet werden.') } finally { setOpening(false) } }}>In Znuny öffnen ↗</button></div></>}{loading && <p role="status">Znuny-Daten werden geladen …</p>}{(error || loadError) && <p className="error-message" role="alert">{error || loadError}</p>}</dialog>
}
