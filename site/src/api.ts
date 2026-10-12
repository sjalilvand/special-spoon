export interface PublicCounselor {
  id: string;
  name: string;
  professional_title: string | null;
  specialty: string | null;
  photo_url: string | null;
}

export async function fetchPublicCounselors(): Promise<PublicCounselor[]> {
  const r = await fetch("/api/v1/public/counselors");
  if (!r.ok) throw new Error("خطا در دریافت مشاوران");
  return (await r.json()).items as PublicCounselor[];
}

export async function postConsultation(payload: Record<string, unknown>): Promise<void> {
  const r = await fetch("/api/v1/public/consultation-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => null);
    throw new Error((d && d.detail) || "خطا در ارسال درخواست");
  }
}
