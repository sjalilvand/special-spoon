// فاز ۹۳ — قواعد سمت مرورگر فرم فراخوان همکاری: الگوریتم کد ملی + محدودهٔ سن
//
// خواستهٔ صاحب سامانه (چک‌لیست فرم فراخوان):
// 1) الگوریتم رسمی کد ملی — همان جمع وزنی ۹ رقم اول × (۱۰..۲) به پیمانهٔ ۱۱ و رقم کنترل
//    که سرور در app/services/farakhan_validation.py اعمال می‌کند؛ اینجا فقط برای
//    بازخورد زندهٔ زیر فیلد است و سرور همچنان مرجع نهایی است.
//    (نکته: ارقام تکراری مثل ۱۱۱۱۱۱۱۱۱۱ از الگوریتم صاحب سامانه می‌گذرند ولی
//    ثبت‌نام واقعی نیستند — سرور و اینجا هر دو رد می‌کنند تا با هم‌راستا باشند.)
// 2) حداقل سن ثبت‌نام ۱۸ سال و 3) حداکثر ۸۰ سال — سن «تکمیل‌شده» از تاریخ تولد
//    شمسی؛ تبدیل شمسی/میلادی پورت همان الگوریتم app/core/dates.py سرور است تا
//    مرزهای نوروز و کبیسه‌ها دقیقاً مثل سرور حساب شود.

export const FARAKHAN_MIN_AGE = 18;
export const FARAKHAN_MAX_AGE = 80;

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** ارقام فارسی/عربی → لاتین (هم‌راستا با نرمال‌سازی سرور) */
export function normalizeFaDigits(value: string): string {
  return (value || "").replace(/[۰-۹٠-٩]/g, (d) => {
    const fa = FA_DIGITS.indexOf(d);
    if (fa >= 0) return String(fa);
    return String(AR_DIGITS.indexOf(d));
  });
}

/**
 * الگوریتم رسمی کد ملی (همان الگوریتم اعلامی صاحب سامانه):
 * - دقیقاً ۱۰ رقم (ارقام فارسی نرمال می‌شود)
 * - کدِ همهٔ ارقام یکسان (از جمله ۰۰۰۰۰۰۰۰۰۰) نامعتبر است
 * - s = Σ رقمِ i × (۱۰−i) برای ۹ رقم اول، به پیمانهٔ ۱۱؛ رقم کنترل c:
 *   s<2 → c==s وگرنه c==11−s
 */
export function isValidNationalCode(raw: string): boolean {
  const code = normalizeFaDigits(raw).trim();
  if (!/^\d{10}$/.test(code)) return false;
  if (code === code[0].repeat(10)) return false;
  let s = 0;
  for (let i = 0; i < 9; i++) s += Number(code[i]) * (10 - i);
  s %= 11;
  const c = Number(code[9]);
  return s < 2 ? c === s : c === 11 - s;
}

// ── تبدیل شمسی/میلادی (پورت دقیق app/core/dates.py سرور) ──

export function jalaliToGregorian(jy: number, jm: number, jd: number): Date {
  let days = -355668 + 365 * (jy + 1595) + Math.floor((jy + 1595) / 33) * 8
    + Math.floor((((jy + 1595) % 33) + 3) / 4) + jd;
  days += jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186;
  let gy = 400 * Math.floor(days / 146097);
  days %= 146097;
  if (days > 36524) {
    days -= 1;
    gy += 100 * Math.floor(days / 36524);
    days %= 36524;
    if (days >= 365) days += 1;
  }
  gy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    gy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  let gd = days + 1;
  const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
  const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  let gm = 0;
  for (let i = 0; i < 12; i++) {
    if (gd <= monthDays[i]) { gm = i + 1; break; }
    gd -= monthDays[i];
  }
  return new Date(gy, gm - 1, gd);
}

export function gregorianToJalali(gy: number, gm: number, gd: number): [number, number, number] {
  const d = new Date(gy, gm - 1, gd);
  let jy = gy - 621;
  const nowruzOf = (yy: number) => jalaliToGregorian(yy, 1, 1);
  let nowruz = nowruzOf(jy);
  if (d.getTime() < nowruz.getTime()) {
    jy -= 1;
    nowruz = nowruzOf(jy);
  }
  const delta = Math.floor((d.getTime() - nowruz.getTime()) / 86400000);
  let jm: number;
  let jd: number;
  if (delta < 186) {
    jm = Math.floor(delta / 31) + 1;
    jd = (delta % 31) + 1;
  } else {
    jm = Math.floor((delta - 186) / 30) + 7;
    jd = ((delta - 186) % 30) + 1;
  }
  return [jy, jm, jd];
}

/** سن تکمیل‌شده از تاریخ تولد شمسی «YYYY/MM/DD»؛ -۱ یعنی تاریخ نامعتبر */
export function completedAgeFromJalali(jalali: string): number {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec((jalali || "").trim());
  if (!m) return -1;
  const birth = jalaliToGregorian(Number(m[1]), Number(m[2]), Number(m[3]));
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday = today.getMonth() < birth.getMonth()
    || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

/**
 * کف/سقف تقویم تولد (شمسی) هم‌راستا با محدودهٔ سن سرور:
 * مبدأ میلادی است («امروز نابر N سال» میلادی، بعد تبدیل به شمسی) تا مرز
 * نوروز/کبیسه مثل محاسبهٔ سنِ سرور بماند. maxJalali = ۱۸ سالگی، minJalali = ۸۰ سالگی.
 */
export function birthDateCalendarBounds(minAge = FARAKHAN_MIN_AGE, maxAge = FARAKHAN_MAX_AGE): { minJalali: string; maxJalali: string } {
  const fmt = (d: Date) => {
    const [jy, jm, jd] = gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
    const two = (x: number) => String(x).padStart(2, "0");
    return `${String(jy).padStart(4, "0")}/${two(jm)}/${two(jd)}`;
  };
  const today = new Date();
  const minusYears = (n: number) => {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    d.setFullYear(d.getFullYear() - n);
    return d;
  };
  return { minJalali: fmt(minusYears(maxAge)), maxJalali: fmt(minusYears(minAge)) };
}
