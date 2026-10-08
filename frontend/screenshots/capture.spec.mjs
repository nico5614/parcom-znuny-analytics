import { test, expect } from '@playwright/test'
import { readFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { setup } from '../e2e/desktop-fixture.mjs'

test('capture the implemented frontend with anonymous synthetic Python DTOs', async ({ page }) => {
  const data = JSON.parse(readFileSync(new URL('../.validation/docs-fixtures.json', import.meta.url), 'utf8'))
  const destination = new URL('../../docs/screenshots/', import.meta.url)
  mkdirSync(destination, { recursive: true })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const capture = async name => {
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, destination)), fullPage: true, animations: 'disabled' })
  }
  const nav = name => page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('button', { name, exact: true })
  await setup(page, data)
  await expect(page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible()
  await capture('login')
  await page.getByRole('button', { name: 'Lokalen Datenstand öffnen' }).click()
  await expect(page.getByRole('heading', { name: 'Ticketentwicklung' })).toBeVisible()
  await capture('dashboard-hero')
  await nav('Analysen').click()
  await page.getByRole('tab').nth(3).click()
  await expect(page.getByRole('heading', { name: data.analyses['4'].all.title, exact: true }).first()).toBeVisible()
  await capture('analytics')
  await nav('Agenten').click()
  await expect(page.getByText('Informelles Ranking', { exact: true })).toBeVisible()
  await capture('agents')
  await nav('Übersicht').click()
  await page.getByRole('button', { name: /^TEST/ }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('Kundennummer', { exact: true })).toBeVisible()
  await capture('ticket-details')
  await page.getByRole('dialog').getByRole('button', { name: 'Schliessen' }).first().click()
  await nav('Export').click()
  await expect(page.getByRole('button', { name: 'Als PDF speichern' })).toBeVisible()
  await capture('export')
  expect(errors).toEqual([])
})
