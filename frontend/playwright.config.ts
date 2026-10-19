// فاز ۳۷ - گام اول آزمون E2E (دسته ۳/۴/۶ سند جامع)
// Playwright config — اجرا روی سیستم توسعه؛ جزو build نیست (خارج از tsconfig/vite)
// پیش‌نیازها و دستور اجرا: frontend/e2e/README.md
import { defineConfig } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const apiURL = process.env.E2E_API_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    apiURL,
    headless: true,
    viewport: { width: 1366, height: 850 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
