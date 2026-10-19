// فاز ۳۵ - B23 سند جامع: نظرسنجی/شکایت/تیکت پشتیبانی
import { apiClient } from "./client";

// ---------------------------------------------------------------- نظرسنجی
export interface SurveySummary {
  total: number;
  average: number;
  distribution: Record<string, number>;
  recent_comments: { score: number; comment: string | null; created_at: string | null }[];
}

export async function fetchSurveySummary(): Promise<SurveySummary> {
  const r = await apiClient.get<SurveySummary>("/reports/survey-summary");
  return r.data;
}

export async function submitSurvey(sessionId: string, payload: { score: number; comment?: string }) {
  const r = await apiClient.post(`/sessions/${sessionId}/survey`, payload);
  return r.data;
}

// ---------------------------------------------------------------- شکایت
export interface Complaint {
  id: string;
  complainant_user_id: string;
  subject: string;
  body: string;
  status: "new" | "in_review" | "resolved" | "rejected";
  resolution_note: string | null;
  reviewed_at: string | null;
  created_at: string | null;
}

export async function fetchComplaints(): Promise<Complaint[]> {
  const r = await apiClient.get<{ items: Complaint[] }>("/complaints");
  return r.data.items;
}

export async function createComplaint(payload: { subject: string; body: string }) {
  const r = await apiClient.post("/complaints", payload);
  return r.data;
}

export async function reviewComplaint(
  id: string,
  payload: { status: string; resolution_note?: string },
): Promise<Complaint> {
  const r = await apiClient.patch<Complaint>(`/complaints/${id}/review`, payload);
  return r.data;
}

// ---------------------------------------------------------------- تیکت
export interface TicketMessage {
  id: string;
  sender_user_id: string;
  body: string;
  is_staff: boolean;
  created_at: string | null;
}

export interface Ticket {
  id: string;
  user_id: string;
  subject: string;
  status: "open" | "answered" | "closed";
  priority: "normal" | "high";
  closed_at: string | null;
  created_at: string | null;
  messages_count: number;
  messages?: TicketMessage[];
}

export async function fetchTickets(): Promise<Ticket[]> {
  const r = await apiClient.get<{ items: Ticket[] }>("/tickets");
  return r.data.items;
}

export async function fetchTicket(id: string): Promise<Ticket> {
  const r = await apiClient.get<Ticket>(`/tickets/${id}`);
  return r.data;
}

export async function createTicket(payload: { subject: string; body: string; priority: string }) {
  const r = await apiClient.post("/tickets", payload);
  return r.data;
}

export async function addTicketMessage(id: string, body: string): Promise<Ticket> {
  const r = await apiClient.post<Ticket>(`/tickets/${id}/messages`, { body });
  return r.data;
}

export async function closeTicket(id: string): Promise<Ticket> {
  const r = await apiClient.post<Ticket>(`/tickets/${id}/close`, {});
  return r.data;
}
