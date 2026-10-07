import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'

export default defineConfig({
  base: './',
  plugins: [react(), tailwind()],
  build: { outDir: 'dist', sourcemap: false, target: 'es2022' },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], clearMocks: true },
})
