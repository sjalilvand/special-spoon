import { lazy } from "react";

/**
 * فاز ۸۱ — lazy مقاوم به قطعیِ شبکه (عارضهٔ میدانی: «تا رفرش نکنیم کار نمی‌کند»)
 *
 * تقسیم کد مسیرمحور (فاز ۷۷) یعنی ورود به هر صفحهٔ جدید = دانلود یک chunk تازه.
 * روی اینترنت موبایل/ضغیف، دانلود همان chunk گاهی شکست می‌خورد؛ React.lazy
 * وعدهٔ شکست‌خورده را کش می‌کند و هر تلاش بعدی بلافاصله همان خطا را دوباره
 * می‌اندازد — کاربر تا رفرش کامل صفحه (دریافت index.html تازه) در همان صفحه
 * گیر می‌کند. این پوشش، ایمپورت را ۳ بار با تأخیر فزاینده تکرار می‌کند؛
 * مرورگر هم ماژولِ شکست‌خورده را از کش نمی‌گیرد، پس هر تلاش دانلود تازه است.
 */
export function lazyRetry<T extends { default: React.ComponentType<unknown> }>(
  importer: () => Promise<T>
) {
  return lazy(async () => {
    let lastError: unknown;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        return await importer();
      } catch (err) {
        lastError = err;
        if (attempt < 3) {
          await new Promise((resolve) => setTimeout(resolve, 400 * attempt));
        }
      }
    }
    throw lastError;
  });
}
