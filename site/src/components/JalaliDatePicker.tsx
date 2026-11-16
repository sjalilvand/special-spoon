// فاز ۹۱ — تقویم شمسی برای فراخوان همکاری (تاریخ تولد)
//
// خواستهٔ صاحب سامانه: تاریخ تولد باید «شمسی، با تقویم، بدون تایپ مستقیم» باشد —
// کاربر فقط از تقویم انتخاب می‌کند و ورودی متن قابل تایپ نیست (readOnly) تا قالب
// و اعتبار تاریخ تضمین شود. خروجی onChange رشتهٔ شمسی «YYYY/MM/DD» با ارقام لاتین
// است (همان قالبی که سرور فراخوان می‌پذیرد) و نمایش در ورودی با ارقام فارسی.
// تقویم همان کتابخانهٔ پنل است (react-multi-date-picker + تقویم persian) تا رفتار
// یکسان باشد؛ مالکیت تاریخ آینده/بیش از ۱۲۵۰ بسته است (هم‌راستا با اعتبارسنجی سرور).
import {
  Box, IconButton, InputAdornment, Paper, Popover, TextField, Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import { Calendar } from "react-multi-date-picker";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import persian from "react-date-object/calendars/persian";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import persian_fa from "react-date-object/locales/persian_fa";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import DateObject from "react-date-object";

/** آیکون تقویم — SVG داخلی (سایت وابسته به @mui/icons-material ندارد) */
function CalendarIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 20, height: 20, display: "block" }} aria-hidden>
      <path
        d="M7 2v2H5a2 2 0 00-2 2v13a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-2V2h-2v2H9V2H7zm-2 7h14v10H5V9zm2 2v2h2v-2H7zm4 0v2h2v-2h-2zm4 0v2h2v-2h-2zm-8 4v2h2v-2H7zm4 0v2h2v-2h-2z"
        fill="currentColor"
      />
    </Box>
  );
}

/** آیکون پاک‌کردن — SVG داخلی */
function ClearIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 18, height: 18, display: "block" }} aria-hidden>
      <path
        d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"
        fill="currentColor"
      />
    </Box>
  );
}

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** «1370/01/01» لاتین → نمایش فارسی «۱۳۷۰/۰۱/۰۱» */
function toFaDisplay(value: string): string {
  return value.replace(/\d/g, (d) => FA_DIGITS[Number(d)]);
}

/** رشتهٔ شمسی → DateObject تقویم شمسی (برای مقدار اولیهٔ تقویم) */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function jalaliStringToDateObject(value: string): any {
  try {
    const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(value.trim());
    if (!m) return undefined;
    return new DateObject({
      calendar: persian, locale: persian_fa,
      year: Number(m[1]), month: Number(m[2]), day: Number(m[3]),
    });
  } catch {
    return undefined;
  }
}

export default function JalaliDatePicker({
  label, value, onChange, required, error, helperText, disabled,
}: {
  label: string;
  /** رشتهٔ شمسی با ارقام لاتین «1370/01/01»؛ خالی = انتخاب نشده */
  value: string;
  onChange: (jalali: string) => void;
  required?: boolean;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const open = Boolean(anchor) && !disabled;

  // سقف انتخاب: امروز (شمسی) — تاریخ آیندهٔ تولد بی‌معناست؛ کف: ۱۲۵۰ مثل سرور
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const todayObj = useMemo(() => new DateObject({ calendar: persian, locale: persian_fa }), []);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const minDateObj = useMemo(
    () => new DateObject({ calendar: persian, locale: persian_fa, year: 1250, month: 1, day: 1 }),
    [],
  );
  const calendarValue = useMemo(() => jalaliStringToDateObject(value), [value]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pick = (d: any) => {
    if (!d) {
      onChange("");
      return;
    }
    const y = String(d.year).padStart(4, "0");
    const m = String(d.month).padStart(2, "0");
    const day = String(d.day).padStart(2, "0");
    onChange(`${y}/${m}/${day}`);
    setAnchor(null);
  };

  return (
    <>
      <TextField
        fullWidth
        size="small"
        label={label}
        required={required}
        value={value ? toFaDisplay(value) : ""}
        placeholder="از تقویم انتخاب کنید"
        error={error}
        helperText={helperText ?? "انتخاب از تقویم شمسی — تایپ مستقیم غیرفعال است"}
        onClick={(e) => !disabled && setAnchor(e.currentTarget)}
        /* خواستهٔ صاحب سامانه: از واردکردن مستقیم تاریخ جلوگیری شود */
        inputProps={{
          readOnly: true,
          dir: "ltr",
          inputMode: "none" as never,
          onKeyDown: (e: React.KeyboardEvent) => e.preventDefault(),
        }}
        InputProps={{
          style: { cursor: disabled ? "default" : "pointer" },
          endAdornment: (
            <InputAdornment position="end">
              {value && !disabled && (
                <IconButton
                  size="small" edge="end" aria-label={`پاک‌کردن ${label}`}
                  onClick={(e) => { e.stopPropagation(); onChange(""); }}
                  onMouseDown={(e) => e.stopPropagation()}
                >
                  <ClearIcon />
                </IconButton>
              )}
              <IconButton
                size="small" edge={value && !disabled ? false : "end"} aria-label={`بازکردن تقویم ${label}`}
                onClick={(e) => { e.stopPropagation(); if (!disabled) setAnchor(e.currentTarget); }}
                onMouseDown={(e) => e.stopPropagation()}
                disabled={disabled}
              >
                <CalendarIcon />
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      <Popover
        open={open}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { elevation: 4, sx: { mt: 0.5 } } }}
      >
        <Paper elevation={0}>
          <Calendar
            value={calendarValue}
            calendar={persian}
            locale={persian_fa}
            onChange={pick}
            minDate={minDateObj}
            maxDate={todayObj}
          />
          <Box sx={{ px: 2, pb: 1.5 }}>
            <Typography variant="caption" color="text.secondary">
              تولد نمی‌تواند در آینده باشد — بازهٔ مجاز: ۱۲۵۰ تا امروز
            </Typography>
          </Box>
        </Paper>
      </Popover>
    </>
  );
}
