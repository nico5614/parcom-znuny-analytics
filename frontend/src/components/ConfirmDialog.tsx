import { useEffect, useRef } from 'react'
export function ConfirmDialog({ title, body, confirmLabel, onConfirm, onCancel }: { title: string; body: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { const current = dialog.current!; current.showModal(); return () => current.close() }, [])
  return <dialog ref={dialog} className="ticket-dialog confirm-dialog" aria-labelledby="confirmation-title" onCancel={event => { event.preventDefault(); onCancel() }}><div className="dialog-header"><h2 id="confirmation-title">{title}</h2></div><p>{body}</p><footer className="dialog-footer"><button className="secondary" autoFocus onClick={onCancel}>Abbrechen</button><button className="primary" onClick={onConfirm}>{confirmLabel}</button></footer></dialog>
}
