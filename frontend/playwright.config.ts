import { defineConfig, devices } from "@playwright/test";

const viteApiBaseUrl = process.env.PLAYWRIGHT_VITE_API_BASE_URL ?? "/api/v1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  webServer: {
    command: `VITE_API_BASE_URL=${viteApiBaseUrl} npm run dev -- --host 127.0.0.1 --port 4173 --strictPort`,
    port: 4173,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
