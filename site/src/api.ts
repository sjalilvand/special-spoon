export interface PublicCounselor {
  id: string;
  name: string;
  professional_title: string | null;
  specialty: string | null;
  photo_url: string | null;
  /** فاز ۶۷: استان/شعبهٔ مشاور برای فیلتر فهرست رزرو بر اساس استان */
  province_code: string | null;
  province_name: string | null;
  branch_name: string | null;
  /** فاز ۶۹: امتیاز میانگین (۱..۵، بدون نظر = null) + تعداد نظرات */
  rating_avg: number | null;
  review_count: number;
}

export interface SlotDay {
  date: string;
  slots: { start_at: string; label: string }[];
}

export interface BookingResult {
  status: string;
  request_id: string;
  /** فاز ۶۹ - اگر پرداخت آنلاین درخواست شده باشد */
  payment?: BookingPayment;
  payment_error?: string;
}

export async function fetchPublicCounselors(): Promise<PublicCounselor[]> {
  const r = await fetch("/api/v1/public/counselors");
  if (!r.ok) throw new Error("خطا در دریافت مشاوران");
  return (await r.json()).items as PublicCounselor[];
}

export async function fetchBookingSlots(counselorId: string): Promise<SlotDay[]> {
  const r = await fetch(`/api/v1/public/booking/slots?counselor_id=${encodeURIComponent(counselorId)}`);
  if (!r.ok) throw new Error("خطا در دریافت نوبت‌های آزاد");
  return (await r.json()).days as SlotDay[];
}

export async function postConsultation(payload: Record<string, unknown>): Promise<BookingResult> {
  const r = await fetch("/api/v1/public/consultation-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "خطا در ارسال درخواست");
  }
  return (await r.json()) as BookingResult;
}

// ---------------- فاز ۲۶ - نگهداشت موقت اسلات (B09) ----------------

export interface BookingHold {
  hold_id: string;
  hold_token: string;
  expires_at: string;
  remaining_seconds: number;
  counselor: { id: string; name: string };
  start_at: string;
  hold_minutes: number;
}

export interface HoldStatus {
  status: "active" | "confirmed" | "released" | "expired";
  remaining_seconds: number;
  expires_at: string;
  start_at: string;
  counselor_name: string | null;
}

export async function createBookingHold(counselorId: string, startAt: string): Promise<BookingHold> {
  const r = await fetch("/api/v1/public/booking-holds", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ counselor_id: counselorId, start_at: startAt }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "خطا در نگهداشت نوبت");
  }
  return (await r.json()) as BookingHold;
}

export async function fetchBookingHold(token: string): Promise<HoldStatus> {
  const r = await fetch(`/api/v1/public/booking-holds/${encodeURIComponent(token)}`);
  if (!r.ok) throw new Error("خطا در بررسی وضعیت نگهداشت");
  return (await r.json()) as HoldStatus;
}

export async function releaseBookingHold(token: string): Promise<void> {
  await fetch(`/api/v1/public/booking-holds/${encodeURIComponent(token)}`, { method: "DELETE" }).catch(() => undefined);
}

// ---------------- فاز ۲۶ - کد یک‌بارمصرف (B02-lite) ----------------

export interface OtpRequestResult {
  status: string;
  expires_in: number;
  dev_code?: string;
  dev_notice?: string;
}

export async function requestOtp(mobile: string): Promise<OtpRequestResult> {
  const r = await fetch("/api/v1/auth/otp/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mobile, purpose: "booking" }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "خطا در ارسال کد تأیید");
  }
  return (await r.json()) as OtpRequestResult;
}

export async function verifyOtp(mobile: string, code: string): Promise<{ verify_token: string }> {
  const r = await fetch("/api/v1/auth/otp/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mobile, code, purpose: "booking" }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "کد تأیید نامعتبر است");
  }
  return (await r.json()) as { verify_token: string };
}
// ---------------- فاز ۶۶ - نقشهٔ کلینیک‌های شرکت رز ----------------

export interface MapCounselor {
  id: string;
  name: string;
  degree: string | null;
  license: string | null;
  /** فاز ۶۷: موبایل/رتبه از خروجی عمومی حذف شد؛ پرچم واجد شرط رزرو (B05) */
  bookable: boolean;
  /** فاز ۶۹: امتیاز برای نمایش ستاره‌ها و مرتب‌سازی «بالاترین امتیاز اول» */
  rating_avg?: number | null;
  review_count?: number;
}

