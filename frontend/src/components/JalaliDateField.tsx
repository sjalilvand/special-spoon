import { Box, Typography } from "@mui/material";
import DatePicker from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import DateObject from "react-date-object";

/**
 * فاز ۵۹ — رفع باگ تبدیل دوطرفهٔ تاریخ:
 * ۱) value ورودی ISO میلادی («2026-10-29») بود ولی DatePicker با calendar=persian
 *    رشتهٔ خام را «شمسی» تفسیر می‌کرد → نمایش ~۶۲۰ سال جلوتر. حالا رشتهٔ ISO
 *    به Date میلادی تبدیل و سپس به تقویم شمسی نگاشت می‌شود.
 * ۲) safeJalaliToIso اعداد شمسی (مثل ۱۴۰۵/۰۸/۰۷) را عیناً به‌عنوان ISO میلادی
 *    ذخیره می‌کرد → تاریخ‌های ~۵۷۸ سال در آینده در پایگاه‌داده. حالا DateObject
 *    شمسی با toDate() به تاریخ میلادی واقعی تبدیل می‌شود.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function safeJalaliToIso(d: any): string | undefined {
  if (!d) return undefined;
  try {
    // خروجی onChange در react-multi-date-picker یک DateObject (تقویم شمسی) است؛
    // toDate() تاریخ میلادی واقعیِ زیرین را برمی‌گرداند.
    if (typeof d === "object" && typeof d.toDate === "function") {
      const g = d.toDate() as Date;
      if (isNaN(g.getTime())) return undefined;
      return g.toISOString().slice(0, 10);
    }
    // دفاعی: Date خام یا رشتهٔ ISO میلادی
    const g = d instanceof Date ? d : new Date(String(d));
    if (isNaN(g.getTime())) return undefined;
    return g.toISOString().slice(0, 10);
  } catch {
    return undefined;
  }
}

/** ISO میلادی → DateObject شمسی برای نمایش درست در DatePicker */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isoToJalaliObject(iso: any) {
  if (!iso) return "";
  try {
    if (typeof iso === "object" && typeof iso.toDate === "function") return iso;
    const g = iso instanceof Date ? iso : new Date(`${String(iso).slice(0, 10)}T00:00:00`);
    if (isNaN(g.getTime())) return "";
    return new DateObject({ date: g, calendar: persian, locale: persian_fa });
  } catch {
    return "";
  }
}

// فاز ۴۹: فیلد تاریخ تمام‌عرض با minWidth صفر — در گرید/فرم باریک دیگر
// از کادر بیرون نمی‌زند (رفع سرریز تاریخ انقضا در مدارک مشاور و ...)
// فاز ۵۹: تبدیل درست میلادی↔شمسی + نمایش placeholder شمسی
export default function JalaliDateField({
  label, value, onChange, required = false,
}: {
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any;
  onChange: (iso: string | undefined) => void;
  required?: boolean;
}) {
  return (
    <Box sx={{ width: "100%", minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" component="div">
        {label}
        {required ? " *" : ""}
      </Typography>
      <DatePicker
        value={isoToJalaliObject(value)}
        onChange={(d) => onChange(safeJalaliToIso(d))}
        calendar={persian}
        locale={persian_fa}
        containerStyle={{ width: "100%", maxWidth: "100%", minWidth: 0 }}
        style={{ width: "100%", maxWidth: "100%", boxSizing: "border-box" }}
        placeholder="انتخاب تاریخ (تقویم شمسی)"
        inputClass="rdp-input"
      />
    </Box>
  );
}
