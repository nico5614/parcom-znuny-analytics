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
  it('defaults saving off, saves only when opted in and clears password immediately', async () => {
    const login = vi.fn().mockResolvedValue({ ok: true, data: { username: 'test-agent' } })
    const getSavedCredentials = vi.fn().mockResolvedValue({ supported: true, available: false, username: null })
    render(<Login api={{ login, getSavedCredentials } as unknown as DesktopApi} onLogin={vi.fn()} bridgeError="" />)
    const checkbox = screen.getByRole('checkbox', { name: 'Zugangsdaten speichern' })
    expect(checkbox).not.toBeChecked()
    await waitFor(() => expect(checkbox).toBeEnabled())
    fireEvent.click(checkbox); fill()
    expect(login).toHaveBeenCalledWith('test-agent', 'synthetic-password', true)
    expect(screen.getByLabelText('Passwort')).toHaveValue('')
  })
  it('uses and removes saved credentials without receiving a password', async () => {
    const loginSaved = vi.fn().mockResolvedValue({ ok: false, error: { message: 'Sitzung nicht verfügbar.' } })
    const removeSavedCredentials = vi.fn().mockResolvedValue({ ok: true, data: null })
    const api = { getSavedCredentials: vi.fn().mockResolvedValue({ supported: true, available: true, username: 'saved-user' }), loginSaved, removeSavedCredentials } as unknown as DesktopApi
    render(<Login api={api} onLogin={vi.fn()} bridgeError="" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Gespeicherte Anmeldung verwenden' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sitzung nicht verfügbar.')
    expect(screen.getByLabelText('Passwort')).toHaveValue('')
    fireEvent.click(screen.getByRole('button', { name: 'Gespeicherte Zugangsdaten entfernen' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Gespeicherte Anmeldung verwenden' })).toBeNull())
    expect(removeSavedCredentials).toHaveBeenCalledOnce()
    expect(loginSaved).toHaveBeenCalledWith()
  })
  it.each(['light', 'dark'] as const)('offers the %s toggle before authentication', theme => {
    const onTheme = vi.fn()
    render(<Login theme={theme} onTheme={onTheme} onLogin={vi.fn()} bridgeError="" />)
    const toggle = screen.getByRole('button', { name: 'Helles oder dunkles Design' })
    expect(toggle).toHaveAttribute('aria-pressed', String(theme === 'dark'))
    fireEvent.click(toggle)
    expect(onTheme).toHaveBeenCalledOnce()
  })
  it('clears the password while the Python call is still pending', async () => {
    let finish!: (result: Result<Session>) => void
    const login = vi.fn(() => new Promise<Result<Session>>(resolve => { finish = resolve }))
    const onLogin = vi.fn()
    render(<Login api={{ login } as unknown as DesktopApi} onLogin={onLogin} bridgeError="" />)
    fill()
    expect(login).toHaveBeenCalledWith('test-agent', 'synthetic-password')
    expect(screen.getByLabelText('Passwort')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Anmeldung läuft …' })).toBeDisabled()
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
