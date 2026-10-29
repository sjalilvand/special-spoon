import {
  Alert, Box, Button, Chip, CircularProgress, Container, MenuItem,
  Paper, Stack, Step, StepLabel, Stepper, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createBookingHold, fetchBookingSlots, fetchPublicCounselors, postConsultation,
  releaseBookingHold, requestOtp, verifyOtp,
} from "../api";
import type { BookingHold, BookingResult, PublicCounselor, SlotDay } from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { texts } from "../content/texts";

function faDayLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fa-IR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  } catch {
    return iso;
  }
}

function fmtCountdown(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toLocaleString("fa-IR")}:${s.toString().padStart(2, "0").replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)])}`;
}

export default function BookingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
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

  // فاز ۲۶ - نگهداشت نوبت
  const [hold, setHold] = useState<BookingHold | null>(null);
  const [remaining, setRemaining] = useState(0);
  const holdRef = useRef<BookingHold | null>(null);

  // فاز ۲۶ - کد یک‌بارمصرف
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpToken, setOtpToken] = useState<string | null>(null);
  const [otpDevCode, setOtpDevCode] = useState<string | null>(null);
  const [otpBusy, setOtpBusy] = useState(false);

  useEffect(() => {
    fetchPublicCounselors().then((list) => {
      setCounselors(list);
      // فاز ۵۴ - پیش‌انتخاب مشاور از لینک چت: /booking?counselor=<id>
      const wanted = searchParams.get("counselor");
      if (wanted) {
        const found = list.find((c) => c.id === wanted);
        if (found) {
          setCounselor(found);
          setStep(1);
          fetchBookingSlots(found.id)
            .then(setDays)
            .catch(() => setDays([]));
        }
        setSearchParams({}, { replace: true });
      }
    }).catch(() => setCounselors([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // شمارش معکوس نگهداشت - محدودشده به زمان سمت سرور با remaining_seconds
  useEffect(() => {
    if (!hold) return;
    setRemaining(hold.remaining_seconds);
    const deadline = Date.now() + hold.remaining_seconds * 1000;
    const iv = setInterval(() => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setRemaining(left);
      if (left <= 0) clearInterval(iv);
    }, 1000);
    return () => clearInterval(iv);
  }, [hold]);

  const dropHold = (silent = true) => {
    const h = holdRef.current;
    if (h) releaseBookingHold(h.hold_token).finally(() => undefined);
    if (!silent) setHold(null);
    holdRef.current = null;
    setHold(null);
    setOtpSent(false);
    setOtpCode("");
    setOtpToken(null);
    setOtpDevCode(null);
  };

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
    dropHold();
    setCounselor(c); setError(null); setStep(1);
    loadSlots(c);
  };

  // ادامه از انتخاب زمان → نگهداشت اسلات و رفتن به فرم اطلاعات
  const proceedToInfo = async () => {
    if (!counselor || !slot) return;
    setError(null);
    if (holdRef.current) {
      // نگهداشت فعلی روی همین اسلات است؛ ادامه بده
      setStep(2);
      return;
    }
    try {
      const h = await createBookingHold(counselor.id, slot.start_at);
      holdRef.current = h;
      setHold(h);
      setStep(2);
    } catch (err) {
      setError((err as Error).message || "این زمان در دسترس نیست؛ اسلات دیگری انتخاب کنید");
      await loadSlots(counselor);
      setDay(null); setSlot(null);
    }
  };

  const sendOtp = async () => {
    if (!/09\d{9}/.test(mobile.trim())) {
      setError("شماره موبایل را به قالب 09121234567 وارد کنید");
      return;
    }
    setError(null); setOtpBusy(true);
    try {
      const res = await requestOtp(mobile.trim());
      setOtpSent(true);
      setOtpDevCode(res.dev_code ?? null);
      setOtpToken(null);
    } catch (err) {
      setError((err as Error).message || "خطا در ارسال کد تأیید");
    } finally {
      setOtpBusy(false);
    }
  };

  const checkOtp = async () => {
    if (!otpCode.trim()) return;
    setError(null); setOtpBusy(true);
    try {
      const res = await verifyOtp(mobile.trim(), otpCode.trim());
      setOtpToken(res.verify_token);
    } catch (err) {
      setError((err as Error).message || "کد تأیید نامعتبر است");
    } finally {
      setOtpBusy(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!counselor || !slot || !holdRef.current) return;
    if (!otpToken) {
      setError("لطفاً موبایل خود را با کد یک‌بارمصرف تأیید کنید");
      return;
    }
    setError(null); setBusy(true);
    try {
      const res = await postConsultation({
        full_name: fullName.trim(),
        mobile: mobile.trim(),
        topic,
        counselor_id: counselor.id,
        start_at: slot.start_at,
        hold_token: holdRef.current.hold_token,
        otp_token: otpToken,
        message: message.trim() || undefined,
        website: honeypot,
      });
      setDone(res);
      holdRef.current = null;
      setHold(null);
    } catch (err) {
      const msg = (err as Error).message || "خطا در ثبت رزرو";
      setError(msg);
      if (msg.includes("منقضی") || msg.includes("در دسترس نیست") || msg.includes("رزرو شد")) {
        dropHold();
        if (counselor) await loadSlots(counselor);
        setStep(1);
      }
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    dropHold();
    setStep(0); setCounselor(null); setDays(null); setDay(null); setSlot(null);
    setDone(null); setError(null);
  };

  // انقضای نگهداشت هنگام تکمیل فرم
  useEffect(() => {
    if (step === 2 && hold && remaining <= 0) {
      setError("زمان نگهداشت نوبت منقضی شد؛ لطفاً اسلات را دوباره انتخاب کنید");
      holdRef.current = null;
      setHold(null);
      setOtpSent(false); setOtpCode(""); setOtpToken(null); setOtpDevCode(null);
      if (counselor) loadSlots(counselor);
      setStep(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, step, hold]);

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

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)} role="alert">{error}</Alert>}

            {step === 0 && (
              counselors === null ? (
                <Stack alignItems="center" py={4} role="status" aria-label="در حال بارگذاری مشاوران"><CircularProgress /></Stack>
              ) : counselors.length === 0 ? (
                <Typography textAlign="center" color="text.secondary" py={3}>
                  در حال حاضر مشاوری برای رزرو موجود نیست.
                </Typography>
              ) : (
                <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={2}>
                  {counselors.map((c) => (
                    <Paper key={c.id} variant="outlined" sx={{ p: 2, cursor: "pointer", "&:hover": { borderColor: "primary.main" } }}
                      onClick={() => pickCounselor(c)} aria-label={`انتخاب مشاور ${c.name}`}>
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
                  <Stack alignItems="center" py={4} role="status" aria-label="در حال بارگذاری نوبت‌ها"><CircularProgress /></Stack>
                ) : days.length === 0 ? (
                  <Typography textAlign="center" color="text.secondary" py={3}>
                    در ۳۰ روز آینده اسلات آزادی موجود نیست.
                  </Typography>
                ) : (
                  <>
                    {!day && (
                      <Box display="flex" flexWrap="wrap" gap={1}>
                        {days.map((d) => (
                          <Button key={d.date} variant="outlined" onClick={() => setDay(d)}
                            aria-label={`روز ${faDayLabel(d.date)} با ${d.slots.length} نوبت آزاد`}>
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
                              onClick={() => setSlot(s)}
                              aria-label={`ساعت ${s.label}`}>
                              {s.label}
                            </Button>
                          ))}
                        </Box>
                        <Stack direction="row" spacing={1}>
                          <Button onClick={() => { setDay(null); setSlot(null); }}>تغییر روز</Button>
                          <Button variant="contained" disabled={!slot} onClick={proceedToInfo}>ادامه</Button>
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
                  <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                    <Alert severity="info" sx={{ flex: 1, minWidth: 240 }}>
                      {counselor.name} — {faDayLabel(day.date)} ساعت {slot.label}
                    </Alert>
                    {hold && remaining > 0 && (
                      <Chip
                        size="medium"
                        color={remaining <= 60 ? "warning" : "primary"}
                        variant="filled"
                        label={`نگهداشت نوبت: ${fmtCountdown(remaining)}`}
                        aria-live="polite"
                      />
                    )}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    این زمان تا پایان شمارش معکوس برای شما نگه داشته شده است.
                  </Typography>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
                    <TextField label="نام و نام خانوادگی *" value={fullName}
                      onChange={(e) => setFullName(e.target.value)} required fullWidth />
                    <TextField label="موبایل * (09121234567)" value={mobile}
                      onChange={(e) => { setMobile(e.target.value); setOtpSent(false); setOtpToken(null); }}
                      required fullWidth inputMode="tel" />
                  </Stack>

                  {/* فاز ۲۶ - تأیید موبایل با کد یک‌بارمصرف */}
                  <Paper variant="outlined" sx={{ p: 2, bgcolor: "#fafafa" }}>
                    <Typography variant="subtitle2" fontWeight={700} mb={1}>تأیید شماره موبایل *</Typography>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems="center">
                      <Button variant="outlined" onClick={sendOtp} disabled={otpBusy}
                        aria-label="ارسال کد تأیید موبایل">
                        {otpBusy ? "…" : otpSent ? "ارسال دوباره کد" : "دریافت کد تأیید"}
                      </Button>
                      {otpSent && (
                        <>
                          <TextField size="small" label="کد ۶ رقمی" value={otpCode}
                            onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                            inputMode="numeric" sx={{ maxWidth: 160 }} aria-label="کد یک‌بارمصرف" />
                          <Button variant="text" onClick={checkOtp} disabled={otpBusy || otpCode.length < 4}>
                            بررسی کد
                          </Button>
                          {otpToken && <Chip size="small" color="success" label="موبایل تأیید شد ✓" />}
                        </>
                      )}
                    </Stack>
                    {otpDevCode && !otpToken && (
                      <Alert severity="info" sx={{ mt: 1.5, py: 0.5 }}>
                        حالت توسعه — کد شما: <b dir="ltr">{otpDevCode}</b>
                      </Alert>
                    )}
                  </Paper>

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
                    <Button onClick={() => { dropHold(); setStep(1); }} aria-label="بازگشت به انتخاب زمان">بازگشت</Button>
                    <Button type="submit" variant="contained" size="large" disabled={busy || !otpToken || remaining <= 0}
                      aria-label="ثبت نهایی رزرو">
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
