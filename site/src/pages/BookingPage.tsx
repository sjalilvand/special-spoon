// فاز ۵۶ - بازطراحی کامل صفحهٔ رزرو نوبت (زیباسازی) + فیکس باگ «نگه‌داشت منقضی»
//
// فیکس باگ اولین رزرو: پیش‌تر state «remaining» با مقدار اولیهٔ ۰ صبر می‌کرد تا
// افکت انقضا فایر شود؛ در همان کامِتی که hold ساخته می‌شد (remaining هنوز 0 بود)
// افکت انقضا بلافاصله فعال می‌شد و پیام «نگه‌داشت منقضی شد» در اولین ورود دیده
// می‌شد. اکنون remaining هنگام ساخت hold مقداردهی می‌شود و انقضا فقط پس از
// راه‌افتادن واقعی شمارش معکوس (countdownReadyRef) بررسی می‌شود.
import {
  Alert, Avatar, Box, Button, Chip, CircularProgress, Container, FormControl, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Stack, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createBookingHold, fetchBookingSlots, fetchPublicCounselors, postConsultation,
  releaseBookingHold, requestOtp, verifyOtp,
} from "../api";
import type { BookingHold, BookingResult, PublicCounselor, SlotDay } from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { texts } from "../content/texts";

const STEPS = ["انتخاب مشاور", "انتخاب زمان", "اطلاعات شما"];

function faDayLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fa-IR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  } catch {
    return iso;
  }
}

function faParts(iso: string): { weekday: string; day: string; month: string } {
  try {
    const d = new Date(iso + "T00:00:00");
    return {
      weekday: d.toLocaleDateString("fa-IR", { weekday: "long" }),
      day: d.toLocaleDateString("fa-IR", { day: "numeric" }),
      month: d.toLocaleDateString("fa-IR", { month: "long" }),
    };
  } catch {
    return { weekday: iso, day: "", month: "" };
  }
}

