import { apiClient } from "./client";

export interface ConsultationRow {
  id: string;
  full_name: string;
  mobile: string;
  topic: string;
  preferred_date: string | null;
  preferred_slot: string | null;
  message: string | null;
  status: string;
  created_at: string | null;
  handled_by_name: string | null;
  reception_note: string | null;
  contact_attempts: number;
  city: string | null;
  referral_source: string | null;
}

export const CONSULT_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" }> = {
  new: { label: "جدید", color: "warning" },
  in_review: { label: "در حال بررسی", color: "info" },
  converted: { label: "تبدیل به متقاضی", color: "success" },
  archived: { label: "بایگانی", color: "default" },
};

export async function fetchConsultationRequests(params: {
  status?: string;
  page: number;
}): Promise<{ items: ConsultationRow[]; total: number }> {
  return (await apiClient.get("/consultation-requests", { params: { ...params, page_size: 20 } })).data;
}

export async function updateConsultationRequest(
  id: string,
  payload: { status: string; reception_note?: string; add_contact_attempt?: boolean }
): Promise<void> {
  await apiClient.patch(`/consultation-requests/${id}`, payload);
}

export async function uploadCounselorPhoto(id: string, file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  await apiClient.post(`/counselors/${id}/photo`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
