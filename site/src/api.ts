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
  rules: { require_military_status_for_male: boolean; phone_required: boolean };
}

export interface FarakhanCaptcha {
  captcha_id: string;
  svg: string;
  ttl_seconds: number;
}

/** خطای اعتبارسنجی فراخوان: نقشهٔ «برچسب فارسی فیلد → پیام» */
export class FarakhanValidationError extends Error {
  errors: Record<string, string>;
  constructor(message: string, errors: Record<string, string>) {
    super(message);
    this.errors = errors;
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

export async function submitFarakhan(payload: Record<string, unknown>, files: Record<string, File>): Promise<FarakhanSubmitResult> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(payload));
  for (const [key, file] of Object.entries(files)) {
    if (file) fd.append(key, file, file.name);
  }
  const r = await fetch("/api/v1/farakhan/submissions", { method: "POST", body: fd });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    const detail = d && d.detail;
    if (detail && typeof detail === "object" && detail.errors) {
      throw new FarakhanValidationError(
        detail.message || "اعتبارسنجی اطلاعات ناموفق بود.",
        detail.errors as Record<string, string>,
      );
    }
    throw new Error(typeof detail === "string" ? detail : "خطا در ثبت فرم فراخوان");
  }
  return (await r.json()) as FarakhanSubmitResult;
}
