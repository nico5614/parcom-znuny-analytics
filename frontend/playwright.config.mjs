import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', workers: 1, timeout: 30000,
  outputDir: '.validation/browser-results', reporter: 'list',
  use: { channel: 'msedge', baseURL: 'http://127.0.0.1:4178', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop-1920', use: { viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 } },
    { name: 'compact-1050', use: { viewport: { width: 1050, height: 650 }, deviceScaleFactor: 1 } },
    { name: 'dpi-125', use: { viewport: { width: 1536, height: 864 }, deviceScaleFactor: 1.25 } },
    { name: 'dpi-150', use: { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5 } },
  ],
  webServer: { command: 'pnpm exec vite preview --host 127.0.0.1 --port 4178 --strictPort', url: 'http://127.0.0.1:4178', reuseExistingServer: false },
})