export interface MapClinic {
  id: string;
  name: string;
  clinic_name: string | null;
  province_code: string | null;
  province: string | null;
  city: string | null;
  address: string | null;
  postal_code: string | null;
  phone: string | null;
  manager_name: string | null;
  manager_phone: string | null;
  exec_name: string | null;
  exec_phone: string | null;
  working_hours: string | null;
  latitude: number | null;
  longitude: number | null;
  map_url: string | null;
  counselor_count: number;
  counselors: MapCounselor[];
}

export async function fetchClinicsMap(): Promise<MapClinic[]> {
  const r = await fetch("/api/v1/public/clinics-map");
  if (!r.ok) throw new Error("خطا در دریافت کلینیک‌ها");
  return (await r.json()).items as MapClinic[];
}

// ---------------- فاز ۶۹ - پرداخت آنلاین رزرو + امتیازدهی مشاوران ----------------

export interface BookingPayment {
  redirect_url: string;
  authority: string;
  gateway: string;
  order_number: string;
  amount: number;
  currency: string;
}

export interface PublicService {
  id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  session_type: string;
  price_amount: number | null;
  price_currency: string | null;
}

export interface CounselorReviewItem {
  id: string;
  rating: number;
  comment: string | null;
  author: string;
  created_at: string | null;
}

export interface CounselorReviewsResponse {
  items: CounselorReviewItem[];
  summary: {
    rating_avg: number | null;
    review_count: number;
    breakdown: Record<string, number>;
  };
}

export async function fetchPublicCounselor(id: string): Promise<PublicCounselor & { degree: string | null }> {
  const r = await fetch(`/api/v1/public/counselors/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error("مشاور یافت نشد یا فعال نیست");
  return (await r.json()) as PublicCounselor & { degree: string | null };
}

export async function fetchPublicServices(): Promise<PublicService[]> {
  const r = await fetch("/api/v1/public/services");
  if (!r.ok) throw new Error("خطا در دریافت خدمات");
  return (await r.json()).items as PublicService[];
}

export async function fetchCounselorReviews(id: string): Promise<CounselorReviewsResponse> {
  const r = await fetch(`/api/v1/public/counselors/${encodeURIComponent(id)}/reviews`);
  if (!r.ok) throw new Error("خطا در دریافت نظرات");
  return (await r.json()) as CounselorReviewsResponse;
}

export async function postCounselorReview(
  counselorId: string,
  payload: { review_token: string; rating: number; comment?: string },
): Promise<void> {
  const r = await fetch(`/api/v1/public/counselors/${encodeURIComponent(counselorId)}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "خطا در ثبت نظر");
  }
}

// ---------------- فاز ۸۸ - فراخوان همکاری (پورت فرم مرجع farakhan) ----------------

export interface FarakhanOption {
  value: string;
  label: string;
}

export interface FarakhanFileField {
  key: string;
  label: string;
  required: boolean;
}

export interface FarakhanMeta {
  genders: FarakhanOption[];
  military_status_options: FarakhanOption[];
  education_degrees: FarakhanOption[];
  license_status_options: FarakhanOption[];
  center_ownership_options: FarakhanOption[];
  file_fields: FarakhanFileField[];
  allowed_extensions: string[];
  max_file_size_bytes: number;
  max_files: number;
  /** فاز ۹۳ — قواعد اعتبارسنجی منتشرشدهٔ سرور (محدودهٔ سن + الگوریتم کد ملی) */
  rules: {
    require_military_status_for_male: boolean;
    phone_required: boolean;
    min_age?: number;
    max_age?: number;
    national_code_checksum?: boolean;
  };
  /** فاز ۸۹ - نشست یک‌ساعتهٔ فرم: شناسهٔ نشست + طول مهلت (ثانیه) برای شمارش معکوس */
  session_id: string;
  session_ttl_seconds: number;
}

export interface FarakhanCaptcha {
  captcha_id: string;
  svg: string;
  ttl_seconds: number;
}

/** فاز ۹۴ - یک ردیف جدول عمومی «افراد ثبت‌نام‌شدهٔ فراخوان» (کمترین دادهٔ شخصی) */
export interface FarakhanPublicRow {
  name: string;
  province_name: string;
  county_name: string;
  education_degree_label: string;
  created_at: string | null;
}

export interface FarakhanPublicList {
  items: FarakhanPublicRow[];
  total: number;
}

/** فاز ۹۴ - فهرست عمومی ثبت‌نام‌شده‌های فراخوان (بدون ورود؛ سقف نرخ ۱۲۰/ساعت/IP) */
export async function fetchFarakhanPublicSubmissions(): Promise<FarakhanPublicList> {
  const r = await fetch("/api/v1/farakhan/public/submissions");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FarakhanPublicList;
}


