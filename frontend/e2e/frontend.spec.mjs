import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixtures = JSON.parse(readFileSync(new URL('../.validation/fixtures.json', import.meta.url), 'utf8'))
async function setup(page) {
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message))
  await page.addInitScript(data => {
    const calls = []
    const state = { connection: 'cached', busy: false, newData: false, revision: 0, capturedAt: data.capturedAt, hasCache: true, warning: '' }
    let period = data.periods['1W']
    let preferences = { theme: 'dark', reducedMotion: false }
    window.validation = { calls, failRefresh: false, refreshDelay: 0, exportDelay: 0 }
    const record = (name, args) => calls.push({ name, args })
    const ok = value => ({ ok: true, data: value })
    window.pywebview = { api: {
      getAppInfo: async () => ({ name: 'ParCom Analytics', version: '1.0.0', python: '3.14.8', renderer: 'Windows WebView2', packaged: false }),
      probe: async () => { window.dispatchEvent(new CustomEvent('parcom:desktop', { detail: { kind: 'probe', sequence: 1 } })); return { sequence: 1 } },
      confirmProbe: async () => true,
      getState: async () => ({ ...state }), getPeriod: async () => ({ ...period }),
      getPreferences: async () => preferences, setPreferences: async (theme, reducedMotion) => { preferences = { theme, reducedMotion }; return ok(null) },
      continueOffline: async () => ok({ username: 'Offline' }),
      login: async (username, password) => { record('login', [username, password.length]); if (username === 'network-error') return { ok: false, error: { kind: 'network', message: 'Znuny ist nicht erreichbar.' } }; if (username !== 'validation' || password !== 'validation') return { ok: false, error: { kind: 'authentication', message: 'Anmeldung fehlgeschlagen.' } }; state.connection = 'online'; return ok({ username }) },
      logout: async () => { record('logout', []); state.connection = 'cached'; return ok(null) },
      resolvePeriod: async selection => { record('resolvePeriod', [selection]); if (selection.preset) return ok(data.periods[selection.preset]); if (selection.start === data.custom.startInput && selection.end === data.custom.endInput) return ok(data.custom); return { ok: false, error: { kind: 'validation', message: 'Mindestens ein Tag ist erforderlich.' } } },
      refresh: async selection => { record('refresh', [selection]); await new Promise(resolve => setTimeout(resolve, window.validation.refreshDelay)); if (window.validation.failRefresh) return { ok: false, error: { kind: 'network', message: 'Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.' } }; period = selection.preset ? data.periods[selection.preset] : data.custom; state.revision++; return ok({ ...state }) },
      checkChanges: async () => ({ ...state, newData: true }),
      getOverview: async () => { record('getOverview', []); return ok(data.overview) },
      getAnalysis: async (kpi, type, page) => { record('getAnalysis', [kpi, type, page]); return ok(data.analyses[kpi][type || 'all']) },
      getAgents: async (id, page) => { record('getAgents', [id, page]); return ok(data.agents) },
      setTeam: async selected => { record('setTeam', [selected]); data.agents.selected = selected; state.revision++; return ok({ ...state }) },
      getTicketDetails: async id => { record('getTicketDetails', [id]); return ok(data.tickets[id]) },
      openTicket: async id => { record('openTicket', [id]); return ok(null) },
      getExportOptions: async () => Object.entries(data.analyses).map(([id, kinds]) => ({ id, label: kinds.all.title, types: kinds.all.types })),
      exportPdf: async (target, type) => { record('exportPdf', [target, type]); await new Promise(resolve => setTimeout(resolve, window.validation.exportDelay)); return ok({ cancelled: false, filename: 'synthetic-report.pdf' }) },
    } }
  }, structuredClone(fixtures))
  await page.goto('/')
}
const nav = (page, name) => page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('button', { name, exact: true })
async function offline(page) { await setup(page); await page.getByRole('button', { name: 'Lokalen Datenstand öffnen' }).click(); await expect(page.getByRole('heading', { name: 'Ticketentwicklung' })).toBeVisible() }

