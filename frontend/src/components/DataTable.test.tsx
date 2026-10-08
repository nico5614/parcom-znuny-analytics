import { fireEvent, render, screen } from '@testing-library/react'
import { it, expect, vi } from 'vitest'
import { DataTable } from './DataTable'
it('uses only backend ticket IDs and explicit pagination', () => {
  const onTicket = vi.fn(), onPage = vi.fn()
  render(<DataTable dto={{ columns: [{ key: 'number', label: 'Ticketnummer' }], rows: [{ key: '51', ticketId: '51', cells: ['TEST00051'], tone: 'critical' }], total: 101, page: 0, pageSize: 50 }} onTicket={onTicket} onPage={onPage} />)
  fireEvent.click(screen.getByRole('button', { name: 'TEST00051' }))
  expect(onTicket).toHaveBeenCalledWith('51')
  expect(screen.getByRole('button', { name: 'Zurück' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }))
  expect(onPage).toHaveBeenCalledWith(1)
})
