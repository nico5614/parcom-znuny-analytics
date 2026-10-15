import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DateRangeDialog } from './DateRangeDialog'

HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-15T10:00:00Z')) })
afterEach(() => vi.useRealTimers())
describe('date range selection', () => {
  it('marks today, selects an inclusive range and only submits on confirmation', () => {
    const submit = vi.fn()
    render(<DateRangeDialog start="2026-10-09" end="2026-10-15" onConfirm={submit} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: '2026-10-15' })).toHaveAttribute('aria-current', 'date')
    expect(screen.getByRole('button', { name: '2026-10-16' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '2026-10-09' }))
    expect(screen.getByRole('button', { name: 'Zeitraum bestätigen' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '2026-10-14' }))
    expect(screen.getByRole('button', { name: '2026-10-12' })).toHaveClass('calendar-between')
    expect(submit).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Zeitraum bestätigen' }))
    expect(submit).toHaveBeenCalledWith('2026-10-09', '2026-10-14')
  })
  it('clears selection, supports reverse order and preserves cancellation', () => {
    const submit = vi.fn(), close = vi.fn()
    render(<DateRangeDialog start="2026-10-09" end="2026-10-15" onConfirm={submit} onClose={close} />)
    fireEvent.click(screen.getByRole('button', { name: '2026-10-14' }))
    fireEvent.click(screen.getByRole('button', { name: '2026-10-09' }))
    expect(screen.getByRole('status')).toHaveTextContent('2026-10-09 – 2026-10-14')
    fireEvent.click(screen.getByRole('button', { name: 'Auswahl löschen' }))
    expect(screen.getByRole('button', { name: 'Zeitraum bestätigen' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(close).toHaveBeenCalledOnce()
    expect(submit).not.toHaveBeenCalled()
  })
  it('selects across months and permits a single day', () => {
    const submit = vi.fn()
    render(<DateRangeDialog start="2026-09-30" end="2026-10-15" onConfirm={submit} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    fireEvent.click(screen.getByRole('button', { name: '2026-09-30' }))
    fireEvent.click(screen.getByRole('button', { name: 'Nächster Monat' }))
    fireEvent.click(screen.getByRole('button', { name: '2026-10-02' }))
    fireEvent.click(screen.getByRole('button', { name: 'Zeitraum bestätigen' }))
    expect(submit).toHaveBeenCalledWith('2026-09-30', '2026-10-02')
    fireEvent.click(screen.getByRole('button', { name: 'Auswahl löschen' }))
    fireEvent.click(screen.getByRole('button', { name: '2026-10-02' }))
    fireEvent.click(screen.getByRole('button', { name: '2026-10-02' }))
    fireEvent.click(screen.getByRole('button', { name: 'Zeitraum bestätigen' }))
    expect(submit).toHaveBeenLastCalledWith('2026-10-02', '2026-10-02')
  })
})
