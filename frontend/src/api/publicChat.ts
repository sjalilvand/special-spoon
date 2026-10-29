import { apiClient, paginationOf } from "./client";

/** فاز ۵۵ - پنل پذیرش/مدیر: مشاهدهٔ گفتگوهای عمومی سایت و امتیازها */

export interface PublicChatSessionRow {
  id: string;
  who: "user" | "guest";
  display_name: string;
  username: string | null;
  visitor_name: string | null;
  is_registered: boolean;
  ip: string;
  user_agent: string | null;
  first_page: string | null;
  status: "open" | "closed";
  rating: number | null;
  rating_comment: string | null;
  staff_note: string | null;
  handled_by: string | null;
  handled_at: string | null;
  message_count: number;
  first_question: string | null;
  last_message: string | null;
  last_role: "user" | "assistant" | "operator" | null;
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PublicChatStats {
  total: number;
  last_7d: number;
  today: number;
  open: number;
  rated: number;
  avg_rating: number | null;
  distribution: Record<string, number>;
  top_intents: { intent: string; count: number }[];
}

export interface PublicChatMessageRow {
  id: string;
  role: "user" | "assistant" | "operator";
  content: string;
  sender_name: string | null;
  actions: { label: string; url: string; kind?: string }[] | null;
  quick_replies: string[] | null;
  intent: string | null;
  created_at: string | null;
}

export interface SessionFilters {
  q?: string;
  status?: string;
  rating?: string;
  days?: number;
  page?: number;
  page_size?: number;
}

export async function fetchPublicChatSessions(
  filters: SessionFilters,
): Promise<{ items: PublicChatSessionRow[]; total: number; page: number; page_size: number }> {
  // فاز ۵۵ (v2): پاسخ فهرستی {items,total,page,page_size} به data آرایه +
  // meta.pagination شکسته می‌شود — بازچینی مطابق قرارداد siteops
  const res = await apiClient.get<PublicChatSessionRow[] | { items: PublicChatSessionRow[]; total: number }>(
    "/public-chat/admin/sessions", { params: filters },
  );
  const pag = paginationOf(res);
  const items = Array.isArray(res.data) ? res.data : (res.data as { items?: PublicChatSessionRow[] })?.items ?? [];
  return {
    items,
    total: Number(pag.total ?? items.length),
    page: Number(pag.page ?? 1),
    page_size: Number(pag.page_size ?? 20),
  };
}

export async function fetchPublicChatStats(): Promise<PublicChatStats> {
  const res = await apiClient.get<PublicChatStats>("/public-chat/admin/stats");
  return res.data;
}

export async function fetchPublicChatMessages(
  sessionId: string,
): Promise<{ session: PublicChatSessionRow; messages: PublicChatMessageRow[] }> {
  const res = await apiClient.get(`/public-chat/admin/sessions/${sessionId}/messages`);
  return res.data;
}

export async function updatePublicChatSession(
  sessionId: string,
  payload: { staff_note?: string | null; status?: "open" | "closed" },
): Promise<{ status: string; session_status: string; staff_note: string | null }> {
  const res = await apiClient.put(`/public-chat/admin/sessions/${sessionId}`, payload);
  return res.data;
}

/** فاز ۵۶ - پاسخ زندهٔ پذیرش — مستقیم در ویجت بازدیدکننده نمایش داده می‌شود */
export async function replyToPublicChatSession(
  sessionId: string,
  content: string,
): Promise<{ message: PublicChatMessageRow }> {
  const res = await apiClient.post(`/public-chat/admin/sessions/${sessionId}/reply`, { content });
  return res.data;
}
