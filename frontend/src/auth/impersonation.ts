// فاز ۶۰ - حالت «ورود مدیر با هویت کاربر» (impersonation)
//
// هدف کارفرما: «از وقتی کارتابل را می‌زنم انگار با یوزر طرف مقابل وارد شوم و
// همهٔ قسمت‌ها را ببینم» — یعنی کل پنل (منوها، صفحات، داده‌ها) دقیقاً از
// نقطهٔ نظر همان کاربر رندر شود، نه فقط یک نمای خلاصه.
//
// سازوکار:
// - بک‌اند توکن دسترسی مستقل برای کاربر هدف صادر می‌کند (بدون نشست refresh)؛
// - توکن + اطلاعات حالت در sessionStorage (محدود به همین تب) نگه‌داری می‌شود تا
//   پس از reload کامل صفحه هم نشستِ مشاهده برقرار بماند — با بسته‌شدن تب پاک
//   می‌شود و برخلاف localStorage ماندگار نیست؛
// - کوکی refresh متعلق به مدیر دست‌نخورده می‌ماند → «بازگشت به حساب مدیر» فقط
//   با حذف این کلید و reload انجام می‌شود؛
// - client.ts هنگام فعال‌بودن این حالت هرگز refresh نمی‌زند (کوکی مدیر را
//   نمی‌خواند) و با 401 به‌طور خودکار از حالت مشاهده خارج می‌شود.

const KEY = "rosepsy_impersonation";

export interface ImpersonationInfo {
  /** توکن دسترسی کاربر هدف (صادره توسط POST /users/{id}/impersonate) */
  token: string;
  userId: string;
  username: string;
  displayName: string;
  /** مسیر بازگشت مدیر (صفحه‌ای که از آن وارد حالت مشاهده شد) */
  returnPath: string;
  startedAt: string;
}

export function readImpersonation(): ImpersonationInfo | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ImpersonationInfo;
    if (!parsed?.token || !parsed?.userId) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function startImpersonation(info: ImpersonationInfo): void {
  sessionStorage.setItem(KEY, JSON.stringify(info));
}

export function endImpersonation(): void {
  sessionStorage.removeItem(KEY);
}

export function isImpersonating(): boolean {
  return readImpersonation() !== null;
}
