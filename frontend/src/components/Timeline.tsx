import { useEffect, useRef, useState, type PointerEvent, type KeyboardEvent } from 'react'
import type { DesktopApi, Period, PeriodSelection } from '../types/bridge'

export function selection(period: Period): PeriodSelection { return period.preset ? { preset: period.preset } : { preset: null, start: period.start, end: period.end } }
export function Timeline({ api, period, onChange }: { api: DesktopApi; period: Period; onChange: (period: Period) => void }) {
  const [start, setStart] = useState(period.startInput)
  const [end, setEnd] = useState(period.endInput)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<string | null>(null)
  const track = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; key: string | null; moved: boolean } | null>(null)
  const request = useRef(0)
  useEffect(() => { setStart(period.startInput); setEnd(period.endInput); setDraft(null) }, [period])
  async function resolve(value: PeriodSelection) {
    const current = ++request.current
    try {
      const reply = await api.resolvePeriod(value)
      if (current !== request.current) return
      if (reply.ok) { setError(''); onChange(reply.data) }
      else setError(reply.error.message)
    } catch { if (current === request.current) setError('Der Zeitraum konnte nicht geprüft werden.') }
    setDraft(null)
  }
  function snap(clientX: number) {
    const bounds = track.current!.getBoundingClientRect()
    return period.presets[Math.min(5, Math.max(0, Math.round((clientX - bounds.left) / bounds.width * 6)))]
  }
  function down(event: PointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { x: event.clientX, key: period.preset, moved: false }
  }
  function move(event: PointerEvent<HTMLButtonElement>) {
    if (drag.current && Math.abs(event.clientX - drag.current.x) > 2) {
      drag.current.moved = true
      drag.current.key = snap(event.clientX)
      setDraft(drag.current.key)
    }
  }
  function up() {
    if (drag.current?.moved && drag.current.key) void resolve({ preset: drag.current.key })
    drag.current = null
  }
  function keyboard(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const index = period.presets.indexOf(period.preset || '1W')
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? 5 : Math.min(5, Math.max(0, index + (event.key === 'ArrowLeft' ? -1 : 1)))
    void resolve({ preset: period.presets[next] })
  }
  const key = draft || period.preset
  const custom = key === null
  const left = custom ? 0 : period.presets.indexOf(key!) / 6 * 100
  return <div className="timeline-panel">
    <div className="timeline-track-wrap"><div className="timeline-track" ref={track}>
      <div className="timeline-selected" style={{ left: `${left}%` }} />
      {[left, 100].map((position, i) => <button key={i} className="timeline-handle" style={{ left: `${position}%` }} role="slider" aria-label={i ? 'Zeitraum-Ende' : 'Zeitraum-Beginn'} aria-valuemin={0} aria-valuemax={5} aria-valuenow={custom ? 0 : period.presets.indexOf(key!)} aria-valuetext={custom ? period.label : key!} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={() => { drag.current = null; setDraft(null) }} onKeyDown={keyboard}><span /></button>)}
      <div className={`timeline-labels ${custom ? 'custom-labels' : ''}`}>{custom ? <><span>{period.startInput.replace('T', ' ')}</span><span>{period.endInput.replace('T', ' ')}</span></> : <>{period.presets.map((preset, i) => <button key={preset} className={key === preset ? 'selected' : ''} style={{ left: `${i / 6 * 100}%` }} onClick={() => void resolve({ preset })}>{preset}</button>)}<span className="now-label">Jetzt</span></>}</div>
    </div></div>
    <form className="custom-range" onSubmit={event => { event.preventDefault(); void resolve({ preset: null, start, end }) }}><label>Von<input type="datetime-local" value={start} onChange={event => setStart(event.target.value)} required /></label><label>Bis<input type="datetime-local" value={end} onChange={event => setEnd(event.target.value)} required /></label><button className="secondary" type="submit">Anwenden</button></form>
    {error && <p role="alert" className="timeline-error">{error}</p>}
  </div>
}
