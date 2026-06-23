import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 1,
  use: {
    baseURL: 'http://localhost:5899',
    headless: true,
  },
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5899',
    reuseExistingServer: true,
  },
})
