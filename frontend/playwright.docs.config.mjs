import base from './playwright.config.mjs'
import { defineConfig } from '@playwright/test'

export default defineConfig({
  ...base,
  testDir: './screenshots',
  projects: [{ name: 'documentation', use: { viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 } }],
})
