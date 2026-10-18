import { apiClient } from "./client";

export interface NotificationItem {
  id: string;
  category: string;
  event_code: string;
  title: string;
  body: string | null;
  severity: "info" | "warning" | "critical";
  entity_type: string | null;
  entity_id: string | null;
  read_at: string | null;
  created_at: string | null;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  unread: number;
}

export async function fetchNotifications(unreadOnly = false, limit = 50): Promise<NotificationsResponse> {
  const { data } = await apiClient.get<NotificationsResponse>("/notifications", {
    params: { unread_only: unreadOnly, limit },
  });
  return data;
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await apiClient.get<{ count: number }>("/notifications/unread-count");
  return data.count;
}

export async function markNotificationRead(id: string): Promise<void> {
  await apiClient.post(`/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await apiClient.post<{ updated: number }>("/notifications/read-all");
  return data.updated;
}

export const severityColor: Record<NotificationItem["severity"], "info" | "warning" | "error"> = {
  info: "info",
  warning: "warning",
  critical: "error",
};
