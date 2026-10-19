// فاز ۳۷ - گام اول آزمون E2E (دسته ۳/۴/۶ سند جامع) — دود ساده مسیرهای حیاتی
// اجرا: npm i -D @playwright/test && npx playwright test
// متغیرها: E2E_BASE_URL / E2E_API_URL / E2E_USER / E2E_PASS (README همین پوشه)
import { expect, test } from "@playwright/test";

const USER = process.env.E2E_USER;
const PASS = process.env.E2E_PASS;

test.describe("Rosepsy - E2E smoke", () => {
  test("سلامت API پاسخ می‌دهد", async ({ request }) => {
    const r = await request.get("/api/v1/health");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.status ?? body.app_name ?? "ok").toBeTruthy();
  });

  test("مسیر محافظت‌شده بدون نشست به ورود برمی‌گردد", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("ورود موفق کاربر از /login عبور می‌کند", async ({ page }) => {
    test.skip(!USER || !PASS, "E2E_USER/E2E_PASS تنظیم نشده است");
    await page.goto("/login");
    await page.getByLabel("نام کاربری").fill(USER!);
    await page.getByLabel("رمز عبور").fill(PASS!);
    await page.getByRole("button", { name: /ورود/ }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator("body")).toContainText(/رز|Rosepsy|داشبورد/);
  });

  test("اعلان‌ها پس از ورود بارگذاری می‌شود", async ({ page }) => {
    test.skip(!USER || !PASS, "E2E_USER/E2E_PASS تنظیم نشده است");
    await page.goto("/login");
    await page.getByLabel("نام کاربری").fill(USER!);
    await page.getByLabel("رمز عبور").fill(PASS!);
    await page.getByRole("button", { name: /ورود/ }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.goto("/notifications");
    await expect(page.locator("body")).toContainText(/اعلان/);
  });
});
