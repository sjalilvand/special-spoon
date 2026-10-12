import { apiClient } from "./client";

export interface CounselorWorkloadRow {
  counselor_id: string;
  counselor_name: string;
  active_cases: number;
  sessions_count: number;
}

export interface RecentImportRow {
  import_type: string;
  status: string;
  created_rows: number;
  error_rows: number;
  created_at: string | null;
}

export interface ReportSummary {
  view: "staff" | "self";
  days: number;
  cases_by_status: Record<string, number>;
  appointments_by_status: Record<string, number>;
  sessions_count: number;
  assessments_pending_review: number;
  applicants_total: number;
  users_active: number;
  counselors_active: number;
  counselor_workload: CounselorWorkloadRow[];
  recent_imports: RecentImportRow[];
}

export async function fetchReportSummary(params: {
  days: number;
  counselor_id?: string;
}): Promise<ReportSummary> {
  return (await apiClient.get("/reports/summary", { params })).data;
}

export interface AuditEventRow {
  id: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  result: string;
  actor_name: string | null;
  ip: string | null;
  created_at: string | null;
  detail: unknown;
}

export async function fetchAuditEvents(params: {
  page: number;
}): Promise<{ items: AuditEventRow[]; total: number; page: number; page_size: number }> {
  return (await apiClient.get("/audit-events", { params: { ...params, page_size: 30 } })).data;
}

export async function printAssessment(id: string): Promise<void> {
  await apiClient.post(`/assessments/${id}/print`, {});
}
