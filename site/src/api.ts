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