import {
  Alert, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { finalizeIntake, fetchIntake, saveIntake } from "../api/siteops";
import type { ConsultationRow } from "../api/siteops";

const SECTIONS: { title: string; fields: [string, string, boolean?][] }[] = [
  { title: "اطلاعات مراجع", fields: [
    ["identity_full_name", "نام و نام خانوادگی", true],
    ["identity_birth_date", "تاریخ تولد (۱۳۷۰/۰۳/۲۱)"],
    ["identity_education", "تحصیلات"],
    ["identity_gender", "جنسیت"],
    ["identity_marital", "وضعیت تأهل"],
    ["identity_separation", "علت جدایی (در صورت طلاق)"],
    ["identity_address", "آدرس"],
    ["identity_phone", "شماره تماس"],
    ["identity_first_visit", "تاریخ اولین مراجعه"],
    ["identity_reason", "دلیل مراجعه به مشاوره"],
  ]},
  { title: "اطلاعات اولیه", fields: [
    ["initial_problem_summary", "شرح مختصری از مشکل یا مسئله", true],
    ["initial_duration", "مدت زمانی که با این مشکل درگیر هستید"],
    ["initial_past_therapy", "سابقه روان‌درمانی (در صورت مصرف دارو ذکر کنید)"],
    ["initial_medications", "مصرف دارو"],
    ["initial_physical", "سابقه بیماری جسمی"],
  ]},
  { title: "اطلاعات خانوادگی", fields: [
    ["family_relations", "نظرات درباره ارتباط اعضای خانواده با یکدیگر و نوع روابط خانوادگی"],
    ["family_siblings", "تعداد خواهران و برادران"],
  ]},
  { title: "اطلاعات اجتماعی", fields: [
    ["social_relations", "کیفیت روابط اجتماعی (رابطه با همکاران، دوستان و...)"],
    ["social_support", "میزان حمایت اجتماعی (خانواده، دوستان)"],
    ["social_interests", "علاقه‌ها و سرگرمی‌ها"],
  ]},
  { title: "ارزیابی روان‌شناختی", fields: [
    ["psych_emotion", "وضعیت عاطفه و احساس شما در طول زمان"],
    ["psych_anxiety", "وضعیت اضطراب (چه چیزی شما را نگران می‌کند)"],
    ["psych_sleep", "وضعیت خواب"],
    ["psych_appetite", "وضعیت اشتها"],
    ["psych_concentration", "وضعیت تمرکز و توجه"],
    ["psych_memory", "وضعیت حافظه"],
    ["psych_thinking", "وضعیت تفکر و ادراک"],
  ]},
  { title: "برنامه‌ریزی", fields: [
    ["planning_goals", "اهداف مشاوره", true],
    ["planning_sessions", "تعداد جلسات مورد نیاز"],
    ["planning_approach", "نوع رویکرد درمانی"],
    ["planning_homework", "تکالیف بین جلسات"],
  ]},
  { title: "نکات مهم و تأییدیه", fields: [
    ["important_notes", "نکات مهم"],
    ["confirmation_counselor", "نام و امضای مشاور"],
    ["confirmation_client", "نام و امضای مراجع"],
    ["confirmation_date", "تاریخ"],
  ]},
];

export default function IntakeDialog({ row, onClose, onError }: {
  row: ConsultationRow | null;
  onClose: () => void;
  onError: (m: string) => void;
}) {
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
          setMeta(res.updated_at ? `آخرین تغییر: ${new Date(res.updated_at).toLocaleString("fa-IR")}${res.filled_by_name ? " — " + res.filled_by_name : ""}` : "پرسشنامه‌ای ثبت نشده");
        })
        .catch((e) => setFormError(errDetail(e)))
        .finally(() => setLoading(false));
    }
  }, [row]);

  const set = (k: string) => (e: { target: { value: string } }) => setData((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent, final: boolean) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
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

  const editable = status !== "final";

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="md" fullWidth>
      <form onSubmit={(e) => submit(e, false)}>
        <DialogTitle>
          پرسشنامه پذیرش مراجع — {row?.full_name ?? ""}
          {status && (
            <Chip size="small" sx={{ mr: 1 }} color={status === "final" ? "success" : "warning"}
              label={status === "final" ? "نهایی" : "پیش‌نویس"} />
          )}
        </DialogTitle>
        <DialogContent>
          <Typography variant="caption" color="text.secondary">{meta}</Typography>
          {loading && <CircularProgress size={24} sx={{ mx: "auto", display: "block", my: 2 }} />}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {message && <Alert severity="success" sx={{ mt: 2 }}>{message}</Alert>}
          {row && !loading && (
            <Stack spacing={2} mt={2}>
              {SECTIONS.map((sec) => (
                <Paper key={sec.title} variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} color="primary.main" mb={1.5}>
                    {sec.title}
                  </Typography>
                  <Stack spacing={1.5}>
                    {sec.fields.map(([key, label, req]) => (
                      <TextField
                        key={key}
                        label={label + (req ? " *" : "")}
                        value={data[key] ?? ""}
                        onChange={set(key)}
                        multiline={label.length > 30 || key.startsWith("psych") || key.startsWith("initial")}
                        minRows={key.startsWith("initial") || key.startsWith("psych") || key.startsWith("social") || key === "family_relations" || key === "planning_goals" || key === "important_notes" ? 2 : 1}
                        disabled={!editable}
                        fullWidth
                      />
                    ))}
                  </Stack>
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
