// فاز ۳۳ - B32 سند جامع: دسته‌بندی موضوعی
import { apiClient } from "./client";

export interface Topic {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  parent_name: string | null;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  service_count: number;
  service_ids: string[];
  children_count: number;
  created_at: string | null;
}

export interface PublicTopic {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  description: string | null;
  sort_order: number;
  active_service_count: number;
}

export async function fetchTopics(includeInactive = true): Promise<Topic[]> {
  const r = await apiClient.get<{ items: Topic[] }>("/topics", {
    params: { include_inactive: includeInactive },
  });
  return r.data.items;
}

export async function createTopic(payload: Record<string, unknown>): Promise<Topic> {
  const r = await apiClient.post<Topic>("/topics", payload);
  return r.data;
}

export async function updateTopic(id: string, payload: Record<string, unknown>): Promise<Topic> {
  const r = await apiClient.patch<Topic>(`/topics/${id}`, payload);
  return r.data;
}

export async function deleteTopic(id: string): Promise<void> {
  await apiClient.delete(`/topics/${id}`);
}

export async function setTopicServices(id: string, serviceIds: string[]): Promise<Topic> {
  const r = await apiClient.put<Topic>(`/topics/${id}/services`, { service_ids: serviceIds });
  return r.data;
}
