import { Alert, Box, Button, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { FormEvent, useState } from "react";
import DatePicker from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import { postConsultation } from "../api";
import { texts } from "../content/texts";

interface JalaliShape {
  year: number;
  monthNumber: number;
  day: number;
}

function toIsoDate(d: JalaliShape | null): string | undefined {
  if (!d || typeof d.year !== "number") return undefined;
  return new Date(Date.UTC(d.year, d.monthNumber - 1, d.day)).toISOString().slice(0, 10);
}

export default function ConsultForm() {
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [topic, setTopic] = useState("");
  const [slot, setSlot] = useState("");
  const [dateVal, setDateVal] = useState<JalaliShape | null>(null);
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await postConsultation({
        full_name: fullName.trim(),
        mobile: mobile.trim(),
        topic,
        preferred_date: toIsoDate(dateVal),
        preferred_slot: slot || undefined,
        message: message.trim() || undefined,
        website: honeypot, // ضدربات — باید خالی بماند
      });
      setDone(true);
    } catch (err) {
      setError((err as Error).message || "خطا در ارسال");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ bgcolor: "#fdf2f4", py: 8 }}>
      <Container id="consult">
        <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center">
          {texts.consultTitle}
        </Typography>
        <Typography variant="body1" color="text.secondary" textAlign="center" mb={4}>
          {texts.consultSub}
        </Typography>

        {done ? (
          <Paper sx={{ p: 4, maxWidth: 640, mx: "auto", textAlign: "center" }}>
            <Alert severity="success">
              درخواست شما ثبت شد. کارشناسان پذیرش در اولین فرصت با شما تماس می‌گیرند.
            </Alert>
          </Paper>
        ) : (
          <Paper sx={{ p: { xs: 2, md: 4 }, maxWidth: 680, mx: "auto" }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <form onSubmit={submit}>
              <Stack spacing={2.5}>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
                  <TextField
                    label="نام و نام خانوادگی *"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    fullWidth
                  />
                  <TextField
                    label="شماره موبایل * (مثال: 09121234567)"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                    required
                    fullWidth
                  />
                </Stack>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
                  <TextField
                    select
                    label="موضوع درخواست *"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    required
                    fullWidth
                  >
                    {texts.topics.map((t) => (
                      <MenuItem key={t} value={t}>
                        {t}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField select label="بازه زمانی ترجیحی" value={slot} onChange={(e) => setSlot(e.target.value)} fullWidth>
                    {texts.slots.map((s) => (
                      <MenuItem key={s} value={s}>
                        {s}
                      </MenuItem>
                    ))}
                  </TextField>
                </Stack>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    تاریخ ترجیحی تماس (تقویم شمسی)
                  </Typography>
                  <DatePicker
                    value={dateVal}
                    onChange={(d) => setDateVal(d as unknown as JalaliShape | null)}
                    calendar={persian}
                    locale={persian_fa}
                    containerStyle={{ width: "100%" }}
                  />
                </Box>
                <TextField
                  label="توضیح کوتاه (اختیاری)"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  multiline
                  minRows={3}
                  fullWidth
                />
                {/* ضدربات: کاربر واقعی این فیلد را نمی‌بیند */}
                <TextField
                  label="وب‌سایت"
                  value={honeypot}
                  onChange={(e) => setHoneypot(e.target.value)}
                  sx={{ display: "none" }}
                />
                <Button type="submit" variant="contained" size="large" disabled={busy}>
                  {busy ? "در حال ارسال…" : "ارسال درخواست مشاوره"}
                </Button>
              </Stack>
            </form>
          </Paper>
        )}
      </Container>
    </Box>
  );
}
