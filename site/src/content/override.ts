// فاز ۸۴ — لایهٔ بازنویسی محتوای سایت از پنل ادمین (ویرایشگر صفحات عمومی)
//
// گردش کار:
// ۱) اپ با متن‌های پیش‌فرض (همین فایل‌ها) رندر می‌شود — اولین رنگ‌آمیزی سریع،
//    حتی اگر API در دسترس نباشد؛
// ۲) روی همان، سندهای «منتشرشده» از GET /api/v1/site-content/public واکشی و
//    در جا (mutate) روی اشیاء ماژول اعمال می‌شود؛ چون همهٔ کامپوننت‌ها به همین
//    اشیاء ارجاع دارند، یک re-render کافی است تا متن‌های ویرایش‌شده دیده شوند؛
// ۳) اگر API در دسترس نبود یا سندی منتشر نشده بود، هیچ اتفاقی نمی‌افتد —
//    یعنی سایت همیشه حداقل با متن‌های پیش‌فرض کامل است.
import { texts } from "./texts";
import { psycho } from "./psycho";
import { payRules } from "./payRules";
import { clinics } from "./clinics";
import { specialist } from "./specialist";

type Doc = Record<string, unknown>;

// فاز ۸۵: کلیدهای «clinics» و «specialist» هم به ویرایشگر پیوستند
export const CONTENT_PAGE_KEYS = ["home", "psycho", "payment-rules", "clinics", "specialist"] as const;
export type ContentPageKey = (typeof CONTENT_PAGE_KEYS)[number];

const TARGETS: Record<ContentPageKey, Doc> = {
  home: texts as unknown as Doc,
  psycho: psycho as unknown as Doc,
  "payment-rules": payRules as unknown as Doc,
  clinics: clinics as unknown as Doc,
  specialist: specialist as unknown as Doc,
};

function isPlainObject(v: unknown): v is Doc {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** اعمال سند منتشرشده روی شیء هدف — در جا، تا ارجاع مشترک حفظ شود */
function applyInPlace(target: Doc, over: Doc, depth = 0): boolean {
  let changed = false;
  for (const key of Object.keys(over)) {
    const nv = over[key];
    const cv = target[key];
    if (isPlainObject(nv) && isPlainObject(cv) && depth < 4) {
      changed = applyInPlace(cv, nv, depth + 1) || changed;
    } else if (JSON.stringify(cv) !== JSON.stringify(nv)) {
      // کلون کامل تا هیچ ارجاعی از سند DB داخل اپ باقی نماند
      target[key] = JSON.parse(JSON.stringify(nv));
      changed = true;
    }
  }
  return changed;
}

let appliedOnce = false;
let appliedChanged = false;

/** واکشی سندهای منتشرشده و اعمال روی محتوای پیش‌فرض — خطا بی‌صدا (fallback) */
export async function fetchAndApplySiteContent(): Promise<boolean> {
  try {
    const r = await fetch("/api/v1/site-content/public", { cache: "no-store" });
    if (!r.ok) return false;
    const data = (await r.json()) as Record<string, Doc | null>;
    let changed = false;
    for (const key of CONTENT_PAGE_KEYS) {
      const doc = data?.[key];
      if (doc && typeof doc === "object" && !Array.isArray(doc)) {
        changed = applyInPlace(TARGETS[key], doc) || changed;
      }
    }
    appliedOnce = true;
    appliedChanged = changed;
    return changed;
  } catch {
    // API در دسترس نیست — سایت با متن‌های پیش‌فرض ادامه می‌دهد
    return false;
  }
}

/** آیا حداقل یک‌بار واکشی انجام شده است؟ (برای تشخیص اتمام لود در تست‌ها) */
export function siteContentLoaded(): boolean {
  return appliedOnce;
}

/** آیا واکشیِ آخر تغییری در محتوا داد؟ */
export function siteContentChanged(): boolean {
  return appliedChanged;
}
