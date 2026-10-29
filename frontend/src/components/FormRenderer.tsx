import { useMemo, useState } from "react";
import {
  Alert, Box, Checkbox, Chip, Divider, FormControl, FormControlLabel, FormLabel,
  MenuItem, Paper, Radio, RadioGroup, Rating, Stack, TextField, Typography,
} from "@mui/material";
import JalaliDateField from "./JalaliDateField";
import { FORM_FIELD_TYPE_LABELS, type FormFieldDef, type FormTemplate } from "../api/forms";

/**
 * فاز ۶۱ - رندرکنندهٔ فرم بر پایهٔ تعریف JSON (فرم‌ساز مدیر).
 * دو حالت: تکمیل (onChange مقادیر) و فقط‌خواندنی (مشاهدهٔ پاسخ).
 * مقدار هر فیلد در values[field.id] نگهداری می‌شود؛ اعتبارسنجی اجباری‌ها
 * هم سمت سرور و هم اینجا (پیش از ارسال) انجام می‌شود.
 */

export type FormValues = Record<string, unknown>;

export function validateFormValues(fields: FormFieldDef[], values: FormValues): string | null {
  for (const f of fields) {
    if (f.type === "heading") continue;
    const v = values[f.id];
    const empty =
      v === undefined ||
      v === null ||
      (typeof v === "string" && !v.trim()) ||
      (Array.isArray(v) && v.length === 0);
    if (f.required && empty) return `تکمیل «${f.label}» الزامی است`;
  }
  return null;
}

function FieldControl({
  field, value, onChange, disabled,
}: {
  field: FormFieldDef;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any;
  onChange: (v: unknown) => void;
  disabled?: boolean;
}) {
  switch (field.type) {
    case "text":
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label + (field.required ? " *" : "")}
          helperText={field.help}
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "textarea":
      return (
        <TextField
          fullWidth
          size="small"
          multiline
          minRows={3}
          label={field.label + (field.required ? " *" : "")}
          helperText={field.help}
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "number":
      return (
        <TextField
          fullWidth
          size="small"
          type="number"
          label={field.label + (field.required ? " *" : "")}
          helperText={field.help}
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        />
      );
    case "date":
      return (
        <Box>
          <JalaliDateField
            label={field.label}
            required={field.required}
            value={value ?? ""}
            onChange={(iso) => onChange(iso ?? "")}
          />
          {field.help ? (
            <Typography variant="caption" color="text.secondary">{field.help}</Typography>
          ) : null}
        </Box>
      );
    case "select":
      return (
        <TextField
          fullWidth
          select
          size="small"
          label={field.label + (field.required ? " *" : "")}
          helperText={field.help}
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        >
          <MenuItem value=""><em>— انتخاب کنید —</em></MenuItem>
          {(field.options ?? []).map((o) => (
            <MenuItem key={o} value={o}>{o}</MenuItem>
          ))}
        </TextField>
      );
    case "radio":
      return (
        <FormControl disabled={disabled} sx={{ display: "block" }}>
          <FormLabel sx={{ fontSize: 13, color: "text.primary" }}>
            {field.label}{field.required ? " *" : ""}
          </FormLabel>
          <RadioGroup
            row
            value={value ?? ""}
            onChange={(e) => onChange(e.target.value)}
          >
            {(field.options ?? []).map((o) => (
              <FormControlLabel key={o} value={o} control={<Radio size="small" />} label={o} />
            ))}
          </RadioGroup>
          {field.help ? <Typography variant="caption" color="text.secondary">{field.help}</Typography> : null}
        </FormControl>
      );
    case "checkbox":
      return (
        <FormControl disabled={disabled} sx={{ display: "block" }}>
          <FormLabel sx={{ fontSize: 13, color: "text.primary" }}>
            {field.label}{field.required ? " *" : ""}
          </FormLabel>
          <Stack direction="row" flexWrap="wrap" sx={{ rowGap: 0, columnGap: 1 }}>
            {(field.options ?? []).map((o) => {
              const arr: string[] = Array.isArray(value) ? value.map(String) : [];
              const checked = arr.includes(o);
              return (
                <FormControlLabel
                  key={o}
                  control={
                    <Checkbox
                      size="small"
                      checked={checked}
                      onChange={() => onChange(checked ? arr.filter((x) => x !== o) : [...arr, o])}
                    />
                  }
                  label={o}
                />
              );
            })}
          </Stack>
          {field.help ? <Typography variant="caption" color="text.secondary">{field.help}</Typography> : null}
        </FormControl>
      );
    case "rating":
      return (
        <Box>
          <Typography component="div" sx={{ fontSize: 13, mb: 0.5 }}>
            {field.label}{field.required ? " *" : ""}
          </Typography>
          <Rating
            value={typeof value === "number" ? value : null}
            onChange={(_, v) => onChange(v ?? "")}
            disabled={disabled}
          />
          {field.help ? (
            <Typography variant="caption" color="text.secondary" component="div">{field.help}</Typography>
          ) : null}
        </Box>
      );
    case "yesno":
      return (
        <FormControl disabled={disabled} sx={{ display: "block" }}>
          <FormLabel sx={{ fontSize: 13, color: "text.primary" }}>
            {field.label}{field.required ? " *" : ""}
          </FormLabel>
          <RadioGroup row value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
            <FormControlLabel value="بله" control={<Radio size="small" />} label="بله" />
            <FormControlLabel value="خیر" control={<Radio size="small" />} label="خیر" />
          </RadioGroup>
        </FormControl>
      );
    default:
      return null;
  }
}

