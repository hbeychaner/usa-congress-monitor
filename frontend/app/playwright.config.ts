import { defineConfig } from '@playwright/test';

const baseURL = process.env.BROWSER_BASE_URL ?? 'http://127.0.0.1:4175';

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 2,
  timeout: 30_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    browserName: 'chromium',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'narrow', use: { viewport: { width: 320, height: 740 } } },
  ],
  webServer: process.env.BROWSER_EXTERNAL_SERVER === '1' ? undefined : {
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${new URL(baseURL).port} --strictPort`,
    url: baseURL,
    env: { VITE_API_BASE_URL: process.env.BROWSER_API_BASE_URL ?? 'http://127.0.0.1:8000' },
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
