import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Login } from './Login'
import type { DesktopApi, Result, Session } from '../types/bridge'

function fill() {
  fireEvent.change(screen.getByLabelText('Benutzername'), { target: { value: 'test-agent' } })
  fireEvent.change(screen.getByLabelText('Passwort'), { target: { value: 'synthetic-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
}
describe('Znuny login', () => {
  it('clears the password while the Python call is still pending', async () => {
    let finish!: (result: Result<Session>) => void
    const login = vi.fn(() => new Promise<Result<Session>>(resolve => { finish = resolve }))
    const onLogin = vi.fn()
    render(<Login api={{ login } as unknown as DesktopApi} onLogin={onLogin} bridgeError="" />)
    fill()
    expect(login).toHaveBeenCalledWith('test-agent', 'synthetic-password')
    expect(screen.getByLabelText('Passwort')).toHaveValue('')
    expect(screen.getByRole('button')).toBeDisabled()
    finish({ ok: true, data: { username: 'test-agent' } })
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith({ username: 'test-agent' }))
  })
  it.each(['Anmeldung fehlgeschlagen. Bitte Benutzername und Passwort prüfen.', 'Znuny ist nicht erreichbar. Bitte Netzwerk oder Serververbindung prüfen.'])('renders the distinct backend error: %s', async message => {
    const login = vi.fn().mockResolvedValue({ ok: false, error: { kind: 'test', message } })
    render(<Login api={{ login } as unknown as DesktopApi} onLogin={vi.fn()} bridgeError="" />)
    fill()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByLabelText('Passwort')).toHaveValue('')
  })
  it('validates empty input before calling Python', () => {
    const login = vi.fn()
    render(<Login api={{ login } as unknown as DesktopApi} onLogin={vi.fn()} bridgeError="" />)
    fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Benutzername und Passwort')
    expect(login).not.toHaveBeenCalled()
  })
})
