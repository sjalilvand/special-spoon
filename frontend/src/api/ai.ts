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