export default function FormRenderer({
  template, values, onChange, readOnly = false,
}: {
  template: Pick<FormTemplate, "title" | "description" | "fields">;
  values: FormValues;
  onChange?: (fieldId: string, v: unknown) => void;
  readOnly?: boolean;
}) {
  const fields = template.fields ?? [];

  if (readOnly) {
    return (
      <Stack spacing={1.25}>
        {fields.map((f) => {
          if (f.type === "heading") {
            return (
              <Divider key={f.id} textAlign="right" sx={{ mt: 1 }}>
                <Chip size="small" label={f.label} color="primary" variant="outlined" />
              </Divider>
            );
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const v = (values as any)[f.id];
          let txt = "";
          if (f.type === "rating") txt = v ? `${v} از ۵` : "—";
          else if (Array.isArray(v)) txt = v.length ? v.join("، ") : "—";
          else if (f.type === "yesno") txt = v === "بله" ? "بله" : v === "خیر" ? "خیر" : "—";
          else txt = v !== undefined && v !== null && String(v).trim() !== "" ? String(v) : "—";
          return (
            <Stack key={f.id} direction="row" spacing={1} alignItems="baseline">
              <Typography sx={{ minWidth: 180, color: "text.secondary", fontSize: 13 }}>
                {f.label}:
              </Typography>
              <Typography sx={{ fontWeight: 500, fontSize: 14, whiteSpace: "pre-wrap" }}>{txt}</Typography>
            </Stack>
          );
        })}
        {fields.filter((f) => f.type !== "heading").length === 0 ? (
          <Typography color="text.secondary">این فرم فیلدی ندارد.</Typography>
        ) : null}
      </Stack>
    );
  }

  return (
    <Stack spacing={2}>
      {fields.map((f) =>
        f.type === "heading" ? (
          <Divider key={f.id} textAlign="right" sx={{ mt: 1 }}>
            <Chip size="small" label={f.label} color="primary" variant="outlined" />
          </Divider>
        ) : (
          <FieldControl
            key={f.id}
            field={f}
            value={(values as Record<string, unknown>)[f.id]}
            onChange={(v) => onChange?.(f.id, v)}
          />
        ),
      )}
    </Stack>
  );
}

/** پیش‌نمایش فرم در فرم‌ساز — مقادیر آزمایشی و خطای اجباری‌ها را نشان می‌دهد */
export function FormPreview({ template }: { template: Pick<FormTemplate, "title" | "description" | "fields"> }) {
  const [values, setValues] = useState<FormValues>({});
  const fields = template.fields ?? [];
  const missing = useMemo(
    () => fields.filter((f) => f.type !== "heading" && f.required).length,
    [fields],
  );
  return (
    <Stack spacing={2}>
      <Alert severity="info" variant="outlined">
        پیش‌نمایش فرم — {missing} فیلد اجباری دارد. مقادیر ذخیره نمی‌شوند.
      </Alert>
      <FormRenderer template={template} values={values} onChange={(id, v) => setValues((s) => ({ ...s, [id]: v }))} />
    </Stack>
  );
}

export { FORM_FIELD_TYPE_LABELS };

/** خروجی CSV پاسخ‌ها (UTF-8 BOM برای اکسل فارسی) */
export function responsesToCsv(
  fields: FormFieldDef[],
  rows: { respondent_name: string | null; submitted_at: string | null; answers: Record<string, unknown> }[],
): string {
  const esc = (s: unknown) => `"${String(s ?? "").replace(/"/g, '""')}"`;
  const head = ["پاسخ‌دهنده", "زمان ثبت", ...fields.filter((f) => f.type !== "heading").map((f) => f.label)];
  const lines = [head.map(esc).join(",")];
  for (const r of rows) {
    const cells = fields
      .filter((f) => f.type !== "heading")
      .map((f) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const v = (r.answers as any)[f.id];
        if (Array.isArray(v)) return v.join(" | ");
        if (f.type === "rating") return v ? `${v} از ۵` : "";
        return v ?? "";
      });
    lines.push([esc(r.respondent_name ?? ""), esc(r.submitted_at ?? ""), ...cells.map(esc)].join(","));
  }
  return "\uFEFF" + lines.join("\r\n");
}

export function fieldTypeName(t: string): string {
  return (FORM_FIELD_TYPE_LABELS as Record<string, string>)[t] ?? t;
}

export function FormFieldChip({ type }: { type: string }) {
  return <Chip size="small" label={fieldTypeName(type)} variant="outlined" />;
}

export function EmptyFieldsHint() {
  return (
    <Paper variant="outlined" sx={{ p: 2, textAlign: "center", bgcolor: "#fafafa" }}>
      <Typography variant="body2" color="text.secondary">
        هنوز فیلدی اضافه نشده — از «افزودن فیلد» یک نوع انتخاب کنید.
      </Typography>
    </Paper>
  );
}