/** خطای اعتبارسنجی فراخوان: نقشهٔ «برچسب فارسی فیلد → پیام» */
export class FarakhanValidationError extends Error {
  errors: Record<string, string>;
  constructor(message: string, errors: Record<string, string>) {
    super(message);
    this.errors = errors;
  }
}

/** فاز ۹۱ - خطای سرور/شبکه: پیام فارسی روشن + اینکه ثبت انجام نشده و داده محفوظ است */
export class FarakhanServerError extends Error {
  status: number;
  kind: string;
  constructor(message: string, status: number, kind = "server") {
    super(message);
    this.status = status;
    this.kind = kind;
  }
}

export async function fetchFarakhanMeta(): Promise<FarakhanMeta> {
  const r = await fetch("/api/v1/farakhan/meta");
  if (!r.ok) throw new Error("خطا در دریافت اطلاعات فرم فراخوان");
  return (await r.json()) as FarakhanMeta;
}

export async function fetchFarakhanCaptcha(): Promise<FarakhanCaptcha> {
  const r = await fetch("/api/v1/farakhan/captcha");
  if (!r.ok) throw new Error("خطا در دریافت کپچا");
  return (await r.json()) as FarakhanCaptcha;
}

export interface FarakhanLocationOption {
  id: number;
  name: string;
}

export async function fetchFarakhanProvinces(): Promise<FarakhanLocationOption[]> {
  const r = await fetch("/api/v1/farakhan/provinces");
  if (!r.ok) throw new Error("خطا در دریافت استان‌ها");
  return (await r.json()).items as FarakhanLocationOption[];
}

export async function fetchFarakhanCounties(provinceId: number): Promise<FarakhanLocationOption[]> {
  const r = await fetch(`/api/v1/farakhan/provinces/${encodeURIComponent(String(provinceId))}/counties`);
  if (!r.ok) return [];
  return (await r.json()).items as FarakhanLocationOption[];
}

export interface FarakhanSubmitResult {
  success: boolean;
  tracking_code: string;
  message: string;
}

export interface FarakhanNationalCodeCheck {
  valid: boolean;
  duplicate: boolean;
}

/**
 * فاز ۹۳ — وارسی زندهٔ کد ملی (الگوریتم + تکراری بودن) هنگام خروج از فیلد.
 * fail-open: خطای شبکه/سرور فرم را بلاک نمی‌کند — سرور در لحظهٔ ثبت همان را
 * کامل و نهایی بررسی می‌کند.
 */
export async function checkFarakhanNationalCode(code: string): Promise<FarakhanNationalCodeCheck> {
  try {
    const r = await fetch(`/api/v1/farakhan/check-national-code?code=${encodeURIComponent(code)}`);
    if (!r.ok) return { valid: true, duplicate: false };
    const d = (await r.json()) as FarakhanNationalCodeCheck;
    return { valid: d.valid !== false, duplicate: d.duplicate === true };
  } catch {
    return { valid: true, duplicate: false };
  }
}

export async function submitFarakhan(payload: Record<string, unknown>, files: Record<string, File>): Promise<FarakhanSubmitResult> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(payload));
  for (const [key, file] of Object.entries(files)) {
    if (file) fd.append(key, file, file.name);
  }
  let r: Response;
  try {
    r = await fetch("/api/v1/farakhan/submissions", { method: "POST", body: fd });
  } catch {
    // فاز ۹۱ - قطع شبکه/قطع بدنه در میانهٔ بارگذاری (پروکسی/فایروال) — پیام روشن فارسی
    throw _farakhanNetworkError();
  }
  // فاز ۹۵ - مسیر پشتیبان ثبت: دامنهٔ رسمی پشت CDN است؛ CDN بدنهٔ multipart را در
  // میانهٔ ارسال می‌شکند (IncompleteRead) و پاسخِ غیر-۲xx را با صفحهٔ HTML خودش
  // جایگزین می‌کند. اگر پاسخ مسیر اصلی «JSON سالم» نبود، ثبت یک‌بار مستقیم از
  // مبدأ اصلی (IP سرور — VITE_API_FALLBACK_BASE) دوباره تلاش می‌شود؛ پاسخ همان
  // مسیر پشتیبان (موفق یا خطای اعتبارسنجی واقعی) ملاک است. اگر ثبت اول در واقعیت
  // رسیده باشد، مسیر پشتیبان «کد ملی تکراری» می‌دهد و فرم همان پیام را نشان می‌دهد.
  if (_farakhanFallbackUsable() && !(r.ok && _farakhanIsJson(r))) {
    try {
      const r2 = await fetch(`${FARAKHAN_FALLBACK_BASE}/api/v1/farakhan/submissions`, { method: "POST", body: fd });
      if (_farakhanIsJson(r2)) return await _farakhanParseSubmitResponse(r2);
    } catch {
      // مسیر پشتیبان هم در دسترس نیست — به پیام‌های مسیر اصلی برمی‌گردیم
    }
  }
  return await _farakhanParseSubmitResponse(r);
}

