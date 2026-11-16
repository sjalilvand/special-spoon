// فاز ۸۸ - صفحهٔ عمومی «فراخوان همکاری» (پورت کامل فرم مرجع Samaneh-IT-rose/farakhan)
//
// لینک مستقیم این صفحه: /farakhan (قابل انتشار در گروه‌ها و سامانه‌های دیگر؛
// بدون نیاز به ورود). پیش از ذخیره، کپچای محاسبهٔ دو عدد تک‌مصرف چک می‌شود و
// همهٔ اعتبارسنجی‌ها (کد ملی، تاریخ شمسی، موبایل/ثابت، کدپستی، شرط‌ها) هم در
// مرورگر (سبک) و هم سرور (کامل، هم‌ارز فرم مرجع) انجام می‌شود. پاسخ موفق یک
// کد پیگیری بدون دادهٔ شخصی برمی‌گرداند.
import {
  Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container,
  Divider, FormControl, FormControlLabel, FormHelperText, Grid, IconButton,
  InputLabel, MenuItem, Paper, Select, Stack, Switch, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FarakhanServerError, fetchFarakhanCaptcha, fetchFarakhanCounties, fetchFarakhanMeta,
  fetchFarakhanProvinces, fetchFarakhanPublicSubmissions, FarakhanValidationError,
  submitFarakhan, checkFarakhanNationalCode,
} from "../api";
import type {
  FarakhanCaptcha, FarakhanFileField, FarakhanLocationOption, FarakhanMeta, FarakhanPublicList,
} from "../api";
import {
  FARAKHAN_MAX_AGE, FARAKHAN_MIN_AGE, birthDateCalendarBounds, completedAgeFromJalali,
  isValidNationalCode, normalizeFaDigits,
} from "../utils/farakhanRules";
import JalaliDatePicker from "../components/JalaliDatePicker";
import Footer from "../components/Footer";
import Header from "../components/Header";

/** آیکون بازخوانی — SVG داخلی (سایت عمداً وابسته به @mui/icons-material ندارد) */
function RefreshIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 20, height: 20, display: "block" }} aria-hidden>
      <path
        d="M17.65 6.35A7.96 7.96 0 0012 4a8 8 0 108 8h-2a6 6 0 11-1.76-4.24L13 11h7V4l-2.35 2.35z"
        fill="currentColor"
      />
    </Box>
  );
}

/** آیکون پاک‌کردن انتخاب فایل — SVG داخلی */
function ClearIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 18, height: 18, display: "block" }} aria-hidden>
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor" />
    </Box>
  );
}

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  national_code: "",
  gender: "",
  birth_date: "",
  military_status: "",
  education_degree: "",
  education_field: "",
  license_status: "",
  license_number: "",
  license_description: "",
  center_ownership: "",
  province_id: "",
  county_name: "",
  phone: "",
  mobile_number: "",
  postal_code: "",
  address: "",
  individual_rooms: 0,
  group_rooms: 0,
  child_rooms: 0,
  counselors_count: 0,
  has_waiting_space: false,
  accepts_company_pattern: false,
  has_accessibility: false,
  terms_accepted: false,
  captcha_answer: "",
};

type FormState = typeof EMPTY_FORM;

function faNum(n: number): string {
  return n.toLocaleString("fa-IR");
}

const SESSION_KEY = "farakhan_session_v1";

/** نشست ذخیره‌شدهٔ فرم در این تب — تا بازشدن تازهٔ لینک، مهلت از اولین ورود حساب می‌شود */
function readSavedSession(): { sid: string; deadline: number } | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { sid?: unknown; deadline?: unknown };
    if (typeof parsed.sid !== "string" || typeof parsed.deadline !== "number") return null;
    if (parsed.deadline <= Date.now()) return null;
    return { sid: parsed.sid, deadline: parsed.deadline };
  } catch {
    return null;
  }
}

function clearSavedSession(): void {
  try { sessionStorage.removeItem(SESSION_KEY); } catch { /* private mode — بی‌اهمیت */ }
}

/** ساعت شمارش معکوس با ارقام فارسی: ۰۱:۲۳:۴۵ */
function faClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const two = (x: number) => String(x).padStart(2, "0");
  const text = `${two(Math.floor(s / 3600))}:${two(Math.floor((s % 3600) / 60))}:${two(s % 60)}`;
  return text.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}

/** آیکون ساعت‌شیشه‌ای — SVG داخلی */
function TimerIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 22, height: 22, display: "block", mt: 0.25 }} aria-hidden>
      <path
        d="M6 2v6h.01L6 8.01 10 12l-4 4 .01.01H6V22h12v-5.99h-.01L18 16l-4-4 4-3.99-.01-.01H18V2H6zm10 14.5V20H8v-3.5l4-4 4 4zm-4-5l-4-4V4h8v3.5l-4 4z"
        fill="currentColor"
      />
    </Box>
  );
}

function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <Card elevation={0} sx={{ border: "1px solid #f3dce2", borderRadius: 4, overflow: "hidden" }}>
      <Box sx={{ background: "linear-gradient(90deg,#fdf3f5,#fbf7f4)", px: { xs: 2, md: 3 }, py: 1.5 }}>
        <Typography variant="subtitle1" fontWeight={800} color="primary.main">{title}</Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">{subtitle}</Typography>
        )}
      </Box>
      <CardContent sx={{ p: { xs: 2, md: 3 } }}>{children}</CardContent>
    </Card>
  );
}

