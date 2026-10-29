import { apiClient } from "./client";

/** فاز ۶۱ - تماس تلفنی مدیریت‌شده در گفتگو */

export interface CallSessionDto {
  id: string;
  conversation_id: string | null;
  caller_id: string;
  caller_name: string | null;
  callee_id: string;
  callee_name: string | null;
  phone: string | null;
  status: "ringing" | "ongoing" | "ended" | "declined" | "cancelled";
  started_at: string | null;
  answered_at: string | null;
  ended_at: string | null;
  duration_sec: number;
  survey_template_id: string | null;
}

export async function startCall(conversationId: string, phone?: string): Promise<CallSessionDto> {
  const res = await apiClient.post<CallSessionDto>("/calls/start", {
    conversation_id: conversationId,
    phone: phone || undefined,
  });
  return res.data;
}

export async function answerCall(callId: string): Promise<CallSessionDto> {
  const res = await apiClient.post<CallSessionDto>(`/calls/${callId}/answer`);
  return res.data;
}

export async function declineCall(callId: string): Promise<CallSessionDto> {
  const res = await apiClient.post<CallSessionDto>(`/calls/${callId}/decline`);
  return res.data;
}

export async function cancelCall(callId: string): Promise<CallSessionDto> {
  const res = await apiClient.post<CallSessionDto>(`/calls/${callId}/cancel`);
  return res.data;
}

export async function endCall(callId: string): Promise<CallSessionDto> {
  const res = await apiClient.post<CallSessionDto>(`/calls/${callId}/end`);
  return res.data;
}

export async function fetchActiveCall(): Promise<CallSessionDto | null> {
  const res = await apiClient.get<{ call: CallSessionDto | null }>("/calls/active");
  return res.data.call;
}

export async function fetchMyCalls(): Promise<CallSessionDto[]> {
  const res = await apiClient.get<{ items: CallSessionDto[] }>("/calls/mine");
  return res.data.items;
}
