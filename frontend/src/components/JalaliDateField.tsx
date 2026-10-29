import { useMemo, useState } from "react";
import { Box, Popover, TextField, Typography } from "@mui/material";
import { Calendar } from "react-multi-date-picker";
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
 *
 * فاز ۶۲ — رفع بریده‌شدن تقویم در دیالوگ‌ها:
 * پنل تقویم به‌جای رندر مطلق داخل ظرف فیلد (که توسط overflow دیالوگ بریده
 * می‌شد) داخل MUI Popover با Portal به body رندر می‌شود؛ نتیجه: تقویم کامل
 * (سرصفحهٔ سال + ناوبری ماه) همیشه دیده می‌شود و با لبهٔ دیالوگ برخورد نمی‌کند.
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

/** ISO میلادی → DateObject شمسی برای نمایش درست در تقویم */
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

/** ISO میلادی → متن نمایشی شمسی («۱۴۰۵/۰۸/۰۷») برای خودِ فیلد */
function jalaliDisplayText(iso: string | undefined | null): string {
  if (!iso) return "";
  const j = isoToJalaliObject(iso);
  if (!j || typeof j === "string") return "";
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (j as any).format("YYYY/MM/DD") ?? "";
  } catch {
    return "";
  }
}

// فاز ۴۹: فیلد تاریخ تمام‌عرض با minWidth صفر — در گرید/فرم باریک دیگر
// از کادر بیرون نمی‌زند (رفع سرریز تاریخ انقضا در مدارک مشاور و ...)
// فاز ۵۹: تبدیل درست میلادی↔شمسی + نمایش placeholder شمسی
// فاز ۶۲: تقویم در Popover پرتال‌شده — هیچ‌گاه در دیالوگ بریده نمی‌شود
export default function JalaliDateField({
  label, value, onChange, required = false,
}: {
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any;
  onChange: (iso: string | undefined) => void;
  required?: boolean;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const display = useMemo(() => jalaliDisplayText(typeof value === "string" ? value : undefined), [value]);

  return (
    <Box sx={{ width: "100%", minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" component="div">
        {label}
        {required ? " *" : ""}
      </Typography>
      <TextField
        fullWidth
        size="small"
        value={display}
        placeholder="انتخاب تاریخ (تقویم شمسی)"
        onClick={(e) => setAnchor(e.currentTarget)}
        onFocus={(e) => setAnchor(e.currentTarget)}
        sx={{
          "& .MuiInputBase-input": { cursor: "pointer" },
          // هم‌عرض با بقیهٔ فرم — بدون سرریز در گرید باریک
          minWidth: 0,
        }}
        inputProps={{ readOnly: true, "aria-label": label }}
      />
      <Popover
        open={!!anchor}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { elevation: 8, sx: { mt: 0.5, borderRadius: 2 } } }}
        // بالای دیالوگ‌ها (z-index پیش‌فرض دیالوگ = 1300)
        sx={{ zIndex: 1500 }}
      >
        <Box sx={{ direction: "rtl", "& .rmdp-wrapper": { width: "100%" } }}>
          <Calendar
            value={isoToJalaliObject(value) || undefined}
            onChange={(d) => {
              onChange(safeJalaliToIso(d));
              setAnchor(null);
            }}
            calendar={persian}
            locale={persian_fa}
          />
        </Box>
      </Popover>
    </Box>
  );
}
