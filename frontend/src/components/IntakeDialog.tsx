import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { finalizeIntake, fetchIntake, saveIntake } from "../api/siteops";
import type { ConsultationRow } from "../api/siteops";
import JalaliDateField from "./JalaliDateField";
import { formatJalaliDateTime } from "../utils/jalali";

type FieldType = "text" | "multiline" | "select" | "jalali" | "number";

interface IntakeField {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: string[];
  rows?: number;
}

interface IntakeSection {
  no: string;
  title: string;
  fields: IntakeField[];
}

const PSYCH_OPTIONS = ["طبیعی", "مشکل خفیف", "مشکل متوسط", "مشکل شدید"];

const SECTIONS: IntakeSection[] = [
  { no: "۱", title: "اطلاعات مراجع", fields: [
    { key: "identity_full_name", label: "نام و نام خانوادگی", type: "text", required: true },
    { key: "identity_gender", label: "جنسیت", type: "select", options: ["زن", "مرد"] },
    { key: "identity_birth_date", label: "تاریخ تولد", type: "jalali" },
    { key: "identity_marital", label: "وضعیت تأهل", type: "select", options: ["مجرد", "متأهل", "طلاق‌گرفته", "بیوه"] },
    { key: "identity_separation", label: "علت جدایی (در صورت طلاق)", type: "text" },
    { key: "identity_education", label: "تحصیلات", type: "select", options: ["زیر دیپلم", "دیپلم", "کاردانی", "کارشناسی", "کارشناسی ارشد", "دکتری", "سایر"] },
    { key: "identity_phone", label: "شماره تماس", type: "text" },
    { key: "identity_first_visit", label: "تاریخ اولین مراجعه", type: "jalali" },
    { key: "identity_address", label: "آدرس", type: "multiline", rows: 2 },
    { key: "identity_reason", label: "دلیل مراجعه به مشاوره", type: "multiline", rows: 2 },
  ]},
  { no: "۲", title: "اطلاعات اولیه", fields: [
    { key: "initial_problem_summary", label: "شرح مختصری از مشکل یا مسئله", type: "multiline", rows: 3, required: true },
    { key: "initial_duration", label: "مدت زمانی که با این مشکل درگیر هستید", type: "text" },
    { key: "initial_past_therapy", label: "سابقه روان‌درمانی (در صورت مصرف دارو ذکر کنید)", type: "multiline", rows: 2 },
    { key: "initial_medications", label: "مصرف دارو", type: "multiline", rows: 2 },
    { key: "initial_physical", label: "سابقه بیماری جسمی", type: "multiline", rows: 2 },
  ]},
  { no: "۳", title: "اطلاعات خانوادگی", fields: [
    { key: "family_siblings", label: "تعداد خواهران و برادران", type: "number" },
    { key: "family_relations", label: "نظرات درباره ارتباط اعضای خانواده با یکدیگر و نوع روابط خانوادگی", type: "multiline", rows: 3 },
  ]},
  { no: "۴", title: "اطلاعات اجتماعی", fields: [
    { key: "social_relations", label: "کیفیت روابط اجتماعی (رابطه با همکاران، دوستان و...)", type: "multiline", rows: 2 },
    { key: "social_support", label: "میزان حمایت اجتماعی (خانواده، دوستان)", type: "select", options: ["کم", "متوسط", "زیاد"] },
    { key: "social_interests", label: "علاقه‌ها و سرگرمی‌ها", type: "multiline", rows: 2 },
  ]},
  { no: "۵", title: "ارزیابی روان‌شناختی", fields: [
    { key: "psych_emotion", label: "وضعیت عاطفه و احساس در طول زمان", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_anxiety", label: "وضعیت اضطراب", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_sleep", label: "وضعیت خواب", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_appetite", label: "وضعیت اشتها", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_concentration", label: "وضعیت تمرکز و توجه", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_memory", label: "وضعیت حافظه", type: "select", options: PSYCH_OPTIONS },
    { key: "psych_thinking", label: "وضعیت تفکر و ادراک", type: "select", options: PSYCH_OPTIONS },
  ]},
  { no: "۶", title: "برنامه‌ریزی درمان", fields: [
    { key: "planning_goals", label: "اهداف مشاوره", type: "multiline", rows: 3, required: true },
    { key: "planning_sessions", label: "تعداد جلسات مورد نیاز", type: "number" },
    { key: "planning_approach", label: "نوع رویکرد درمانی", type: "text" },
    { key: "planning_homework", label: "تکالیف بین جلسات", type: "multiline", rows: 2 },
  ]},
  { no: "۷", title: "نکات مهم و تأییدیه", fields: [
    { key: "important_notes", label: "نکات مهم", type: "multiline", rows: 3 },
    { key: "confirmation_counselor", label: "نام و امضای مشاور", type: "text" },
    { key: "confirmation_client", label: "نام و امضای مراجع", type: "text" },
    { key: "confirmation_date", label: "تاریخ", type: "jalali" },
  ]},
];

const REQUIRED_FIELDS: [string, string][] = [
  ["identity_full_name", "نام و نام خانوادگی"],
  ["initial_problem_summary", "شرح مشکل"],
  ["planning_goals", "اهداف مشاوره"],
];

export default function IntakeDialog({ row, onClose, onError }: {
  row: ConsultationRow | null;
  onClose: () => void;
  onError: (m: string) => void;
}) {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canWrite = roles.some((r) => ["ORG_MANAGER", "RECEPTION", "COUNSELOR"].includes(r));

  const [data, setData] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<string | null>(null);
  const [meta, setMeta] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (row) {
      setLoading(true); setFormError(null); setMessage(null);
      fetchIntake(row.id)
        .then((res) => {
          setData((res.data ?? {}) as Record<string, string>);
          setStatus(res.exists ? res.status : null);
          setMeta(res.updated_at ? `آخرین تغییر: ${formatJalaliDateTime(res.updated_at)}${res.filled_by_name ? " — " + res.filled_by_name : ""}` : "پرسشنامه‌ای ثبت نشده");
        })
        .catch((e) => setFormError(errDetail(e)))
        .finally(() => setLoading(false));
    }
  }, [row]);

  const set = (k: string) => (e: { target: { value: string } }) =>
    setData((p) => ({ ...p, [k]: e.target.value }));

  const editable = status !== "final" && canWrite;

  const renderField = (f: IntakeField) => {
    const label = f.label + (f.required ? " *" : "");
    if (f.type === "jalali") {
      return (
        <JalaliDateField
          key={f.key}
          label={label}
          value={data[f.key] ?? ""}
          onChange={(iso) => setData((p) => ({ ...p, [f.key]: iso ?? "" }))}
        />
      );
    }
    if (f.type === "select") {
      return (
        <TextField key={f.key} select label={label} value={data[f.key] ?? ""}
          onChange={set(f.key)} disabled={!editable} fullWidth>
          <MenuItem value="">—</MenuItem>
          {f.options!.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
        </TextField>
      );
    }
    if (f.type === "number") {
      return (
        <TextField key={f.key} type="number" label={label} value={data[f.key] ?? ""}
          onChange={set(f.key)} disabled={!editable} fullWidth />
      );
    }
    const isLong = f.type === "multiline";
    return (
      <TextField
        key={f.key}
        label={label}
        value={data[f.key] ?? ""}
        onChange={set(f.key)}
        multiline={isLong}
        minRows={f.rows ?? 1}
        disabled={!editable}
        fullWidth
        sx={isLong ? { gridColumn: { sm: "1 / -1" } } : undefined}
      />
    );
  };

  const submit = async (e: FormEvent, final: boolean) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
    if (final) {
      const missing = REQUIRED_FIELDS.filter(([k]) => !(data[k] ?? "").trim()).map(([, l]) => l);
      if (missing.length > 0) {
        setFormError("برای نهایی‌سازی، فیلدهای الزامی را تکمیل کنید: " + missing.join("، "));
        return;
      }
    }
    setBusy(true);
    try {
      await saveIntake(row.id, data);
      if (final) {
        await finalizeIntake(row.id);
        setMessage("پرسشنامه نهایی شد و بی‌ردپا تغییر نمی‌کند.");
        setStatus("final");
      } else {
        setMessage("پرسشنامه ذخیره شد (پیش‌نویس).");
      }
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="lg" fullWidth>
      <form onSubmit={(e) => submit(e, false)}>
        <DialogTitle>
          پرسشنامه پذیرش مراجع — {row?.full_name ?? ""}
          {status && (
            <Chip size="small" sx={{ mr: 1 }} color={status === "final" ? "success" : "warning"}
              label={status === "final" ? "نهایی" : "پیش‌نویس"} />
          )}
          {!canWrite && status !== "final" && (
            <Chip size="small" sx={{ mr: 1 }} label="فقط مشاهده" />
          )}
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="caption" color="text.secondary">{meta}</Typography>
          {loading && <CircularProgress size={24} sx={{ mx: "auto", display: "block", my: 2 }} />}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {message && <Alert severity="success" sx={{ mt: 2 }}>{message}</Alert>}
          {row && !loading && (
            <Stack spacing={2.5} mt={2}>
              {SECTIONS.map((sec) => (
                <Paper key={sec.no} variant="outlined"
                  sx={{ p: 2.5, borderInlineStartWidth: 4, borderColor: "primary.main" }}>
                  <Stack direction="row" alignItems="center" spacing={1} mb={2}>
                    <Box sx={{
                      width: 28, height: 28, borderRadius: "50%", bgcolor: "primary.main",
                      color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 14, fontWeight: 700,
                    }}>
                      {sec.no}
                    </Box>
                    <Typography variant="subtitle1" fontWeight={700} color="primary.main">
                      {sec.title}
                    </Typography>
                  </Stack>
                  <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={2}>
                    {sec.fields.map(renderField)}
                  </Box>
                </Paper>
              ))}
              {status === "final" && (
                <Alert severity="info">
                  این پرسشنامه نهایی شده است. طبق سند، فرم نهایی بی‌ردپا تغییر نمی‌کند.
                </Alert>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          {row && editable && !message && (
            <>
              <Button onClick={(e) => submit(e as unknown as FormEvent, false)} disabled={busy}>
                ذخیره پیش‌نویس
              </Button>
              <Button variant="contained" onClick={(e) => submit(e as unknown as FormEvent, true)} disabled={busy}>
                نهایی‌سازی
              </Button>
            </>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}