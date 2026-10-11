import { apiClient } from "./client";

export interface CaseRow {
  id: string;
  case_number: string;
  applicant_name: string | null;
  applicant_national_id: string | null;
  acceptance_date: string;
  service_location_title: string | null;
  service_type: string | null;
  primary_counselor_name: string | null;
  priority: string;
  status: string;
  consent_status: string;
  close_reason: string | null;
  close_date: string | null;
  version: number;
}

export interface AssignmentRow {
  id: string;
  counselor_name: string;
  start_at: string | null;
  end_at: string | null;
  reason: string | null;
  end_reason: string | null;
  is_current: boolean;
}

export interface ConsentRow {
  id: string;
  version: number;
  status: string;
  note: string | null;
  consent_date: string | null;
  recorded_by_name: string | null;
}

export interface CaseDetail extends CaseRow {
  assignments: AssignmentRow[];
  consents: ConsentRow[];
}

export interface OptionRow {
  id: string;
  label: string;
}

export const CASE_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" }> = {
  new: { label: "جدید", color: "info" },
  awaiting_assignment: { label: "در انتظار تخصیص", color: "warning" },
  active: { label: "فعال", color: "success" },
  suspended: { label: "متوقف", color: "default" },
  closed: { label: "بسته", color: "default" },
  archived: { label: "بایگانی", color: "default" },
};

export const PRIORITY_LABELS: Record<string, string> = { low: "کم", normal: "عادی", high: "فوری" };

export const CONSENT_META: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  none: { label: "بدون رضایت‌نامه", color: "default" },
  granted: { label: "رضایت ثبت‌شده", color: "success" },
  revoked: { label: "رضایت پس‌گرفته‌شده", color: "warning" },
};

export async function fetchCases(params: {
  page: number;
  status?: string;
  search?: string;
}): Promise<{ items: CaseRow[]; total: number }> {
  return (await apiClient.get("/cases", { params: { ...params, page_size: 10 } })).data;
}

export async function fetchCase(id: string): Promise<CaseDetail> {
  return (await apiClient.get(`/cases/${id}`)).data;
}

export async function fetchApplicantOptions(search?: string): Promise<{ items: OptionRow[] }> {
  return (await apiClient.get("/cases/applicant-options", { params: { search } })).data;
}

export async function fetchCounselorOptions(): Promise<{ items: OptionRow[] }> {
  return (await apiClient.get("/cases/counselor-options")).data;
}

export async function createCase(payload: Record<string, unknown>): Promise<CaseDetail> {
  return (await apiClient.post("/cases", payload)).data;
}

export async function updateCase(id: string, payload: Record<string, unknown>): Promise<CaseDetail> {
  return (await apiClient.patch(`/cases/${id}`, payload)).data;
}

export async function assignCounselor(id: string, payload: Record<string, unknown>): Promise<CaseDetail> {
  return (await apiClient.post(`/cases/${id}/assignments`, payload)).data;
}

export async function closeCase(id: string, reason: string): Promise<CaseDetail> {
  return (await apiClient.post(`/cases/${id}/close`, { reason })).data;
}

export async function reopenCase(id: string, reason: string): Promise<CaseDetail> {
  return (await apiClient.post(`/cases/${id}/reopen`, { reason })).data;
}

export async function addConsent(id: string, payload: Record<string, unknown>): Promise<CaseDetail> {
  return (await apiClient.post(`/cases/${id}/consents`, payload)).data;
}
