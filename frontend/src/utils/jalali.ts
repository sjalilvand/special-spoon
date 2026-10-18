// فاز ۲۶ - UI سند ۰۸: تاریخ شمسی سراسری
// تبدیل و نمایش تاریخ میلادی ISO به تقویم شمسی با ارقام فارسی

const jDateFmt = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric", month: "2-digit", day: "2-digit",
});

const jDateTimeFmt = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit",
});

function tryFormat(fmt: Intl.DateTimeFormat, d: Date): string {
  try {
    return fmt.format(d);
  } catch {
    return "—";
  }
}

/** «2024-08-02» یا «2024-08-02T09:30:00» → «۱۴۰۳/۰۵/۱۲» */
export function formatJalali(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  if (isNaN(d.getTime())) return iso;
  return tryFormat(jDateFmt, d);
}

/** تاریخ+ساعت به شمسی — ساعت با آفست محلی مرورگر نمایش داده می‌شود */
export function formatJalaliDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return tryFormat(jDateTimeFmt, d);
}

/** برچسب کوتاه شمسی (ماه/روز) برای نمودارها */
export function jalaliShort(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  if (isNaN(d.getTime())) return iso ?? "—";
  try {
    return new Intl.DateTimeFormat("fa-IR-u-ca-persian", { month: "short", day: "numeric" }).format(d);
  } catch {
    return iso;
  }
}
