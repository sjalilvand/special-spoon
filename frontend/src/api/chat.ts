import { apiClient } from "./client";

/** فاز ۵۲ - چت آنلاین: گفتگوی دو نفره + اتاق مشاوره + پیام صوتی */

export interface ChatMember {
  user_id: string;
  username: string | null;
  display_name: string | null;
  roles: string[];
}

export interface ChatLastMessage {
  id: string;
  kind: string;
  preview: string;
  sender_name: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  kind: "dm" | "group";
  title: string;
  members: ChatMember[];
  unread: number;
  last_message: ChatLastMessage | null;
  last_message_at: string | null;
  created_at: string;
}

export interface MessageMedia {
  mime: string;
  bytes: number;
  duration_ms: number | null;
  url: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  kind: "text" | "voice" | "system";
  body: string | null;
  sender_id: string | null;
  sender_name: string;
  created_at: string;
  media?: MessageMedia;
}

export interface DirectoryUser {
  id: string;
  username: string;
  display_name: string;
  roles: string[];
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await apiClient.get<{ items: Conversation[] }>("/chat/conversations");
  return res.data.items;
}

export async function startConversation(peerId: string): Promise<Conversation> {
  const res = await apiClient.post<Conversation>("/chat/conversations", { peer_id: peerId });
  return res.data;
}

export async function fetchMessages(
  conversationId: string,
  beforeId?: string,
  limit = 50,
): Promise<ChatMessage[]> {
  const res = await apiClient.get<{ items: ChatMessage[] }>(
    `/chat/conversations/${conversationId}/messages`,
    { params: { before_id: beforeId, limit } },
  );
  return res.data.items;
}

export async function sendTextMessage(conversationId: string, body: string): Promise<ChatMessage> {
  const res = await apiClient.post<ChatMessage>(`/chat/conversations/${conversationId}/messages`, {
    body,
  });
  return res.data;
}

export async function sendVoiceMessage(
  conversationId: string,
  blob: Blob,
  durationMs: number,
  mime: string,
): Promise<ChatMessage> {
  const form = new FormData();
  const ext = mime.includes("ogg") ? "ogg" : mime.includes("mp4") ? "m4a" : "webm";
  form.append("file", blob, `voice.${ext}`);
  form.append("duration_ms", String(Math.max(0, Math.round(durationMs))));
  const res = await apiClient.post<ChatMessage>(
    `/chat/conversations/${conversationId}/voice`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return res.data;
}

export async function markRead(conversationId: string, messageId: string): Promise<void> {
  await apiClient.post(`/chat/conversations/${conversationId}/read`, { message_id: messageId });
}

export async function inviteToConversation(
  conversationId: string,
  userIds: string[],
  note?: string,
): Promise<{ conversation: Conversation; added: { id: string; display_name: string }[]; was_dm: boolean }> {
  const res = await apiClient.post(`/chat/conversations/${conversationId}/invite`, {
    user_ids: userIds,
    note: note || undefined,
  });
  return res.data;
}

export async function fetchChatDirectory(search?: string): Promise<DirectoryUser[]> {
  const res = await apiClient.get<{ items: DirectoryUser[] }>("/chat/directory", {
    params: { search: search || "" },
  });
  return res.data.items;
}

/** آدرس WebSocket با توکن در query (توکن فقط در حافظه است — بند ۴.۲) */
export function chatWsUrl(token: string | null): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base = import.meta.env.VITE_WS_BASE_URL ?? "";
  const host = base ? base.replace(/^https?:\/\//, "").replace(/\/$/, "") : window.location.host;
  return `${proto}://${host}/api/v2/chat/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}