/** فاز ۹۵ — مبدأ پشتیبان ثبت فراخوان: وقتی سایت از مبدأ دیگری (دامنهٔ پشت CDN) سرو
 * می‌شود، ثبت می‌تواند مستقیم از IP سرور دوباره تلاش کند؛ خالی = بدون مسیر پشتیبان. */
const FARAKHAN_FALLBACK_BASE = (import.meta.env.VITE_API_FALLBACK_BASE ?? "").trim();

function _farakhanFallbackUsable(): boolean {
  if (!FARAKHAN_FALLBACK_BASE) return false;
  try {
    return window.location.origin !== new URL(FARAKHAN_FALLBACK_BASE).origin;
  } catch {
    return true;
  }
}

function _farakhanIsJson(r: Response): boolean {
  return (r.headers.get("content-type") ?? "").toLowerCase().includes("application/json");
}

function _farakhanNetworkError(): FarakhanServerError {
  return new FarakhanServerError(
    "ارتباط با سرور در میانهٔ ارسال قطع شد؛ اطلاعات شما ذخیره نشده است. حجم فایل‌ها را کمتر کنید یا بعد از بررسی اینترنت دوباره «ذخیرهٔ فرم» را بزنید.",
    0,
    "network",
  );
}

/** فاز ۹۵ — تحلیل پاسخ ثبت: خطای ساخت‌یافته (۴۲۲/۵۰۰ با detail.errors) یا پیام‌های
 * عمومی؛ پاسخ غیر-JSON (صفحهٔ خطای CDN) با پیام فارسی روشن رد می‌شود. */
async function _farakhanParseSubmitResponse(r: Response): Promise<FarakhanSubmitResult> {
  if (!r.ok) {
    // فاز ۹۱ - بدنهٔ خطا ممکن است ناقص برسد؛ بدون json سقوط نمی‌کنیم
    const d = _farakhanIsJson(r) ? await r.json().catch(() => null) : null;
    const detail = d && typeof d === "object" ? (d as { detail?: unknown }).detail : null;
    if (detail && typeof detail === "object" && (detail as { errors?: unknown }).errors) {
      const dt = detail as { message?: string; errors?: Record<string, string> };
      if (r.status >= 500) {
        throw new FarakhanServerError(dt.message || "در ذخیره‌سازی فرم خطای سرور رخ داد؛ لطفاً دوباره تلاش کنید.", r.status, "server");
      }
      throw new FarakhanValidationError(
        dt.message || "اعتبارسنجی اطلاعات ناموفق بود.",
        dt.errors as Record<string, string>,
      );
    }
    if (typeof detail === "string" && detail.trim()) {
      throw r.status >= 500
        ? new FarakhanServerError(detail, r.status)
        : new FarakhanValidationError(detail, {});
    }
    if (r.status === 429) {
      throw new FarakhanServerError("تعداد تلاش‌های ثبت زیاد است؛ چند دقیقه بعد دوباره تلاش کنید.", 429, "rate");
    }
    if (r.status === 413) {
      throw new FarakhanServerError("حجم مجموع فایل‌های ارسالی بیش از حد مجاز سرور است؛ یک یا چند فایل را کوچک‌تر کنید.", 413, "size");
    }
    throw new FarakhanServerError(
      r.status >= 500
        ? "خطای سرور در ذخیره‌سازی فرم؛ لطفاً چند لحظه بعد دوباره تلاش کنید. اگر تکرار شد با پشتیبانی تماس بگیرید."
        : "ثبت فرم ناموفق بود؛ دوباره تلاش کنید.",
      r.status,
    );
  }
  if (!_farakhanIsJson(r)) {
    // فاز ۹۵ - پاسخ ۲xx با بدنهٔ غیر JSON (مثلاً صفحهٔ واسط CDN) — قابل اعتماد نیست
    throw new FarakhanServerError(
      "پاسخ سرور قابل خواندن نبود (واسط میانی پاسخ را جایگزین کرده است)؛ لطفاً دوباره تلاش کنید.",
      r.status,
      "cdn",
    );
  }
  return (await r.json()) as FarakhanSubmitResult;
}
