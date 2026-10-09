import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricCard } from './Card'
import { compactTime, meanDetail, MetricTrend } from './MetricTrend'
import type { Metric } from '../types/bridge'

const base: Metric = { label: 'Aktuell offen', value: '32', note: 'Alte Notiz', tone: 'default' }
describe('backend metric semantics', () => {
  it.each(['Stand jetzt', 'Stand am 07.10.2026 12:34', 'Ausgewählter Zeitraum'])('renders the exact supplied context %s', contextLabel => {
    render(<MetricCard metric={{ ...base, contextLabel }} />)
    expect(screen.getByText(contextLabel)).toBeVisible()
    expect(screen.queryByText('Alte Notiz')).not.toBeInTheDocument()
  })
  it('keeps the snapshot value neutral and omits unavailable deltas', () => {
    const { container } = render(<MetricCard metric={{ ...base, metricType: 'snapshot', delta: 10, deltaAvailable: false }} />)
    expect(screen.getByText('32').className).toBe('')
    expect(container.querySelector('.metric-trend')).toBeNull()
  })
  it('uses the supplied semantic trend rather than deriving business meaning from the label', () => {
    render(<MetricTrend metric={{ ...base, delta: -5, deltaAvailable: true, trend: 'improvement' }} />)
    expect(screen.getByLabelText('Verbesserung: −5 Tickets')).toHaveClass('improvement')
    expect(screen.getByText('▼')).toBeVisible()
  })
  it('renders percentage and time units with arrow and sign', () => {
    render(<><MetricTrend metric={{ ...base, value: '50 %', delta: 4.2, deltaAvailable: true, trend: 'improvement', unit: 'percent' }} /><MetricTrend metric={{ ...base, delta: -72, deltaAvailable: true, trend: 'improvement', unit: 'minutes' }} /></>)
    expect(screen.getByLabelText('Verbesserung: +4.2 %')).toBeVisible()
    expect(screen.getByLabelText('Verbesserung: −1 h 12 min')).toBeVisible()
  })
  it.each([[18, '18 min'], [72, '1 h 12 min'], [60, '1 h'], [0, '0 min']])('formats %s minutes compactly', (minutes, label) => {
    expect(compactTime(Number(minutes))).toBe(label)
  })
  it('uses the supplied arithmetic mean for service details, including zero', () => {
    expect(meanDetail({ ...base, label: 'Median Reaktionszeit' }, { 'Durchschnitt Reaktionszeit': { value: 0 } })).toBe('Durchschnitt: 0 min')
    expect(meanDetail({ ...base, label: 'Median Lösungszeit' }, {})).toBeUndefined()
  })
})
