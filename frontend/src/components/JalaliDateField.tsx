import { Box, Typography } from "@mui/material";
import DatePicker from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";

interface JalaliShape {
  year: number;
  monthNumber: number;
  day: number;
}

export function jalaliToIso(d: JalaliShape | null | undefined): string | undefined {
  if (!d || typeof d.year !== "number") return undefined;
  return new Date(Date.UTC(d.year, d.monthNumber - 1, d.day)).toISOString().slice(0, 10);
}

export default function JalaliDateField({
  label, value, onChange, required = false,
}: {
  label: string;
  value: unknown;
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
        inputClass="rdp-input"
      />
    </Box>
  );
}
