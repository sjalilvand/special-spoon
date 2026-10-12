import { apiClient } from "./client";

export interface ReferralRow {
  id: string;
  case_id: string;
  direction: string;
  status: string;
  target_label: string | null;
  to_counselor_id: string | null;
  to_service_location_id: string | null;
  to_center_name: string | null;
  reason: string;
  notes: string | null;
  outcome: string | null;
  referral_date: string | null;
  outcome_date: string | null;
  requested_by_name: string | null;
  handled_by_name: string | null;
  row_version: number;
  case_number?: string;
  direction_label?: string;
}

export const REFERRAL_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" | "error" }> = {
  initiated: { label: "آغاز‌شده", color: "warning" },
  accepted: { label: "پذیرفته‌شده", color: "info" },
  completed: { label: "تکمیل‌شده", color: "success" },
  rejected: { label: "ردشده", color: "error" },
  cancelled: { label: "لغوشده", color: "default" },
};

export const REFERRAL_DIRECTION_LABELS: Record<string, string> = {
  internal: "داخلی",
  cross_center: "بین‌مرکزی",
  external: "خارجی",
};

export async function fetchCaseReferrals(caseId: string): Promise<{ items: ReferralRow[] }> {
  return (await apiClient.get(`/cases/${caseId}/referrals`)).data;
}

export async function createReferral(caseId: string, payload: Record<string, unknown>): Promise<ReferralRow> {
  return (await apiClient.post(`/cases/${caseId}/referrals`, payload)).data;
}

export async function updateReferral(id: string, payload: Record<string, unknown>): Promise<ReferralRow> {
  return (await apiClient.patch(`/referrals/${id}`, payload)).data;
}

export async function convertConsultationRequest(
  id: string,
  payload: Record<string, unknown>
): Promise<{ applicant_id: string; applicant_created: boolean; case_id: string | null; case_number: string | null }> {
  return (await apiClient.post(`/consultation-requests/${id}/convert`, payload)).data;
}
