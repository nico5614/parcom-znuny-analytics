import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Timeline } from './Timeline'
import type { DesktopApi, Period } from '../types/bridge'

const period: Period = { start: '2026-10-01T12:00:00+02:00', end: '2026-10-08T12:00:00+02:00', startInput: '2026-10-01T12:00', endInput: '2026-10-08T12:00', label: 'Python-Zeitraum', preset: '1W', presets: ['1J', '6M', '3M', '1M', '1W', '1T'] }
describe('Python-owned timeline', () => {
  it('has two keyboard handles and uses the resolved Python interval', async () => {
    const resolved = { ...period, preset: '1T', label: 'Exakt aus Python' }
    const resolvePeriod = vi.fn().mockResolvedValue({ ok: true, data: resolved })
    const onChange = vi.fn()
    render(<Timeline api={{ resolvePeriod } as unknown as DesktopApi} period={period} onChange={onChange} />)
    expect(screen.getAllByRole('slider')).toHaveLength(2)
    fireEvent.keyDown(screen.getByRole('slider', { name: 'Zeitraum-Ende' }), { key: 'End' })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(resolved))
    expect(resolvePeriod).toHaveBeenCalledWith({ preset: '1T' })
  })
  it('submits exact custom inputs and shows Python validation without changing data', async () => {
    const resolvePeriod = vi.fn().mockResolvedValue({ ok: false, error: { kind: 'validation', message: 'Mindestens ein Tag ist erforderlich.' } })
    const onChange = vi.fn()
    render(<Timeline api={{ resolvePeriod } as unknown as DesktopApi} period={period} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Von'), { target: { value: '2026-10-08T10:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Anwenden' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Mindestens ein Tag')
    expect(resolvePeriod).toHaveBeenCalledWith({ preset: null, start: '2026-10-08T10:00', end: period.endInput })
    expect(onChange).not.toHaveBeenCalled()
  })
  it('custom mode spans the full track and the next handle action returns to snap mode', async () => {
    const resolvePeriod = vi.fn().mockResolvedValue({ ok: true, data: { ...period, preset: '1J' } })
    const onChange = vi.fn()
    const { container } = render(<Timeline api={{ resolvePeriod } as unknown as DesktopApi} period={{ ...period, preset: null }} onChange={onChange} />)
    expect((container.querySelector('.timeline-selected') as HTMLElement).style.left).toBe('0%')
    expect(container.querySelector('.custom-labels')).toHaveTextContent('2026-10-01 12:00')
    fireEvent.keyDown(screen.getByRole('slider', { name: 'Zeitraum-Beginn' }), { key: 'Home' })
    await waitFor(() => expect(resolvePeriod).toHaveBeenCalledWith({ preset: '1J' }))
  })
})
