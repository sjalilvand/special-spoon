// فاز ۳۶ - B28 سند جامع: یکپارچه‌سازی‌های بیرونی (وضعیت سرویس‌ها + صف پیامک)
import { apiClient, paginationOf } from "./client";

export interface IntegrationStatus {
  configured: string;
  ready: boolean;
  decision: string;
}

export interface SmsStatus extends IntegrationStatus {
  channel: string;
  enabled: boolean;
  active_provider: string;
  fallback_applied: boolean;
  max_attempts: number;
}

export interface IntegrationsConfig {
  payment_gateway: IntegrationStatus;
  maps: IntegrationStatus;
  email: IntegrationStatus;
  ai: IntegrationStatus;
  sms: SmsStatus;
  storage: IntegrationStatus & {
    configured_backend: string;
    active_backend: string;
    fallback_applied: boolean;
    bucket: string;
    boto3_available: boolean;
  };
}

export interface SmsRow {
  id: string;
  notification_id: string | null;
  recipient_mobile: string;
  purpose: string;
  body: string;
  provider: string;
  status: string;
  attempts: number;
  last_error: string | null;
  created_at: string | null;
  sent_at: string | null;
}

export interface SmsOutboxResponse {
  items: SmsRow[];
  total: number;
  page: number;
  page_size: number;
  summary: {
    by_status: Record<string, number>;
    sms_enabled: boolean;
    active_provider: string;
    fallback_applied: boolean;
  };
}

export interface ProcessResult {
  queued: number;
  sent: number;
  failed: number;
  disabled: number;
  active_provider: string;
  fallback_applied: boolean;
}

export async function fetchIntegrationsConfig(): Promise<IntegrationsConfig> {
  const r = await apiClient.get<{ integrations: IntegrationsConfig }>("/integrations/config");
  return r.data.integrations;
}

export async function fetchSmsOutbox(params: {
  status?: string;
  purpose?: string;
  page?: number;
  page_size?: number;
}): Promise<SmsOutboxResponse> {
  // فاز ۳۹ (v2): data آرایه + بقیه کلیدها (total/page/summary) در meta.pagination
  const r = await apiClient.get("/sms-outbox", { params });
  const pg = paginationOf(r) as Pick<SmsOutboxResponse, "total" | "page" | "page_size" | "summary">;
  return { items: r.data, total: pg.total, page: pg.page, page_size: pg.page_size, summary: pg.summary };
}

export async function processSmsOutbox(limit = 25): Promise<ProcessResult> {
  const r = await apiClient.post<ProcessResult>("/sms-outbox/process", null, {
    params: { limit },
  });
  return r.data;
}

export async function retrySmsRow(id: string): Promise<SmsRow> {
  const r = await apiClient.post<SmsRow>(`/sms-outbox/${id}/retry`);
  return r.data;
}
