import { apiClient } from "./client";

export interface RecommendationRow {
  id: string;
  case_id: string;
  content: string;
  is_published: boolean;
  published_at: string | null;
  published_by_name: string | null;
  created_at: string | null;
}

export async function fetchCaseRecommendations(caseId: string): Promise<{ items: RecommendationRow[] }> {
  return (await apiClient.get(`/cases/${caseId}/recommendations`)).data;
}

export async function createRecommendation(caseId: string, content: string): Promise<RecommendationRow> {
  return (await apiClient.post(`/cases/${caseId}/recommendations`, { content })).data;
}

export async function publishRecommendation(id: string): Promise<RecommendationRow> {
  return (await apiClient.post(`/recommendations/${id}/publish`, {})).data;
}
