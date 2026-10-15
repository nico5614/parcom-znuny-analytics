import { useEffect, useRef, useState } from 'react'

const iso = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const parse = (value: string) => new Date(`${value.slice(0, 10)}T12:00:00`)
export function DateRangeDialog({ start, end, onConfirm, onClose }: { start: string; end: string; onConfirm: (start: string, end: string) => void; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [month, setMonth] = useState(parse(end))
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Zurich' }).format(new Date())
  const minimum = parse(today); minimum.setFullYear(minimum.getFullYear() - 1)
  useEffect(() => { const node = dialog.current!; node.showModal(); return () => node.close() }, [])
  const offset = (new Date(month.getFullYear(), month.getMonth(), 1).getDay() + 6) % 7
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  function choose(value: string) {
    if (!first || last) { setFirst(value); setLast('') }
    else if (value < first) { setLast(first); setFirst(value) }
    else setLast(value)
  }
  return <dialog ref={dialog} className="ticket-dialog date-range-dialog" aria-labelledby="date-range-title" onCancel={onClose}>
    <div className="dialog-header"><h2 id="date-range-title">Eigenes Datum auswählen</h2><button className="secondary" onClick={onClose}>Abbrechen</button></div>
    <p className="metadata">Aktuell: {start.slice(0, 10)} – {end.slice(0, 10)}</p>
    <div className="calendar-heading"><button className="secondary" aria-label="Vorheriger Monat" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>‹</button><strong>{month.toLocaleDateString('de-CH', { month: 'long', year: 'numeric' })}</strong><button className="secondary" aria-label="Nächster Monat" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>›</button></div>
    <div className="calendar-grid">{['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].map(day => <span key={day}>{day}</span>)}
      {Array.from({ length: offset }, (_, i) => <span key={`blank-${i}`} />)}
      {Array.from({ length: days }, (_, i) => {
        const value = iso(new Date(month.getFullYear(), month.getMonth(), i + 1))
        const endpoint = value === first || value === last
        return <button key={value} type="button" aria-label={value} aria-pressed={endpoint} aria-current={value === today ? 'date' : undefined} disabled={value > today || value < iso(minimum)} className={`${endpoint ? 'calendar-endpoint' : ''} ${first && last && value > first && value < last ? 'calendar-between' : ''}`} onClick={() => choose(value)}>{i + 1}</button>
      })}
    </div>
    <p role="status">{!first ? 'Startdatum auswählen' : !last ? `${first} · Jetzt Enddatum auswählen` : `${first} – ${last}`}</p>
    <footer className="dialog-footer"><button className="secondary" onClick={() => { setFirst(''); setLast('') }}>Auswahl löschen</button><button className="primary" disabled={!first || !last} onClick={() => onConfirm(first, last)}>Zeitraum bestätigen</button></footer>
  </dialog>
}