/** فاز ۹۴ — جدول عمومی «افراد ثبت‌نام‌شدهٔ فراخوان» (خواستهٔ صاحب سامانه).
 * تنها نام، استان/شهرستان، مدرک و تاریخ ثبت نمایش داده می‌شود؛ دادهٔ حساس
 * (کد ملی، تلفن، نشانی، فایل‌ها و وضعیت بررسی) از سرور عمومی منتشر نمی‌شود. */
function RegisteredPeopleCard() {
  const [data, setData] = useState<FarakhanPublicList | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    fetchFarakhanPublicSubmissions()
      .then((d) => setData(d))
      .catch(() => setFailed(true));
  }, []);
  useEffect(() => { load(); }, [load]);
  const faDate = (iso: string | null): string => {
    if (!iso) return "—";
    try {
      return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(iso));
    } catch {
      return iso.slice(0, 10);
    }
  };
  return (
    <SectionCard
      title="افراد ثبت‌نام‌شدهٔ فراخوان"
      subtitle={data
        ? `تا کنون ${faNum(data.total)} نفر ثبت‌نام کرده‌اند — کد ملی، شمارهٔ تماس و نشانی هرگز نمایش داده نمی‌شود.`
        : "در حال دریافت فهرست ثبت‌نام‌شده‌ها…"}
    >
      {failed ? (
        <Alert severity="warning">دریافت فهرست ثبت‌نام‌شده‌ها ناموفق بود؛ صفحه را دوباره باز کنید.</Alert>
      ) : data === null ? (
        <Stack alignItems="center" py={4}><CircularProgress sx={{ color: "primary.main" }} /></Stack>
      ) : data.items.length === 0 ? (
        <Typography variant="body2" color="text.secondary" textAlign="center" py={3}>
          هنوز ثبت‌نامی انجام نشده است؛ پس از ثبت‌نام، نام افراد در همین جدول نمایش داده می‌شود.
        </Typography>
      ) : (
        <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid #f3dce2", borderRadius: 3 }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: "#fdf3f5" }}>
                <TableCell sx={{ fontWeight: 800 }}>ردیف</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>نام و نام خانوادگی</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>استان / شهرستان</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>مدرک تحصیلی</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>تاریخ ثبت</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.map((row, i) => (
                <TableRow key={`${row.name}-${row.created_at ?? i}-${i}`} hover>
                  <TableCell>{faNum(i + 1)}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{row.name}</TableCell>
                  <TableCell>{row.province_name} / {row.county_name}</TableCell>
                  <TableCell>{row.education_degree_label}</TableCell>
                  <TableCell>{faDate(row.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </SectionCard>
  );
}

function FilePicker({
  field, meta, file, onPick,
}: {
  field: FarakhanFileField;
  meta: FarakhanMeta;
  file: File | null;
  onPick: (key: string, file: File | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const maxMb = Math.round(meta.max_file_size_bytes / (1024 * 1024));
  const tooBig = file != null && file.size > meta.max_file_size_bytes;
  const badExt = file != null && !meta.allowed_extensions.includes(file.name.split(".").pop()?.toLowerCase() || "");
  const error = tooBig || badExt;
  return (
    <Box>
      <input
        ref={inputRef}
        type="file"
        hidden
        accept={meta.allowed_extensions.map((e) => `.${e}`).join(",")}
        onChange={(e) => onPick(field.key, e.target.files?.[0] ?? null)}
      />
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
          <Button variant="outlined" size="small" onClick={() => inputRef.current?.click()}>
            انتخاب فایل
          </Button>
          <Typography variant="body2" sx={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }} noWrap>
            {field.label}
            {field.required && <Box component="span" sx={{ color: "primary.main" }}> *</Box>}
          </Typography>
        </Stack>
        {file && (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Typography variant="caption" color={error ? "error" : "text.secondary"} noWrap sx={{ maxWidth: 140 }}>
              {file.name} ({faNum(Math.ceil(file.size / 1024))} کیلوبایت)
            </Typography>
            <IconButton size="small" aria-label={`حذف فایل ${field.label}`} onClick={() => {
              if (inputRef.current) inputRef.current.value = "";
              onPick(field.key, null);
            }}>
              <ClearIcon />
            </IconButton>
          </Stack>
        )}
      </Stack>
      {tooBig && <FormHelperText error>حجم فایل بیش از {faNum(maxMb)} مگابایت است.</FormHelperText>}
      {badExt && <FormHelperText error>تنها PDF/JPG/JPEG/PNG مجاز است.</FormHelperText>}
    </Box>
  );
}

export default function FarakhanPage() {
  const [meta, setMeta] = useState<FarakhanMeta | null>(null);
  const [provinces, setProvinces] = useState<FarakhanLocationOption[]>([]);
  const [counties, setCounties] = useState<FarakhanLocationOption[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [captcha, setCaptcha] = useState<FarakhanCaptcha | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [trackingCode, setTrackingCode] = useState("");
  // فاز ۸۹ - نشست یک‌ساعتهٔ فرم + شمارش معکوس ثانیه‌ای
  const [sessionId, setSessionId] = useState("");
  const [deadline, setDeadline] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [expired, setExpired] = useState(false);
  // فاز ۹۳ — بازخورد زندهٔ کد ملی/تاریخ تولد زیر فیلد (قبل از submit) + نشان تکراری بودن
  const [liveErrors, setLiveErrors] = useState<Record<string, string>>({});
  const [ncDuplicate, setNcDuplicate] = useState(false);
  const [ncChecking, setNcChecking] = useState(false);

  const setLiveError = (label: string, message: string | null) => {
    setLiveErrors((prev) => {
      const next = { ...prev };
      if (message) next[label] = message;
      else delete next[label];
      return next;
    });
  };

  const loadCaptcha = useCallback(() => {
    setCaptcha(null);
    fetchFarakhanCaptcha()
      .then(setCaptcha)
      .catch(() => setErrorText("دریافت کپچا ناموفق بود؛ صفحه را دوباره باز کنید."));
  }, []);

  useEffect(() => {
    // فاز ۸۹ - اگر این تب قبلاً لینک را باز کرده، همان مهلت ادامه می‌یابد؛
    // در غیر این صورت نشست تازه از meta صادر و در sessionStorage ثبت می‌شود.
    const saved = readSavedSession();
    if (saved) {
      setSessionId(saved.sid);
      setDeadline(saved.deadline);
    }
    fetchFarakhanMeta().then((m) => {
      setMeta(m);
      if (!saved && m.session_id) {
        const dl = Date.now() + Math.max(60, m.session_ttl_seconds || 3600) * 1000;
        setSessionId(m.session_id);
        setDeadline(dl);
        try { sessionStorage.setItem(SESSION_KEY, JSON.stringify({ sid: m.session_id, deadline: dl })); } catch { /* بی‌اهمیت */ }
      }
    }).catch(() => setErrorText("دریافت اطلاعات فرم ناموفق بود."));
    fetchFarakhanProvinces()
      .then((items) => setProvinces(items))
      .catch(() => undefined);
    loadCaptcha();
  }, [loadCaptcha]);

  // فاز ۸۹ - شمارش معکوس ثانیه‌ای تا انقضای مهلت
  useEffect(() => {
    if (deadline == null) return undefined;
    const tick = () => {
      const rem = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      setRemaining(rem);
      if (rem <= 0) {
        setExpired(true);
        clearSavedSession();
      }
    };
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [deadline]);

  // شهرستان‌ها به‌ازای استان انتخاب‌شده
  useEffect(() => {
    if (!form.province_id) {
      setCounties([]);
      return;
    }
    fetchFarakhanCounties(Number(form.province_id))
      .then(setCounties)
      .catch(() => setCounties([]));
  }, [form.province_id]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const isMale = form.gender === "male";
  const selectedProvinceName = useMemo(
    () => provinces.find((p) => String(p.id) === String(form.province_id))?.name ?? "",
    [provinces, form.province_id],
  );

  // فاز ۹۳ — قواعد سن از سرور (meta) با مقادیر پیش‌فرض همان مقادیر سرور
  const minAge = meta?.rules?.min_age ?? FARAKHAN_MIN_AGE;
  const maxAge = meta?.rules?.max_age ?? FARAKHAN_MAX_AGE;
  // کف/سقف تقویم تولد: فقط بازهٔ مجاز سن ۱۸ تا ۸۰ سال قابل انتخاب است
  const birthBounds = useMemo(() => birthDateCalendarBounds(minAge, maxAge), [minAge, maxAge]);

  // فاز ۹۳ — بازخورد زندهٔ کد ملی هنگام خروج از فیلد: الگوریتم + تکراری بودن (endpoint عمومی)
  const onNationalCodeBlur = async () => {
    const raw = form.national_code.trim();
    if (!raw) {
      setNcDuplicate(false);
      setLiveError("کد ملی", null);
      return;
    }
    if (!/^\d{10}$/.test(normalizeFaDigits(raw))) return; // پیام تعداد رقم را clientValidate می‌دهد
    if (!isValidNationalCode(raw)) {
      setNcDuplicate(false);
      setLiveError("کد ملی", "کد ملی واردشده معتبر نیست (رقم کنترل الگوریتم کد ملی رعایت نشده است).");
      return;
    }
    setNcChecking(true);
    try {
      const res = await checkFarakhanNationalCode(normalizeFaDigits(raw));
      if (res.duplicate) {
        setNcDuplicate(true);
        setLiveError("کد ملی", "این کد ملی قبلاً در فراخوان همکاری ثبت شده است و ثبت تکراری امکان‌پذیر نیست.");
      } else {
        setNcDuplicate(false);
        setLiveError("کد ملی", null);
      }
    } finally {
      setNcChecking(false);
    }
  };

  const clientValidate = (): string => {
    if (expired) return "مهلت یک‌ساعتهٔ تکمیل فرم منقضی شده است؛ لطفاً فرم را از ابتدا شروع کنید.";
    if (!form.first_name.trim()) return "نام را وارد کنید.";
    if (!form.last_name.trim()) return "نام خانوادگی را وارد کنید.";
    if (!/^\d{10}$/.test(normalizeFaDigits(form.national_code.trim()))) return "کد ملی باید ۱۰ رقم باشد.";
    // فاز ۹۳ — الگوریتم کد ملی (جمع وزنی/رقم کنترل) پیش از ارسال به سرور
    if (!isValidNationalCode(form.national_code)) return "کد ملی واردشده معتبر نیست (رقم کنترل الگوریتم کد ملی رعایت نشده است).";
    // فاز ۹۳ — نشان تکراری بودن کد ملی (وارسی زندهٔ endpoint عمومی)
    if (ncDuplicate) return "این کد ملی قبلاً در فراخوان همکاری ثبت شده است و ثبت تکراری امکان‌پذیر نیست.";
    if (!form.gender) return "جنسیت را انتخاب کنید.";
    // فاز ۹۱ - تاریخ با تقویم شمسی انتخاب می‌شود؛ تایپ مستقیم نیست
    if (!/^\d{4}\/\d{2}\/\d{2}$/.test(form.birth_date.trim())) return "تاریخ تولد را از تقویم انتخاب کنید.";
    // فاز ۹۳ — محدودهٔ سن ثبت‌نام: حداقل ۱۸ و حداکثر ۸۰ سال (سن تکمیل‌شده)
    const age = completedAgeFromJalali(form.birth_date);
    if (age >= 0 && age < minAge) return `حداقل سن برای ثبت‌نام ${faNum(minAge)} سال است؛ تاریخ تولد انتخاب‌شده کمتر از ${faNum(minAge)} سال دارد.`;
    if (age >= 0 && age > maxAge) return `حداکثر سن برای ثبت‌نام ${faNum(maxAge)} سال است؛ تاریخ تولد انتخاب‌شده بیش از ${faNum(maxAge)} سال دارد.`;
    if (isMale && !form.military_status) return "وضعیت سربازی را برای متقاضی مرد انتخاب کنید.";
    if (!form.education_degree) return "مدرک تحصیلی را انتخاب کنید.";
    if (!form.education_field.trim()) return "رشته تحصیلی را وارد کنید.";
    if (!form.license_status) return "وضعیت پروانه را انتخاب کنید.";
    if (form.license_status === "valid" && !form.license_number?.trim()) return "شماره پروانه الزامی است.";
    if (!form.center_ownership) return "مالکیت مرکز را انتخاب کنید.";
    if (!selectedProvinceName) return "استان را انتخاب کنید.";
    if (!form.county_name) return "شهرستان را انتخاب کنید.";
    if (!form.phone.trim()) return "شماره تلفن ثابت را وارد کنید.";
    if (form.terms_accepted !== true) return "پذیرش قوانین و شرایط الزامی است.";
    if (!form.captcha_answer.trim()) return "پاسخ کپچا را وارد کنید.";
    return "";
  };

  // فاز ۹۲ - پیش‌آزمون فایل‌ها در مرورگر: پیش از بارگذاری سنگین، فایل اجباری
  // گم‌شده/حجم بیش از سقف/پسوند ممنوع را همان‌جا رد می‌کنیم تا کاربر ۳۵ مگابایت
  // را نفرستد و بعد با ۴۲۲ برگردد.
  const clientFileErrors = (): Record<string, string> => {
    const out: Record<string, string> = {};
    if (!meta) return out;
    for (const f of meta.file_fields) {
      const file = files[f.key];
      if (!file) {
        if (f.required) out[f.label] = "انتخاب این فایل الزامی است.";
        continue;
      }
      if (file.size > meta.max_file_size_bytes) {
        out[f.label] = `حجم فایل بیش از ${faNum(Math.ceil(meta.max_file_size_bytes / (1024 * 1024)))} مگابایت است.`;
        continue;
      }
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      if (!meta.allowed_extensions.includes(ext)) {
        out[f.label] = "تنها فایل‌های PDF و تصویری (JPG، JPEG، PNG) پذیرفته می‌شود.";
      }
    }
    return out;
  };

  // فاز ۹۲ - کلید خطای فایل سرور («files.national_id_card») به برچسب فارسی همان فیلد
  const fileErrorLabel = (key: string): string => {
    if (!key.startsWith("files.")) return key;
    const fk = key.slice("files.".length);
    return meta?.file_fields.find((f) => f.key === fk)?.label ?? fk;
  };

  const onSubmit = async () => {
    setErrorText("");
    setFieldErrors({});
    const clientError = clientValidate();
    const fileErrors = clientFileErrors();
    if (clientError || Object.keys(fileErrors).length > 0) {
      setFieldErrors(fileErrors);
      setErrorText(
        clientError
          || "فایل‌های ستاره‌دار الزامی را با حجم و قالب مجاز انتخاب کنید؛ جزئیات زیر هر فایل آمده است.",
      );
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const provinceRow = provinces.find((p) => String(p.id) === String(form.province_id));
    const payload = {
      first_name: form.first_name,
      last_name: form.last_name,
      national_code: form.national_code.trim(),
      gender: form.gender,
      birth_date: form.birth_date.trim(),
      military_status: isMale ? form.military_status : null,
      education_degree: form.education_degree,
      education_field: form.education_field,
      license_status: form.license_status,
      license_number: form.license_number || null,
      license_description: form.license_description || null,
      center_ownership: form.center_ownership,
      province_name: provinceRow?.name ?? "",
      county_name: form.county_name,
      phone: form.phone.trim(),
      mobile_number: form.mobile_number || null,
      postal_code: form.postal_code || null,
      address: form.address || null,
      individual_rooms: Number(form.individual_rooms) || 0,
      group_rooms: Number(form.group_rooms) || 0,
      child_rooms: Number(form.child_rooms) || 0,
      counselors_count: Number(form.counselors_count) || 0,
      has_waiting_space: form.has_waiting_space,
      accepts_company_pattern: form.accepts_company_pattern,
      has_accessibility: form.has_accessibility,
      terms_accepted: form.terms_accepted,
      captcha_id: captcha?.captcha_id ?? "",
      captcha_answer: form.captcha_answer.trim(),
      session_id: sessionId,
    };
    const pickedFiles: Record<string, File> = {};
    for (const [key, file] of Object.entries(files)) {
      if (file) pickedFiles[key] = file;
    }
    setSubmitting(true);
    try {
      const result = await submitFarakhan(payload, pickedFiles);
      setTrackingCode(result.tracking_code);
      clearSavedSession();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      // فاز ۹۱ - مدیریت کامل خطا: اعتبارسنجی روی فیلدها، سرور/شبکه با پیام روشن فارسی؛
      // دادهٔ فرم همیشه حفظ می‌شود و کپچا تازه می‌شود
      if (err instanceof FarakhanValidationError) {
        setFieldErrors(err.errors);
        const names = Object.keys(err.errors);
        const msgs = Object.values(err.errors).join(" ");
        // فاز ۹۲ - نشست سرور منقضی/گم‌شده (مثلاً ری‌استارت سرویس یا سقف یک ساعت):
        // به‌جای بن‌بست، نشست تازه از سرور گرفته می‌شود و کاربر فقط یک‌بار دیگر
        // «ذخیرهٔ فرم» را می‌زند؛ داده‌های فرم حفظ می‌شوند.
        if (msgs.includes("مهلت") || msgs.includes("نشست")) {
          try {
            const m = await fetchFarakhanMeta();
            const dl = Date.now() + Math.max(60, m.session_ttl_seconds || 3600) * 1000;
            setSessionId(m.session_id);
            setDeadline(dl);
            setExpired(false);
            try { sessionStorage.setItem(SESSION_KEY, JSON.stringify({ sid: m.session_id, deadline: dl })); } catch { /* بی‌اهمیت */ }
            setErrorText("نشست فرم تازه‌سازی شد؛ کپچای جدید را وارد کنید و دوباره «ذخیرهٔ فرم» را بزنید. اطلاعات شما حفظ شده است.");
          } catch {
            setErrorText("مهلت تکمیل فرم منقضی شده است؛ لطفاً صفحه را دوباره باز کنید.");
          }
          loadCaptcha();
          setForm((prev) => ({ ...prev, captcha_answer: "" }));
          window.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        setErrorText(
          names.length > 0
            ? `ثبت ناموفق بود؛ این موارد را اصلاح کنید: ${names.map(fileErrorLabel).join("، ")} — جزئیات هر فیلد زیر همان فیلد نمایش داده شده است.`
            : "ثبت فرم ناموفق بود؛ موارد اعلام‌شده را اصلاح کنید.",
        );
      } else if (err instanceof FarakhanServerError) {
        setFieldErrors({});
        // فاز ۹۲ - کد وضعیت HTTP در پیام می‌آید تا گزارش کاربر برای ریشه‌یابی کافی باشد
        setErrorText(err.status > 0 ? `${err.message} (کد خطا: ${err.status})` : err.message);
      } else {
        setFieldErrors({});
        setErrorText(err instanceof Error ? err.message : "خطا در ثبت فرم فراخوان");
      }
      loadCaptcha();
      setForm((prev) => ({ ...prev, captcha_answer: "" }));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSubmitting(false);
    }
  };

  if (trackingCode) {
    return (
      <Box>
        <Header />
        <Container maxWidth="sm" sx={{ py: { xs: 6, md: 10 }, minHeight: "60vh" }}>
          <Paper elevation={0} sx={{ border: "1px solid #f3dce2", borderRadius: 4, p: { xs: 3, md: 5 }, textAlign: "center" }}>
            <Typography variant="h4" fontWeight={800} color="primary.main" gutterBottom>
              ثبت‌نام شما انجام شد
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              اطلاعات فراخوان همکاری با موفقیت ذخیره شد. کد پیگیری شما برای پیگیری‌های بعدی:
            </Typography>
            <Box
              sx={{
                display: "inline-block", px: 4, py: 1.5, mb: 3, borderRadius: 3,
                background: "linear-gradient(135deg,#fdf3f5,#ffffff)", border: "1px dashed #d06b80",
                fontFamily: "monospace", fontSize: 24, fontWeight: 800, color: "primary.dark",
                letterSpacing: 1, direction: "ltr",
              }}
            >
              {trackingCode}
            </Box>
            <Typography variant="body2" color="text.secondary">
              کارشناسان ما پس از بررسی مدارک با شما تماس می‌گیرند. این کد را نزد خود نگه دارید.
            </Typography>
          </Paper>
        </Container>
        <Footer />
      </Box>
    );
  }

  // فاز ۹۳ — خطای زندهٔ زیر فیلد (کد ملی/تاریخ تولد) مقدم بر خطاهای submit است
  const err = (label: string): string | undefined => liveErrors?.[label] || fieldErrors?.[label];

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="md" sx={{ py: { xs: 4, md: 6 }, minHeight: "60vh" }}>
          <Typography variant="h3" fontWeight={800} color="primary.main" textAlign="center">
            فراخوان همکاری
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ mb: 4 }}>
            فرم ثبت‌نام همکاری مراکز مشاوره و روان‌شناسان — لطفاً همهٔ بخش‌ها را با دقت تکمیل کنید.
            فیلدهای ستاره‌دار الزامی‌اند.
          </Typography>

          {/* فاز ۹۴ — جدول عمومی افراد ثبت‌نام‌شده + شمارندهٔ «تعداد ثبت‌شده‌ها» */}
          <Box sx={{ mb: 4 }}>
            <RegisteredPeopleCard />
          </Box>

          {/* فاز ۸۹ - شمارش معکوس یک‌ساعته: از لحظهٔ ورود به صفحه، یک ساعت فرصت تکمیل و ذخیره */}
          {(deadline !== null || expired) && (
            <Alert
              severity={expired ? "error" : remaining <= 300 ? "warning" : "info"}
              icon={<TimerIcon />}
              sx={{ mb: 3, "& .MuiAlert-message": { width: "100%" } }}
            >
              {expired ? (
                <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" justifyContent="space-between">
                  <Typography variant="body2">
                    مهلت یک‌ساعتهٔ تکمیل فرم منقضی شد. برای ثبت‌نام باید فرم را از ابتدا شروع کنید.
                  </Typography>
                  <Button size="small" variant="outlined"
                    onClick={() => { clearSavedSession(); window.location.reload(); }}>
                    شروع دوباره
                  </Button>
                </Stack>
              ) : (
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" justifyContent="space-between">
                  <Typography variant="body2">
                    برای تکمیل و ذخیرهٔ این فرم یک ساعت فرصت دارید؛ پس از آن مهلت منقضی می‌شود و فرم باید از ابتدا پر شود.
                  </Typography>
                  <Box
                    sx={{
                      fontFamily: "monospace", fontSize: 22, fontWeight: 800, direction: "ltr",
                      color: remaining <= 300 ? "warning.dark" : "primary.dark",
                      px: 1.5, py: 0.25, borderRadius: 2,
                      background: "#fbf7f4", border: "1px solid #f3dce2",
                    }}
                    role="timer" aria-label="زمان باقی‌مانده برای تکمیل فرم"
                  >
                    {faClock(remaining)}
                  </Box>
                </Stack>
              )}
            </Alert>
          )}

          {errorText && (
            <Alert severity="error" sx={{ mb: 3 }} onClose={() => setErrorText("")}>
              {errorText}
            </Alert>
          )}
          {Object.keys(fieldErrors).length > 0 && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              <Stack spacing={0.5}>
                {Object.entries(fieldErrors).map(([label, message]) => (
                  // فاز ۹۲ - کلیدهای «files.*» سرور به برچسب فارسی فیلد فایل نقشه می‌شوند
                  <Typography key={label} variant="body2">• <b>{fileErrorLabel(label)}:</b> {message}</Typography>
                ))}
                <Typography variant="caption" color="text.secondary">
                  اطلاعات واردشدهٔ شما حفظ شده است؛ فقط موارد بالا را اصلاح کنید و دوباره ذخیره کنید.
                </Typography>
              </Stack>
            </Alert>
          )}

          {meta === null ? (
            <Stack alignItems="center" py={8} role="status" aria-label="در حال بارگذاری فرم">
              <CircularProgress sx={{ color: "primary.main" }} />
            </Stack>
          ) : (
            /* فاز ۸۹ - با انقضای مهلت، همهٔ ورودی‌های فرم یکجا غیرفعال می‌شوند */
            <fieldset disabled={expired} style={{ border: "none", margin: 0, padding: 0, minWidth: 0 }}>
            <Stack spacing={3}>
              {/* ── بخش ۱: مشخصات فردی ── */}
              <SectionCard title="۱. مشخصات فردی">
                <Grid container spacing={2.5}>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth required size="small" label="نام" value={form.first_name}
                      error={!!err("نام")} helperText={err("نام")}
                      onChange={(e) => set("first_name", e.target.value)} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth required size="small" label="نام خانوادگی" value={form.last_name}
                      error={!!err("نام خانوادگی")} helperText={err("نام خانوادگی")}
                      onChange={(e) => set("last_name", e.target.value)} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    {/* فاز ۹۳ — کد ملی: الگوریتم + تکراری بودن با بازخورد زنده */}
                    <TextField fullWidth required size="small" label="کد ملی" value={form.national_code}
                      inputProps={{ inputMode: "numeric", maxLength: 10, dir: "ltr" }}
                      error={!!err("کد ملی")}
                      helperText={err("کد ملی") ?? (ncChecking ? "در حال بررسی تکراری بودن…" : "۱۰ رقم بدون خط تیره — رقم کنترل الگوریتم بررسی می‌شود")}
                      onChange={(e) => {
                        set("national_code", e.target.value);
                        setNcDuplicate(false);
                        setLiveError("کد ملی", null);
                      }}
                      onBlur={onNationalCodeBlur} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("جنسیت")}>
                      <InputLabel>جنسیت</InputLabel>
                      <Select value={form.gender} label="جنسیت" onChange={(e) => set("gender", e.target.value)}>
                        {meta.genders.map((g) => (
                          <MenuItem key={g.value} value={g.value}>{g.label}</MenuItem>
                        ))}
                      </Select>
                      {err("جنسیت") && <FormHelperText>{err("جنسیت")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    {/* فاز ۹۱ - تاریخ تولد شمسی با تقویم؛ تایپ مستقیم ممنوع */}
                    {/* فاز ۹۳ - تقویم فقط بازهٔ سن مجاز (۱۸ تا ۸۰ سال) را می‌دهد */}
                    <JalaliDatePicker
                      label="تاریخ تولد (شمسی)"
                      value={form.birth_date}
                      onChange={(v) => {
                        set("birth_date", v);
                        const pickedAge = v ? completedAgeFromJalali(v) : -1;
                        if (pickedAge >= 0 && pickedAge < minAge) {
                          setLiveError("تاریخ تولد", `حداقل سن برای ثبت‌نام ${faNum(minAge)} سال است.`);
                        } else if (pickedAge >= 0 && pickedAge > maxAge) {
                          setLiveError("تاریخ تولد", `حداکثر سن برای ثبت‌نام ${faNum(maxAge)} سال است.`);
                        } else {
                          setLiveError("تاریخ تولد", null);
                        }
                      }}
                      required
                      minJalali={birthBounds.minJalali}
                      maxJalali={birthBounds.maxJalali}
                      rangeHint={`بازهٔ مجاز سن: ${faNum(minAge)} تا ${faNum(maxAge)} سال — تاریخ خارج از این بازه قابل انتخاب نیست`}
                      error={!!err("تاریخ تولد")}
                      helperText={err("تاریخ تولد") ?? `انتخاب از تقویم شمسی — سن مجاز: ${faNum(minAge)} تا ${faNum(maxAge)} سال`}
                    />
                  </Grid>
                  {isMale && (
                    <Grid item xs={12} sm={6}>
                      <FormControl fullWidth required size="small" error={!!err("وضعیت سربازی")}>
                        <InputLabel>وضعیت سربازی</InputLabel>
                        <Select value={form.military_status} label="وضعیت سربازی"
                          onChange={(e) => set("military_status", e.target.value)}>
                          {meta.military_status_options.map((m) => (
                            <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>
                          ))}
                        </Select>
                        {err("وضعیت سربازی") && <FormHelperText>{err("وضعیت سربازی")}</FormHelperText>}
                      </FormControl>
                    </Grid>
                  )}
                </Grid>
              </SectionCard>

              {/* ── بخش ۲: تحصیلات و پروانه ── */}
              <SectionCard title="۲. تحصیلات و پروانه فعالیت">
                <Grid container spacing={2.5}>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("مدرک تحصیلی")}>
                      <InputLabel>مدرک تحصیلی</InputLabel>
                      <Select value={form.education_degree} label="مدرک تحصیلی"
                        onChange={(e) => set("education_degree", e.target.value)}>
                        {meta.education_degrees.map((d) => (
                          <MenuItem key={d.value} value={d.value}>{d.label}</MenuItem>
                        ))}
                      </Select>
                      {err("مدرک تحصیلی") && <FormHelperText>{err("مدرک تحصیلی")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth required size="small" label="رشته تحصیلی" value={form.education_field}
                      error={!!err("رشته تحصیلی")} helperText={err("رشته تحصیلی")}
                      onChange={(e) => set("education_field", e.target.value)} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("وضعیت پروانه")}>
                      <InputLabel>وضعیت پروانهٔ مرکز</InputLabel>
                      <Select value={form.license_status} label="وضعیت پروانهٔ مرکز"
                        onChange={(e) => set("license_status", e.target.value)}>
                        {meta.license_status_options.map((l) => (
                          <MenuItem key={l.value} value={l.value}>{l.label}</MenuItem>
                        ))}
                      </Select>
                      {err("وضعیت پروانه") && <FormHelperText>{err("وضعیت پروانه")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  {form.license_status === "valid" && (
                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth required size="small" label="شماره پروانه" value={form.license_number ?? ""}
                        inputProps={{ dir: "ltr" }}
                        error={!!err("شماره پروانه")} helperText={err("شماره پروانه")}
                        onChange={(e) => set("license_number", e.target.value)} />
                    </Grid>
                  )}
                  <Grid item xs={12}>
                    <TextField fullWidth multiline minRows={2} size="small"
                      label="توضیحات پروانه (اختیاری)" value={form.license_description ?? ""}
                      error={!!err("توضیحات پروانه")} helperText={err("توضیحات پروانه")}
                      onChange={(e) => set("license_description", e.target.value)} />
                  </Grid>
                </Grid>
              </SectionCard>

              {/* ── بخش ۳: مرکز ── */}
              <SectionCard title="۳. مشخصات مرکز">
                <Grid container spacing={2.5}>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("مالکیت مرکز")}>
                      <InputLabel>مالکیت مرکز</InputLabel>
                      <Select value={form.center_ownership} label="مالکیت مرکز"
                        onChange={(e) => set("center_ownership", e.target.value)}>
                        {meta.center_ownership_options.map((o) => (
                          <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                        ))}
                      </Select>
                      {err("مالکیت مرکز") && <FormHelperText>{err("مالکیت مرکز")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("استان")}>
                      <InputLabel>استان</InputLabel>
                      <Select value={form.province_id} label="استان"
                        onChange={(e) => { set("province_id", e.target.value); set("county_name", ""); }}>
                        {provinces.map((p) => (
                          <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                        ))}
                      </Select>
                      {err("استان") && <FormHelperText>{err("استان")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth required size="small" error={!!err("شهرستان")} disabled={!form.province_id}>
                      <InputLabel>شهرستان</InputLabel>
                      <Select value={form.county_name} label="شهرستان"
                        onChange={(e) => set("county_name", e.target.value)}>
                        {counties.map((c) => (
                          <MenuItem key={c.id} value={c.name}>{c.name}</MenuItem>
                        ))}
                      </Select>
                      {err("شهرستان") && <FormHelperText>{err("شهرستان")}</FormHelperText>}
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth size="small" label="کدپستی (اختیاری)" value={form.postal_code ?? ""}
                      inputProps={{ inputMode: "numeric", maxLength: 10, dir: "ltr" }}
                      error={!!err("کدپستی")} helperText={err("کدپستی") || "۱۰ رقم"}
                      onChange={(e) => set("postal_code", e.target.value)} />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField fullWidth multiline minRows={2} size="small" label="نشانی مرکز (اختیاری)"
                      value={form.address ?? ""}
                      error={!!err("نشانی")} helperText={err("نشانی")}
                      onChange={(e) => set("address", e.target.value)} />
                  </Grid>
                </Grid>
              </SectionCard>

              {/* ── بخش ۴: تماس ── */}
              <SectionCard title="۴. اطلاعات تماس">
                <Grid container spacing={2.5}>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth required size="small" label="تلفن ثابت" placeholder="02112345678"
                      value={form.phone} inputProps={{ inputMode: "tel", dir: "ltr", maxLength: 15 }}
                      error={!!err("تلفن ثابت")} helperText={err("تلفن ثابت") || "با کد شهر — مثال 02112345678"}
                      onChange={(e) => set("phone", e.target.value)} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField fullWidth size="small" label="شماره همراه (اختیاری)" placeholder="09123456789"
                      value={form.mobile_number ?? ""} inputProps={{ inputMode: "tel", dir: "ltr", maxLength: 15 }}
                      error={!!err("شماره همراه")} helperText={err("شماره همراه")}
                      onChange={(e) => set("mobile_number", e.target.value)} />
                  </Grid>
                </Grid>
              </SectionCard>

              {/* ── بخش ۵: ظرفیت و امکانات ── */}
              <SectionCard title="۵. ظرفیت مرکز">
                <Grid container spacing={2.5}>
                  <Grid item xs={6} sm={3}>
                    <TextField fullWidth size="small" type="number" label="اتاق انفرادی" value={form.individual_rooms}
                      inputProps={{ min: 0, dir: "ltr" }}
                      error={!!err("اتاق انفرادی")} onChange={(e) => set("individual_rooms", Number(e.target.value || 0))} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField fullWidth size="small" type="number" label="اتاق گروهی" value={form.group_rooms}
                      inputProps={{ min: 0, dir: "ltr" }}
                      error={!!err("اتاق گروهی")} onChange={(e) => set("group_rooms", Number(e.target.value || 0))} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField fullWidth size="small" type="number" label="اتاق کودک" value={form.child_rooms}
                      inputProps={{ min: 0, dir: "ltr" }}
                      error={!!err("اتاق کودک")} onChange={(e) => set("child_rooms", Number(e.target.value || 0))} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField fullWidth size="small" type="number" label="تعداد مشاوران" value={form.counselors_count}
                      inputProps={{ min: 0, dir: "ltr" }}
                      error={!!err("تعداد مشاوران")} onChange={(e) => set("counselors_count", Number(e.target.value || 0))} />
                  </Grid>
                  <Grid item xs={12}>
                    <Stack divider={<Divider flexItem />} sx={{ borderTop: "1px solid #f3dce2", borderBottom: "1px solid #f3dce2" }}>
                      <FormControlLabel sx={{ py: 1 }}
                        control={<Switch checked={form.has_waiting_space} onChange={(e) => set("has_waiting_space", e.target.checked)} />}
                        label="فضای انتظار مناسب دارد" />
                      <FormControlLabel sx={{ py: 1 }}
                        control={<Switch checked={form.accepts_company_pattern} onChange={(e) => set("accepts_company_pattern", e.target.checked)} />}
                        label="الگوی شرکت‌ها را می‌پذیرد" />
                      <FormControlLabel sx={{ py: 1 }}
                        control={<Switch checked={form.has_accessibility} onChange={(e) => set("has_accessibility", e.target.checked)} />}
                        label="دسترسی‌پذیری افراد با معلولیت دارد" />
                    </Stack>
                  </Grid>
                </Grid>
              </SectionCard>

              {/* ── بخش ۶: فایل‌ها ── */}
              <SectionCard title="۶. بارگذاری مدارک"
                subtitle={`فایل‌های PDF یا تصویری — حداکثر ${faNum(Math.round(meta.max_file_size_bytes / (1024 * 1024)))} مگابایت هر فایل و ${faNum(meta.max_files)} فایل`}>
                <Stack spacing={1.5}>
                  {meta.file_fields.map((f) => (
                    <FilePicker key={f.key} field={f} meta={meta} file={files[f.key] ?? null}
                      onPick={(key, file) => setFiles((prev) => ({ ...prev, [key]: file }))} />
                  ))}
                </Stack>
              </SectionCard>

              {/* ── بخش ۷: قوانین + کپچا + ثبت ── */}
              <SectionCard title="۷. قوانین و ثبت نهایی">
                <Stack spacing={2.5}>
                  <FormControlLabel
                    control={<Checkbox checked={form.terms_accepted} onChange={(e) => set("terms_accepted", e.target.checked)} />}
                    label={(
                      <Typography variant="body2">
                        قوانین و شرایط همکاری را می‌پذیرم و صحت اطلاعات واردشده را تأیید می‌کنم.
                      </Typography>
                    )}
                  />
                  {err("پذیرش قوانین") && <FormHelperText error>{err("پذیرش قوانین")}</FormHelperText>}

                  <Divider />

                  <Box>
                    <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
                      کپچای امنیتی — حاصل‌جمع دو عدد را وارد کنید
                    </Typography>
                    <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
                      <Paper
                        elevation={0}
                        sx={{ border: "1px solid #e5e7f0", borderRadius: 2, p: 0.5, bgcolor: "#fff" }}
                        aria-label="تصویر کپچای محاسبهٔ دو عدد"
                      >
                        {captcha ? (
                          <img
                            src={`data:image/svg+xml;utf8,${encodeURIComponent(captcha.svg)}`}
                            alt="کپچا: حاصل‌جمع دو عدد"
                            width={190}
                            height={54}
                            style={{ display: "block" }}
                          />
                        ) : (
                          <Box sx={{ width: 190, height: 54, display: "grid", placeItems: "center" }}>
                            <CircularProgress size={22} sx={{ color: "primary.main" }} />
                          </Box>
                        )}
                      </Paper>
                      <IconButton onClick={loadCaptcha} aria-label="کپچای تازه" title="کپچای تازه">
                        <RefreshIcon />
                      </IconButton>
                      <TextField
                        size="small" label="پاسخ" value={form.captcha_answer}
                        inputProps={{ inputMode: "numeric", maxLength: 4, dir: "ltr", style: { width: 90 } }}
                        error={!!err("کپچا")}
                        helperText={err("کپچا") || "مثال: ۷۷"}
                        onChange={(e) => set("captcha_answer", e.target.value)}
                      />
                    </Stack>
                  </Box>

                  <Button
                    variant="contained"
                    size="large"
                    disabled={submitting || captcha === null || expired}
                    onClick={onSubmit}
                    sx={{ alignSelf: "flex-start", px: 6 }}
                  >
                    {submitting ? "در حال ثبت…" : "ذخیرهٔ فرم"}
                  </Button>
                </Stack>
              </SectionCard>
            </Stack>
            </fieldset>
          )}
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
