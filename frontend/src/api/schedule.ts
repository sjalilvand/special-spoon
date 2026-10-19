import { apiClient, paginationOf } from "./client";

export interface AppointmentRow {
  id: string;
  case_id: string;
  case_number: string | null;
  applicant_name: string | null;
  counselor_name: string | null;
  scheduled_at: string;
  duration_minutes: number | null;
  location: string | null;
  status: string;
  note: string | null;
}

export interface CounselorAppointmentRow {
  id: string;
  case_id: string;
  case_number: string;
  applicant_name: string;
  scheduled_at: string;
  duration_minutes: number | null;
  location: string | null;
}

export interface SessionRow {
  id: string;
  case_id: string;
  session_number: number;
  occurred_at: string;
  appointment_id: string | null;
  counselor_name: string | null;
  note_status: string;
  note_version: number;
  content: Record<string, string | undefined>;
  author_name: string | null;
  can_edit_note: boolean;
  updated_at: string | null;
}

export const APPOINTMENT_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" }> = {
  scheduled: { label: "برنامه‌ریزی‌شده", color: "info" },
  done: { label: "انجام‌شده", color: "success" },
  cancelled: { label: "لغوشده", color: "default" },
  no_show: { label: "عدم حضور", color: "warning" },
};

export const SESSION_NOTE_STATUS_META: Record<string, { label: string; color: "success" | "default" }> = {
  draft: { label: "پیش‌نویس", color: "default" },
  final: { label: "نهایی", color: "success" },
};

export const SESSION_FIELD_LABELS: Record<string, string> = {
  goal: "هدف جلسه",
  status_summary: "خلاصه وضعیت",
  intervention: "مداخله",
  client_response: "پاسخ مراجع",
  homework: "تکلیف",
  follow_up: "پیگیری",
  note: "یادداشت",
};

export async function fetchAppointments(params: {
  case_id?: string;
  status?: string;
  page?: number;
}): Promise<{ items: AppointmentRow[]; total: number }> {
  // فاز ۳۹ (v2): data آرایه + total در meta.pagination
  const r = await apiClient.get("/appointments", { params });
  return { items: r.data, total: Number(paginationOf(r).total ?? 0) };
}

export async function createAppointment(payload: Record<string, unknown>): Promise<AppointmentRow> {
  return (await apiClient.post("/appointments", payload)).data;
}

export async function updateAppointment(id: string, payload: Record<string, unknown>): Promise<AppointmentRow> {
  return (await apiClient.patch(`/appointments/${id}`, payload)).data;
}

export async function fetchCounselorAppointments(): Promise<{ items: CounselorAppointmentRow[] }> {
  return (await apiClient.get("/worklists/counselor-appointments")).data;
}

export async function fetchCaseSessions(caseId: string): Promise<{ items: SessionRow[] }> {
  return (await apiClient.get(`/cases/${caseId}/sessions`)).data;
}

export async function createSession(caseId: string, payload: Record<string, unknown>): Promise<SessionRow> {
  return (await apiClient.post(`/cases/${caseId}/sessions`, payload)).data;
}

export async function saveSessionNote(sessionId: string, payload: Record<string, unknown>): Promise<SessionRow> {
  return (await apiClient.post(`/sessions/${sessionId}/note`, payload)).data;
}

export async function finalizeSessionNote(sessionId: string): Promise<SessionRow> {
  return (await apiClient.post(`/sessions/${sessionId}/note/finalize`, {})).data;
}

export async function createSessionNoteRevision(sessionId: string): Promise<SessionRow> {
  return (await apiClient.post(`/sessions/${sessionId}/note/revisions`, {})).data;
}
