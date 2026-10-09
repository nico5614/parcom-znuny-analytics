import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { PeriodEmployee } from './PeriodEmployee'
import type { AgentRow } from '../types/bridge'
const base: AgentRow = { id: '61', displayName: 'Testtechniker', abbreviation: 'TST', isPeriodWinner: true, Geschlossen: 8, Erstantworten: 4, 'Aktuell im Besitz': 2, 'Davon gesperrt': 0, 'Reaktionszeit (Min.)': 0, medianResponseMinutes: 0, meanResponseMinutes: 18 }
it('renders supplied winners, tied winners and zero-minute median without inferring a winner', () => {
  const { container } = render(<PeriodEmployee winners={[base, { ...base, id: '62', displayName: 'Gleichstand' }, { ...base, id: '63', displayName: 'Kein Gewinner', isPeriodWinner: false, Geschlossen: 99 }]} available />)
  expect(screen.getAllByText('0 min')).toHaveLength(2)
  expect(screen.getByText('Gleichstand')).toBeVisible()
  expect(screen.queryByText('Kein Gewinner')).toBeNull()
  expect(container.querySelectorAll('article')).toHaveLength(2)
  expect(screen.getAllByText('Durchschnitt: 18 min')).toHaveLength(2)
})
it('shows an honest unavailable history message', () => {
  render(<PeriodEmployee available={false} />)
  expect(screen.getByText('Historie noch nicht verfügbar.')).toBeVisible()
})
