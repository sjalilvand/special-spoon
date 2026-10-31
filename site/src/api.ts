export interface PublicCounselor {
  id: string;
  name: string;
  professional_title: string | null;
  specialty: string | null;
  photo_url: string | null;
}

export interface SlotDay {
  date: string;
  slots: { start_at: string; label: string }[];
}

export interface BookingResult {
  status: string;
  request_id: string;
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
  name: string;
  degree: string | null;
  rank: string | null;
  license: string | null;
  mobile: string | null;
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
