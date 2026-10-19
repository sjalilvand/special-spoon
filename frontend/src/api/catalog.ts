// فاز ۲۸ - B05/B06/B07 سند جامع: صلاحیت مشاور، خدمات و تعرفه نسخه‌دار
import { apiClient, paginationOf } from "./client";

export interface Specialty {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface Service {
  id: string;
  specialty_id: string;
  specialty_name: string | null;
  code: string | null;
  title: string;
  description: string | null;
  duration_minutes: number;
  session_type: string;
  status: string;
  current_price: number | null;
  current_currency: string | null;
}

export interface TariffVersion {
  id: string;
  service_id: string;
  amount: number;
  currency: string;
  valid_from: string;
  valid_to: string | null;
  note: string | null;
}

export interface PricingQuote {
  service_id: string;
  date: string;
  tariff_version_id: string;
  amount: number;
  currency: string;
  valid_from: string;
  valid_to: string | null;
}

export interface CounselorCredential {
  id: string;
  counselor_id: string;
  counselor_name?: string | null;
  counselor_code?: string | null;
  kind: string;
  title: string;
  license_number: string | null;
  issued_at: string | null;
  expires_at: string | null;
  file_path: string | null;
  verification_status: string;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface Paged<T> { items: T[]; total: number; page: number; page_size: number }

export async function fetchSpecialties(includeInactive = false): Promise<Specialty[]> {
  // فاز ۳۹ (v2): پاسخ صفحه‌بندی‌شده {items,total} → data آرایه
  const r = await apiClient.get("/specialties", { params: { include_inactive: includeInactive || undefined } });
  return r.data;
}

export async function createSpecialty(payload: { name: string; description?: string }): Promise<Specialty> {
  const r = await apiClient.post("/specialties", payload);
  return r.data;
}

export async function updateSpecialty(id: string, payload: Record<string, unknown>): Promise<Specialty> {
  const r = await apiClient.patch(`/specialties/${id}`, payload);
  return r.data;
}

export async function fetchServices(params: {
  specialty_id?: string; status?: string; search?: string; page?: number;
}): Promise<Paged<Service>> {
  // فاز ۳۹ (v2): data آرایه + total/page در meta.pagination
  const r = await apiClient.get("/services", { params });
  return { items: r.data, ...paginationOf(r) } as Paged<Service>;
}

export async function createService(payload: Record<string, unknown>): Promise<Service> {
  const r = await apiClient.post("/services", payload);
  return r.data;
}

export async function updateService(id: string, payload: Record<string, unknown>): Promise<Service> {
  const r = await apiClient.patch(`/services/${id}`, payload);
  return r.data;
}

export async function fetchTariffs(serviceId: string): Promise<TariffVersion[]> {
  const r = await apiClient.get("/tariffs", { params: { service_id: serviceId } });
  return r.data; // فاز ۳۹ (v2): {items,total} صفحه‌بندی‌شده → data آرایه
}

export async function createTariff(payload: {
  service_id: string; amount: number; currency?: string; valid_from: string; valid_to?: string; note?: string;
}): Promise<TariffVersion> {
  const r = await apiClient.post("/tariffs", payload);
  return r.data;
}

export async function updateTariff(id: string, payload: { valid_to?: string; note?: string }): Promise<TariffVersion> {
  const r = await apiClient.patch(`/tariffs/${id}`, payload);
  return r.data;
}

export async function fetchQuote(serviceId: string, date?: string): Promise<PricingQuote> {
  const r = await apiClient.get("/pricing/quote", { params: { service_id: serviceId, date } });
  return r.data;
}

export async function fetchCredentials(counselorId: string): Promise<CounselorCredential[]> {
  const r = await apiClient.get(`/counselors/${counselorId}/credentials`);
  return r.data; // فاز ۳۹ (v2): {items,total} صفحه‌بندی‌شده → data آرایه
}

export async function addCredential(counselorId: string, payload: Record<string, unknown>): Promise<CounselorCredential> {
  const r = await apiClient.post(`/counselors/${counselorId}/credentials`, payload);
  return r.data;
}

export async function fetchVerificationReviews(status = "pending"): Promise<CounselorCredential[]> {
  const r = await apiClient.get("/verification-reviews", { params: { status } });
  return r.data; // فاز ۳۹ (v2): {items,total,all} صفحه‌بندی‌شده → data آرایه
}

export async function reviewCredential(id: string, action: "approve" | "reject", note?: string): Promise<CounselorCredential> {
  const r = await apiClient.post(`/verification-reviews/${id}`, { action, note: note || undefined });
  return r.data;
}
