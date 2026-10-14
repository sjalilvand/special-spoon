import {
  Alert, Box, Button, Chip, CircularProgress, Container, MenuItem,
  Paper, Stack, Step, StepLabel, Stepper, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useState } from "react";
import { fetchBookingSlots, fetchPublicCounselors, postConsultation } from "../api";
import type { BookingResult, PublicCounselor, SlotDay } from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { texts } from "../content/texts";

function faDayLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fa-IR", { weekday: "long", day: "numeric", month: "long" });
  } catch {
    return iso;
  }
}

export default function BookingPage() {
  const [step, setStep] = useState(0);
  const [counselors, setCounselors] = useState<PublicCounselor[] | null>(null);
  const [counselor, setCounselor] = useState<PublicCounselor | null>(null);
  const [days, setDays] = useState<SlotDay[] | null>(null);
  const [day, setDay] = useState<SlotDay | null>(null);
  const [slot, setSlot] = useState<{ start_at: string; label: string } | null>(null);
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<BookingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPublicCounselors().then(setCounselors).catch(() => setCounselors([]));
  }, []);

  const loadSlots = async (c: PublicCounselor) => {
    setDays(null); setDay(null); setSlot(null);
    try {
      setDays(await fetchBookingSlots(c.id));
    } catch {
      setError("خطا در دریافت نوبت‌های آزاد؛ دوباره تلاش کنید");
      setDays([]);
    }
  };

  const pickCounselor = (c: PublicCounselor) => {
    setCounselor(c); setError(null); setStep(1);
    loadSlots(c);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!counselor || !slot) return;
    setError(null); setBusy(true);
    try {
      const res = await postConsultation({
        full_name: fullName.trim(),
        mobile: mobile.trim(),
        topic,
        counselor_id: counselor.id,
        start_at: slot.start_at,
        message: message.trim() || undefined,
        website: honeypot,
      });
      setDone(res);
    } catch (err) {
      setError((err as Error).message || "خطا در ثبت رزرو");
      await loadSlots(counselor);
      setStep(1);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setStep(0); setCounselor(null); setDays(null); setDay(null); setSlot(null);
    setDone(null); setError(null);
  };

  return (
    <Box>
      <Header />
      <Container sx={{ py: 6, minHeight: "60vh" }}>
        <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center">
          رزرو نوبت مشاوره
        </Typography>
        <Typography variant="body1" color="text.secondary" textAlign="center" mb={4}>
          مشاور و زمان دلخواه خود را انتخاب کنید؛ پذیرش برای تأیید نهایی با شما تماس می‌گیرد.
        </Typography>

        {done && counselor && day && slot ? (
          <Paper sx={{ p: 4, maxWidth: 640, mx: "auto", textAlign: "center" }}>
            <Alert severity="success" sx={{ mb: 2 }}>درخواست رزرو شما ثبت شد.</Alert>
            <Typography variant="body1" fontWeight={700}>
              {counselor.name} — {faDayLabel(day.date)} ساعت {slot.label}
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1}>
              کد پیگیری: {done.request_id.slice(0, 8).toUpperCase()}
            </Typography>
            <Button sx={{ mt: 3 }} variant="outlined" onClick={reset}>رزرو جدید</Button>
          </Paper>
        ) : (
          <Paper sx={{ p: { xs: 2, md: 4 }, maxWidth: 760, mx: "auto" }}>
            <Stepper activeStep={step} alternativeLabel sx={{ mb: 3 }}>
              <Step><StepLabel>انتخاب مشاور</StepLabel></Step>
              <Step><StepLabel>انتخاب زمان</StepLabel></Step>
              <Step><StepLabel>اطلاعات شما</StepLabel></Step>
            </Stepper>

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

            {step === 0 && (
              counselors === null ? (
                <Stack alignItems="center" py={4}><CircularProgress /></Stack>
              ) : counselors.length === 0 ? (
                <Typography textAlign="center" color="text.secondary" py={3}>
                  در حال حاضر مشاوری برای رزرو موجود نیست.
                </Typography>
              ) : (
                <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={2}>
                  {counselors.map((c) => (
                    <Paper key={c.id} variant="outlined" sx={{ p: 2, cursor: "pointer", "&:hover": { borderColor: "primary.main" } }}
                      onClick={() => pickCounselor(c)}>
                      <Typography fontWeight={700}>{c.name}</Typography>
                      {c.professional_title && (
                        <Typography variant="body2" color="text.secondary">{c.professional_title}</Typography>
                      )}
                      {c.specialty && <Chip size="small" label={c.specialty} sx={{ mt: 1 }} />}
                    </Paper>
                  ))}
                </Box>
              )
            )}

            {step === 1 && (
              <Stack spacing={2}>
                {days === null ? (
                  <Stack alignItems="center" py={4}><CircularProgress /></Stack>
                ) : days.length === 0 ? (
                  <Typography textAlign="center" color="text.secondary" py={3}>
                    در ۳۰ روز آینده اسلات آزادی موجود نیست.
                  </Typography>
                ) : (
                  <>
                    {!day && (
                      <Box display="flex" flexWrap="wrap" gap={1}>
                        {days.map((d) => (
                          <Button key={d.date} variant="outlined" onClick={() => setDay(d)}>
                            {faDayLabel(d.date)} ({d.slots.length.toLocaleString("fa-IR")} نوبت)
                          </Button>
                        ))}
                      </Box>
                    )}
                    {day && (
                      <>
                        <Typography fontWeight={700}>{faDayLabel(day.date)}</Typography>
                        <Box display="flex" flexWrap="wrap" gap={1}>
                          {day.slots.map((s) => (
                            <Button key={s.start_at}
                              variant={slot?.start_at === s.start_at ? "contained" : "outlined"}
                              onClick={() => setSlot(s)}>
                              {s.label}
                            </Button>
                          ))}
                        </Box>
                        <Stack direction="row" spacing={1}>
                          <Button onClick={() => { setDay(null); setSlot(null); }}>تغییر روز</Button>
                          <Button variant="contained" disabled={!slot} onClick={() => setStep(2)}>ادامه</Button>
                        </Stack>
                      </>
                    )}
                  </>
                )}
              </Stack>
            )}

            {step === 2 && counselor && day && slot && (
              <form onSubmit={submit}>
                <Stack spacing={2.5}>
                  <Alert severity="info">
                    {counselor.name} — {faDayLabel(day.date)} ساعت {slot.label}
                  </Alert>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
                    <TextField label="نام و نام خانوادگی *" value={fullName}
                      onChange={(e) => setFullName(e.target.value)} required fullWidth />
                    <TextField label="موبایل * (09121234567)" value={mobile}
                      onChange={(e) => setMobile(e.target.value)} required fullWidth />
                  </Stack>
                  <TextField select label="موضوع *" value={topic}
                    onChange={(e) => setTopic(e.target.value)} required fullWidth>
                    {texts.topics.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                  </TextField>
                  <TextField label="توضیح کوتاه (اختیاری)" value={message}
                    onChange={(e) => setMessage(e.target.value)} multiline minRows={3} fullWidth />
                  {/* ضدربات: کاربر واقعی این فیلد را نمی‌بیند */}
                  <TextField label="وب‌سایت" value={honeypot}
                    onChange={(e) => setHoneypot(e.target.value)} sx={{ display: "none" }} />
                  <Stack direction="row" spacing={1}>
                    <Button onClick={() => setStep(1)}>بازگشت</Button>
                    <Button type="submit" variant="contained" size="large" disabled={busy}>
                      {busy ? "در حال ثبت…" : "ثبت رزرو"}
                    </Button>
                  </Stack>
                </Stack>
              </form>
            )}
          </Paper>
        )}
      </Container>
      <Footer />
    </Box>
  );
}