test('cached dashboard and complete navigation, ticket, team, export and logout', async ({ page }, info) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message))
  await offline(page)
  await expect(page.getByText('Lokaler Datenstand', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `.validation/overview-${info.project.name}.png`, fullPage: true })
  if (info.project.name === 'desktop-1920') expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(1080)
  await nav(page, 'Analysen').click()
  for (const [index, data] of Object.entries(fixtures.analyses)) {
    await page.getByRole('tab').nth(Number(index) - 1).click()
    await expect(page.getByRole('heading', { name: data.all.title, exact: true }).first()).toBeVisible()
  }
  await page.getByRole('tab').nth(4).click()
  await page.getByLabel('Tickettyp', { exact: true }).selectOption('Auftrag')
  await expect.poll(() => page.evaluate(() => window.validation.calls.filter(call => call.name === 'getAnalysis').at(-1).args)).toEqual([5, 'Auftrag', 0])
  await page.screenshot({ path: `.validation/analysis-${info.project.name}.png`, fullPage: true })
  await nav(page, 'Agenten').click()
  await expect(page.getByText('Informelles Ranking', { exact: true })).toBeVisible()
  await page.screenshot({ path: `.validation/agents-${info.project.name}.png`, fullPage: true })
  await page.getByRole('button', { name: 'Team verwalten' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('dialog').getByRole('checkbox').last().check()
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await nav(page, 'Übersicht').click()
  const cachedCalls = await page.evaluate(() => window.validation.calls.filter(call => call.name === 'getOverview').length)
  await nav(page, 'Info').click()
  await page.getByRole('checkbox', { name: /Bewegungen reduzieren/ }).check()
  await expect(page.locator('html')).toHaveAttribute('data-reduced-motion', 'true')
  await nav(page, 'Übersicht').click()
  expect(await page.evaluate(() => window.validation.calls.filter(call => call.name === 'getOverview').length)).toBe(cachedCalls)
  await page.getByRole('button', { name: /^TEST/ }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('Kundennummer', { exact: true })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: /In Znuny/ }).click()
  await expect.poll(() => page.evaluate(() => window.validation.calls.some(call => call.name === 'openTicket'))).toBe(true)
  await page.getByRole('dialog').getByRole('button', { name: 'Schliessen' }).first().click()
  await page.getByRole('button', { name: 'Helles oder dunkles Design' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.screenshot({ path: `.validation/light-${info.project.name}.png`, fullPage: true })
  await nav(page, 'Export').click()
  await page.getByLabel('Auswertung', { exact: true }).selectOption('5')
  await page.getByLabel('Tickettyp im Export', { exact: true }).selectOption('Auftrag')
  await page.getByRole('button', { name: 'Als PDF speichern' }).click()
  await expect(page.getByRole('status')).toHaveText('PDF gespeichert: synthetic-report.pdf')
  expect(await page.evaluate(() => window.validation.calls.filter(call => call.name === 'exportPdf').at(-1).args)).toEqual(['5', 'Auftrag'])
  await page.getByRole('button', { name: 'Logout', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('login errors, custom interval, handle snap, cached refresh and pending navigation', async ({ page }) => {
  await setup(page)
  await page.getByLabel('Benutzername', { exact: true }).fill('wrong')
  await page.getByLabel('Passwort', { exact: true }).fill('wrong')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('Anmeldung fehlgeschlagen.')
  await expect(page.getByLabel('Passwort', { exact: true })).toHaveValue('')
  await page.getByLabel('Benutzername', { exact: true }).fill('network-error')
  await page.getByLabel('Passwort', { exact: true }).fill('wrong')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('Znuny ist nicht erreichbar.')
  await page.getByLabel('Benutzername', { exact: true }).fill('validation')
  await page.getByLabel('Passwort', { exact: true }).fill('validation')
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Ticketentwicklung' })).toBeVisible()
  await page.getByLabel('Von', { exact: true }).fill(fixtures.custom.startInput)
  await page.getByLabel('Bis', { exact: true }).fill(fixtures.custom.endInput)
  await page.getByRole('button', { name: 'Anwenden' }).click()
  await expect(page.locator('.custom-labels')).toBeVisible()
  await expect(page.locator('.timeline-selected')).toHaveCSS('left', '0px')
  await page.getByRole('slider', { name: 'Zeitraum-Beginn' }).press('End')
  await expect(page.getByRole('slider', { name: 'Zeitraum-Beginn' })).toHaveAttribute('aria-valuetext', '1T')
  await page.evaluate(() => { window.validation.refreshDelay = 1400; window.validation.failRefresh = true })
  await page.getByRole('button', { name: 'Aktualisieren', exact: true }).click()
  await expect(page.getByText('Znuny-Daten werden geladen …', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ticketentwicklung' })).toBeVisible()
  await nav(page, 'Agenten').click()
  await expect(page.getByText('Informelles Ranking', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('Sitzung ist abgelaufen')
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0)
})
