import { Box, Typography } from "@mui/material";
import DatePicker from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";

interface JalaliShape {
  year: number;
  monthNumber: number;
  day: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function safeJalaliToIso(d: any): string | undefined {
  if (!d || typeof d !== "object") return undefined;
  try {
    const y = Number(d.year);
    const m = Number(d.monthNumber ?? d.month?.number);
    const day = Number(d.day);
    if (!y || !m || !day || m < 1 || m > 12 || day < 1 || day > 31) return undefined;
    const dt = new Date(Date.UTC(y, m - 1, day));
    if (isNaN(dt.getTime())) return undefined;
    return dt.toISOString().slice(0, 10);
  } catch {
    return undefined;
  }
}

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
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
        {required ? " *" : ""}
      </Typography>
      <DatePicker
        value={value}
        onChange={(d) => onChange(jalaliToIso(d as unknown as JalaliShape | null))}
        calendar={persian}
        locale={persian_fa}
        containerStyle={{ width: "100%" }}
        placeholder="انتخاب تاریخ (کلیک = تقویم شمسی)"
        inputClass="rdp-input"
      />
    </Box>
  );
}
