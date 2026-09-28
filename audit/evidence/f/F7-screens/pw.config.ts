import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: '.', timeout: 60_000, workers: 1, reporter: [['list']],
  use: { locale: 'vi-VN', viewport: { width: 1440, height: 900 } },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: { command: 'PORT=18090 npx max preview --port 18090', url: 'http://127.0.0.1:18090/upload', reuseExistingServer: false, timeout: 60_000, cwd: '..' },
});