function fmtCountdown(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toLocaleString("fa-IR")}:${s.toString().padStart(2, "0").replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)])}`;
}

/** استپر سفارشی — دایرهٔ شماره/تیک + خط اتصال، راست‌به‌چپ */
function StepHeader({ step }: { step: number }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", mb: 4, px: { xs: 0.5, md: 2 } }}>
      {STEPS.map((label, i) => (
        <Box key={label} sx={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : undefined, minWidth: 0 }}>
          <Stack spacing={0.75} alignItems="center" sx={{ flexShrink: 0 }}>
            <Box sx={{
              width: 38, height: 38, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 800, fontSize: 15, transition: "all .25s",
              ...(i < step
                ? { bgcolor: "#e8f5ec", color: "#2e7d46", border: "2px solid #bfe3ca" }
                : i === step
                  ? { bgcolor: "primary.main", color: "#fff", boxShadow: "0 4px 14px rgba(124,39,64,.35)" }
                  : { bgcolor: "#fff", color: "#b9a6ad", border: "2px dashed #e5d3da" }),
            }}>
              {i < step ? "✓" : (i + 1).toLocaleString("fa-IR")}
            </Box>
            <Typography sx={{ fontSize: 12.5, fontWeight: i === step ? 800 : 600, color: i === step ? "primary.main" : i < step ? "#2e7d46" : "#b9a6ad", whiteSpace: "nowrap" }}>
              {label}
            </Typography>
          </Stack>
          {i < STEPS.length - 1 && (
            <Box sx={{
              flex: 1, height: 2, mx: 1.5, mb: 3, borderRadius: 1,
              background: i < step ? "linear-gradient(90deg,#bfe3ca,#e5d3da)" : "#efe3e8", minWidth: 24,
            }} />
          )}
        </Box>
      ))}
    </Box>
  );
}

function CounselorAvatar({ c, size }: { c: PublicCounselor; size: number }) {
  return (
    <Avatar
      src={c.photo_url || undefined}
      alt={c.name}
      sx={{ width: size, height: size, bgcolor: "#f3e2e8", color: "primary.main", fontWeight: 800, fontSize: size * 0.38, flexShrink: 0 }}
    >
      {c.name.trim().charAt(0)}
    </Avatar>
  );
}

function SendIconMini() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 16, height: 16, fill: "currentColor", transform: "scaleX(-1)" }} aria-hidden>
      <path d="M2.5 21 23 12 2.5 3l.01 7L17 12 2.51 14z" />
    </Box>
  );
}

export default function BookingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [step, setStep] = useState(0);
  const [counselors, setCounselors] = useState<PublicCounselor[] | null>(null);
  const [counselor, setCounselor] = useState<PublicCounselor | null>(null);
  // فاز ۶۷: فیلتر استان روی فهرست مشاوران قابل رزرو («لیست براساس انتخاب استان»)
  const [province, setProvince] = useState<string>("");
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

  // فاز ۲۶ - نگهداشت نوبت (+ فیکس فاز ۵۶)
  const [hold, setHold] = useState<BookingHold | null>(null);
  const [remaining, setRemaining] = useState(0);
  const holdRef = useRef<BookingHold | null>(null);
  const remainingRef = useRef(0);
  const countdownReadyRef = useRef(false);

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

  // فاز ۶۷: فهرست استان‌ها + فیلتر سمت کاربر (۲۱۶ آیتم — نیازی به کوئری سرور نیست)
  const provinces = useMemo(() => {
    const names = new Set<string>();
    for (const c of counselors ?? []) if (c.province_name) names.add(c.province_name);
    return Array.from(names).sort((a, b) => a.localeCompare(b, "fa"));
  }, [counselors]);
  const visibleCounselors = useMemo(
    () => (province ? (counselors ?? []).filter((c) => c.province_name === province) : (counselors ?? [])),
    [counselors, province],
  );

  // شمارش معکوس نگهداشت — محدودشده به زمان سمت سرور (remaining_seconds)
  // فاز ۵۶: remainingRef + countdownReadyRef برای این‌که افکت انقضا فقط پس از
  // راه‌افتادن واقعی شمارش فایر شود (نه با مقدار اولیهٔ 0 در همان اولین رندر)
  useEffect(() => {
    if (!hold) { countdownReadyRef.current = false; return; }
    remainingRef.current = hold.remaining_seconds;
    countdownReadyRef.current = true;
    setRemaining(hold.remaining_seconds);
    const deadline = Date.now() + hold.remaining_seconds * 1000;
    const iv = setInterval(() => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      remainingRef.current = left;
      setRemaining(left);
      if (left <= 0) clearInterval(iv);
    }, 1000);
    return () => clearInterval(iv);
  }, [hold]);

  // اسکرول نرم به بالای فرم با تغییر گام
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [step]);

  const dropHold = (silent = true) => {
    const h = holdRef.current;
    if (h) releaseBookingHold(h.hold_token).finally(() => undefined);
    if (!silent) setHold(null);
    holdRef.current = null;
    countdownReadyRef.current = false;
    remainingRef.current = 0;
    setHold(null);
    setRemaining(0);
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
      // فیکس فاز ۵۶: مقداردهی فوری remaining هم‌زمان با hold تا افکت انقضا با 0 فایر نشود
      setHold(h);
      setRemaining(h.remaining_seconds);
      setStep(2);
    } catch (err) {
      const raw = (err as Error).message || "";
      setError(
        raw.includes("در دسترس نیست") || raw.includes("نگه")
          ? "این زمان در دسترس نیست؛ بازه‌های تازه بارگذاری شد — لطفاً زمان دیگری انتخاب کنید"
          : raw || "این زمان در دسترس نیست؛ اسلات دیگری انتخاب کنید",
      );
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
      countdownReadyRef.current = false;
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

  // انقضای نگهداشت هنگام تکمیل فرم — فقط پس از راه‌افتادن واقعی شمارش (فیکس فاز ۵۶)
  useEffect(() => {
    if (step === 2 && hold && countdownReadyRef.current && remaining <= 0 && remainingRef.current <= 0) {
      setError("زمان نگهداشت نوبت به پایان رسید؛ لطفاً اسلات را دوباره انتخاب کنید");
      holdRef.current = null;
      countdownReadyRef.current = false;
      setHold(null);
      setOtpSent(false); setOtpCode(""); setOtpToken(null); setOtpDevCode(null);
      if (counselor) loadSlots(counselor);
      setStep(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, step, hold]);

  // گروه‌بندی اسلات‌ها بر اساس ساعت (صبح/بعدازظهر)
  const slotGroups = day
    ? (() => {
        const morning = day.slots.filter((s) => (parseInt(s.label.slice(0, 2), 10) || 0) < 12);
        const evening = day.slots.filter((s) => (parseInt(s.label.slice(0, 2), 10) || 0) >= 12);
        const groups: { title: string; items: typeof morning }[] = [];
        if (morning.length) groups.push({ title: "☀ صبح", items: morning });
        if (evening.length) groups.push({ title: "◐ بعدازظهر و عصر", items: evening });
        return groups.length ? groups : [{ title: "بازه‌های آزاد", items: day.slots }];
      })()
    : [];

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container sx={{ py: { xs: 4, md: 6 }, minHeight: "60vh" }}>
          <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center">
            رزرو نوبت مشاوره
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center" mb={{ xs: 3, md: 4 }}>
            مشاور و زمان دلخواه خود را انتخاب کنید؛ پذیرش برای تأیید نهایی با شما تماس می‌گیرد.
          </Typography>

          {done && counselor && day && slot ? (
            <Paper sx={{ p: { xs: 3, md: 5 }, maxWidth: 560, mx: "auto", textAlign: "center", borderRadius: 4, border: "1px solid #f3dce2" }}>
              <Box sx={{
                width: 84, height: 84, borderRadius: "50%", mx: "auto", mb: 2,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: "linear-gradient(135deg,#e8f5ec,#d3ecd9)", color: "#2e7d46", fontSize: 42,
                animation: "rosepsyPop .45s ease", "@keyframes rosepsyPop": { from: { transform: "scale(.4)", opacity: 0 }, to: { transform: "scale(1)", opacity: 1 } },
              }}>✓</Box>
              <Typography variant="h6" fontWeight={800} mb={1}>درخواست رزرو شما ثبت شد</Typography>
              <Typography variant="body1" fontWeight={700} color="primary.main">
                {counselor.name} — {faDayLabel(day.date)} ساعت {slot.label}
              </Typography>
              <Chip
                sx={{ mt: 2, fontWeight: 700, letterSpacing: 1 }}
                color="primary" variant="outlined"
                label={`کد پیگیری: ${done.request_id.slice(0, 8).toUpperCase()}`}
              />
              <Typography variant="body2" color="text.secondary" mt={2} px={2}>
                پذیرش تا چند ساعت آینده برای تأیید نهایی با شما تماس می‌گیرد. جزئیات این نوبت در سامانه نیز برای شما ثبت شد.
              </Typography>
              <Button sx={{ mt: 3 }} variant="outlined" onClick={reset}>رزرو جدید</Button>
            </Paper>
          ) : (
            <Paper sx={{ p: { xs: 2, md: 4 }, maxWidth: 820, mx: "auto", borderRadius: 4, border: "1px solid #f3dce2", boxShadow: "0 18px 44px rgba(124,39,64,.10)" }}>
              <StepHeader step={step} />

              {error && <Alert severity="warning" sx={{ mb: 2, borderRadius: 2 }} onClose={() => setError(null)} role="alert">{error}</Alert>}

              {/* گام ۰ — انتخاب مشاور */}
              {step === 0 && (
                counselors === null ? (
                  <Stack alignItems="center" py={6} role="status" aria-label="در حال بارگذاری مشاوران"><CircularProgress /></Stack>
                ) : counselors.length === 0 ? (
                  <Typography textAlign="center" color="text.secondary" py={3}>
                    در حال حاضر مشاوری برای رزرو موجود نیست.
                  </Typography>
                ) : (
                  <>
                  {/* فاز ۶۷: انتخاب استان — «لیست را براساس انتخاب استان بذار» */}
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mb: 2 }}>
                    <FormControl size="small" sx={{ minWidth: 240 }}>
                      <InputLabel>فیلتر استان</InputLabel>
                      <Select
                        value={province}
                        label="فیلتر استان"
                        onChange={(e) => setProvince(e.target.value)}
                      >
                        <MenuItem value="">همهٔ استان‌ها</MenuItem>
                        {provinces.map((p) => (
                          <MenuItem key={p} value={p}>{p}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <Typography variant="body2" color="text.secondary">
                      {visibleCounselors.length.toLocaleString("fa-IR")} مشاور قابل رزرو
                    </Typography>
                  </Stack>
                  {visibleCounselors.length === 0 ? (
                    <Typography textAlign="center" color="text.secondary" py={3}>
                      برای این استان مشاوری قابل رزرو نیست — استان دیگری را انتخاب کنید.
                    </Typography>
                  ) : (
                  <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={2}>
                    {visibleCounselors.map((c) => (
                      <Paper
                        key={c.id} variant="outlined"
                        sx={{
                          p: 2, cursor: "pointer", borderRadius: 3, transition: "all .2s",
                          borderColor: "#f0dde2", "&:hover": { borderColor: "primary.main", boxShadow: "0 8px 22px rgba(124,39,64,.14)", transform: "translateY(-2px)" },
                        }}
                        onClick={() => pickCounselor(c)} aria-label={`انتخاب مشاور ${c.name}`}
                      >
                        <Stack direction="row" spacing={2} alignItems="center">
                          <CounselorAvatar c={c} size={54} />
                          <Box sx={{ minWidth: 0, flex: 1 }}>
                            <Typography fontWeight={800} noWrap>{c.name}</Typography>
                            {c.professional_title && (
                              <Typography variant="body2" color="text.secondary" noWrap>{c.professional_title}</Typography>
                            )}
                            {c.specialty && <Chip size="small" label={c.specialty} sx={{ mt: 0.75, bgcolor: "#fdf3f5" }} />}
                            {c.province_name && (
                              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>
                                کلینیک رز — {c.province_name}
                              </Typography>
                            )}
                          </Box>
                          <Box sx={{ color: "primary.main", flexShrink: 0, fontWeight: 800 }}>‹</Box>
                        </Stack>
                      </Paper>
                    ))}
                  </Box>
                  )
                  }
                  </>
                )
              )}

              {/* گام ۱ — انتخاب زمان */}
              {step === 1 && counselor && (
                <Stack spacing={2.5}>
                  <Stack direction="row" alignItems="center" spacing={1.5} sx={{ bgcolor: "#fdf3f5", borderRadius: 2.5, p: 1.25 }}>
                    <CounselorAvatar c={counselor} size={38} />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography fontWeight={800} fontSize={14}>{counselor.name}</Typography>
                      <Button size="small" sx={{ p: 0, minWidth: 0, fontSize: 12 }} onClick={() => { dropHold(); setStep(0); setDays(null); setDay(null); setSlot(null); }}>
                        تغییر مشاور
                      </Button>
                    </Box>
                    {day && <Chip label={faDayLabel(day.date)} size="small" color="primary" variant="outlined" />}
                  </Stack>

                  {days === null ? (
                    <Stack alignItems="center" py={6} role="status" aria-label="در حال بارگذاری نوبت‌ها"><CircularProgress /></Stack>
                  ) : days.length === 0 ? (
                    <Typography textAlign="center" color="text.secondary" py={3}>
                      در ۳۰ روز آینده اسلات آزادی موجود نیست.
                    </Typography>
                  ) : (
                    <>
                      {/* انتخاب روز — کارت‌های افقی اسکرول‌شو */}
                      {!day ? (
                        <Box sx={{ display: "flex", gap: 1.2, overflowX: "auto", pb: 1, "::-webkit-scrollbar": { height: 6 }, "::-webkit-scrollbar-thumb": { bgcolor: "#ecd7de", borderRadius: 3 } }}>
                          {days.map((d) => {
                            const p = faParts(d.date);
                            return (
                              <Paper
                                key={d.date} variant="outlined"
                                onClick={() => setDay(d)}
                                aria-label={`روز ${faDayLabel(d.date)} با ${d.slots.length} نوبت آزاد`}
                                sx={{
                                  cursor: "pointer", textAlign: "center", px: 2, py: 1.4, minWidth: 108, flexShrink: 0, borderRadius: 3,
                                  borderColor: "#f0dde2", transition: "all .2s",
                                  "&:hover": { borderColor: "primary.main", bgcolor: "#fdf3f5", transform: "translateY(-2px)" },
                                }}
                              >
                                <Typography sx={{ fontSize: 12, fontWeight: 700, color: "primary.main" }}>{p.weekday}</Typography>
                                <Typography sx={{ fontSize: 24, fontWeight: 800, lineHeight: 1.3 }}>{p.day}</Typography>
                                <Typography sx={{ fontSize: 11, color: "text.secondary" }}>{p.month}</Typography>
                                <Chip size="small" sx={{ mt: 0.5, height: 18, fontSize: 10.5, bgcolor: "#e8f5ec", color: "#2e7d46" }}
                                  label={`${d.slots.length.toLocaleString("fa-IR")} نوبت`} />
                              </Paper>
                            );
                          })}
                        </Box>
                      ) : (
                        <>
                          {/* اسلات‌های روز انتخاب‌شده — گروه‌بندی صبح/عصر */}
                          {slotGroups.map((g) => (
                            <Box key={g.title}>
                              <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ display: "block", mb: 1 }}>{g.title}</Typography>
                              <Box display="flex" flexWrap="wrap" gap={1}>
                                {g.items.map((s) => (
                                  <Button
                                    key={s.start_at}
                                    variant={slot?.start_at === s.start_at ? "contained" : "outlined"}
                                    onClick={() => setSlot(s)}
                                    aria-label={`ساعت ${s.label}`}
                                    sx={{ borderRadius: 999, minWidth: 86, fontWeight: 700, px: 2, py: 0.6 }}
                                  >
                                    {s.label}
                                  </Button>
                                ))}
                              </Box>
                            </Box>
                          ))}
                          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ borderTop: "1px dashed #ecd7de", pt: 2 }}>
                            <Button onClick={() => { setDay(null); setSlot(null); }}>‹ همهٔ روزها</Button>
                            <Button variant="contained" size="large" disabled={!slot} onClick={proceedToInfo}
                              endIcon={<SendIconMini />} sx={{ borderRadius: 999, px: 4 }}>
                              ادامه
                            </Button>
                          </Stack>
                        </>
                      )}
                    </>
                  )}
                </Stack>
              )}

              {/* گام ۲ — اطلاعات و ثبت */}
              {step === 2 && counselor && day && slot && (
                <form onSubmit={submit}>
                  <Stack spacing={2.5}>
                    {/* خلاصهٔ رزرو + شمارش معکوس */}
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: "#fdf3f5", borderColor: "#f0dde2" }}>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <CounselorAvatar c={counselor} size={46} />
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography fontWeight={800}>{counselor.name}</Typography>
                          <Typography variant="body2" color="text.secondary">{faDayLabel(day.date)} — ساعت {slot.label}</Typography>
                        </Box>
                        {hold && remaining > 0 && (
                          <Stack alignItems="flex-end" spacing={0.5} sx={{ minWidth: 120 }}>
                            <Chip
                              size="small"
                              color={remaining <= 60 ? "warning" : "primary"}
                              variant="filled"
                              label={`⏱ نگهداشت: ${fmtCountdown(remaining)}`}
                              aria-live="polite"
                            />
                            <LinearProgress
                              variant="determinate"
                              value={Math.max(2, Math.min(100, (remaining / (hold.hold_minutes * 60)) * 100))}
                              sx={{ width: 120, height: 5, borderRadius: 3, bgcolor: "#f0dde2" }}
                            />
                          </Stack>
                        )}
                      </Stack>
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                        این زمان تا پایان شمارش معکوس فقط برای شما نگه داشته شده است.
                      </Typography>
                    </Paper>

                    <TextField label="نام و نام خانوادگی *" value={fullName}
                      onChange={(e) => setFullName(e.target.value)} required fullWidth />
                    <TextField label="موبایل * (09121234567)" value={mobile}
                      onChange={(e) => { setMobile(e.target.value); setOtpSent(false); setOtpToken(null); }}
                      required fullWidth inputMode="tel" />

                    {/* فاز ۲۶ - تأیید موبایل با کد یک‌بارمصرف */}
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: "#fffdf5", borderColor: "#f0e2c0" }}>
                      <Stack direction="row" alignItems="center" spacing={1} mb={1.25}>
                        <Box sx={{ width: 22, height: 22, borderRadius: "50%", bgcolor: "#f5b301", color: "#fff", fontSize: 12, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>۲</Box>
                        <Typography variant="subtitle2" fontWeight={700}>تأیید شماره موبایل *</Typography>
                      </Stack>
                      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems="center">
                        <Button variant="outlined" onClick={sendOtp} disabled={otpBusy}
                          aria-label="ارسال کد تأیید موبایل" sx={{ borderRadius: 999, whiteSpace: "nowrap" }}>
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
                    <Stack direction="row" spacing={1} justifyContent="space-between" sx={{ pt: 1 }}>
                      <Button onClick={() => { dropHold(); setStep(1); }} aria-label="بازگشت به انتخاب زمان">
                        ‹ بازگشت
                      </Button>
                      <Button type="submit" variant="contained" size="large" disabled={busy || !otpToken || remaining <= 0}
                        aria-label="ثبت نهایی رزرو" endIcon={!busy ? <SendIconMini /> : undefined} sx={{ borderRadius: 999, px: 5 }}>
                        {busy ? "در حال ثبت…" : "ثبت رزرو"}
                      </Button>
                    </Stack>
                  </Stack>
                </form>
              )}
            </Paper>
          )}
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
