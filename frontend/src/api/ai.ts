// فاز ۳۵ - B25/B26/B27 سند جامع: دستیار هوشمند (تصمیم D07 — پلاگین‌پذیر)
import { apiClient } from "./client";

export interface AiConfig {
  configured_provider: string;
  active_provider: string;
  fallback_applied: boolean;
  rate_limit_per_minute: number;
  disclaimer: string;
}

export interface ChatResult {
  response: string;
  provider: string;
  disclaimer: string;
  latency_ms: number;
}

export interface RecommendationItem {
  service_id: string;
  title: string;
  topic_id: string;
}

export interface NoShowRiskItem {
  appointment_id: string;
  case_id: string | null;
  scheduled_at: string | null;
  previous_no_shows: number;
  risk_score: number;
  risk_level: string;
  factors: string[];
}

export async function fetchAiConfig(): Promise<AiConfig> {
  const r = await apiClient.get<AiConfig>("/ai/config");
  return r.data;
}

export async function aiChat(message: string): Promise<ChatResult> {
  const r = await apiClient.post<ChatResult>("/ai/chat", { message });
  return r.data;
}

export async function fetchRecommendations(): Promise<RecommendationItem[]> {
  const r = await apiClient.get<{ items: RecommendationItem[] }>("/ai/recommendations");
  return r.data.items;
}

export async function fetchNoShowRisk(daysAhead = 7): Promise<{ window_days: number; count: number; items: NoShowRiskItem[] }> {
  const r = await apiClient.get("/ai/no-show-risk", { params: { days_ahead: daysAhead } });
  return r.data;
}

// ===========================================================================
// فاز ۵۳ - عامل هوشمند (الگوی deepseek-harness: agent loop + tools + session)
// ===========================================================================

export interface AgentToolInfo {
  name: string;
  title: string;
  description: string;
  staff_only: boolean;
}

export interface AgentConfig {
  llm_ready: boolean;
  agent_available: boolean;
  tools: AgentToolInfo[];
  disclaimer: string;
}

export interface AgentStepTrace {
  tool_name: string;
  tool_title: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface AgentChatResult {
  session_id: string;
  response: string;
  provider: string;
  fallback_used: boolean;
  steps: AgentStepTrace[];
  disclaimer: string;
  latency_ms: number;
}

export interface AgentSessionItem {
  id: string;
  title: string;
  updated_at: string | null;
}

export interface AgentMessageItem {
  role: "user" | "assistant" | "tool";
  content: string;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
  tool_result: Record<string, unknown> | null;
  provider: string | null;
  created_at: string | null;
}

export async function fetchAgentConfig(): Promise<AgentConfig> {
  const r = await apiClient.get<AgentConfig>("/ai/agent/config");
  return r.data;
}

export async function agentChat(message: string, sessionId?: string | null): Promise<AgentChatResult> {
  const r = await apiClient.post<AgentChatResult>("/ai/agent/chat", {
    message,
    session_id: sessionId ?? null,
  });
  return r.data;
}

export async function fetchAgentSessions(page = 1, pageSize = 20): Promise<{ items: AgentSessionItem[]; total: number }> {
  const r = await apiClient.get("/ai/agent/sessions", { params: { page, page_size: pageSize } });
  return r.data;
}

export async function fetchAgentMessages(sessionId: string): Promise<{ title: string; items: AgentMessageItem[] }> {
  const r = await apiClient.get(`/ai/agent/sessions/${sessionId}/messages`);
  return r.data;
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/ai/agent/sessions/${sessionId}`);
}
