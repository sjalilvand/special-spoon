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

// ---------------- فاز ۲۶ - B24 داشبورد مدیر ----------------

export interface TrendPoint { date: string; count: number }

export interface AdminDashboardData {
  days: number;
  generated_at: string;
  kpis: {
    applicants_total: number;
    users_active: number;
    counselors_active: number;
    cases_total: number;
    cases_by_status: Record<string, number>;
    assessments_pending_review: number;
    assessments_approved: number;
    avg_review_hours: number | null;
    appointments_window: number;
    appointments_done: number;
    appointments_cancelled: number;
    appointments_no_show: number;
    no_show_rate: number;
    appointments_upcoming_7d: number;
    consultations_total: number;
    consultations_with_slot: number;
    consultations_by_status: Record<string, number>;
    booking_active_holds: number;
    booking_confirmed_holds: number;
    sales_paid_orders: number;
    sales_paid_amount: number;
    sales_pending_orders: number;
    sessions_count: number;
  };
  trends: { cases: TrendPoint[]; bookings: TrendPoint[]; sales?: SalesTrendPoint[] };
  counselor_workload: CounselorWorkloadRow[];
}

export interface SalesTrendPoint { date: string; amount: number }

export async function fetchAdminDashboard(days: number): Promise<AdminDashboardData> {
  return (await apiClient.get("/reports/admin-dashboard", { params: { days } })).data;
}

// ---------------- فاز ۲۷ - B41+ گزارش انطباق DPO ----------------

export interface DpoReportData {
  generated_at: string;
  days: number;
  generated_by: string;
  consents: {
    by_kind: Record<string, { granted_active: number; revoked: number }>;
    grants_in_window: number;
    revocations_in_window: number;
    grants_without_version: number;
    versions: Record<string, { versions: number; latest: number }>;
  };
  access: {
    distinct_actors: number;
    login_failed: number;
    tracked_actions: Record<string, number>;
    actions_by_count: Record<string, number>;
  };
  files: {
    scan_status: Record<string, number>;
    scanner_usage: Record<string, number>;
    uploads_in_window: number;
    scan_backends: {
      clamd_configured: boolean;
      clamd_reachable: boolean;
      clamscan_available: boolean;
      fallback: string;
    };
  };
  email_outbox: {
    by_status: Record<string, number>;
    smtp_enabled: boolean;
  };
  accounts: {
    users_active: number;
    users_disabled: number;
    users_pending: number;
    active_sessions: number;
  };
}

export async function fetchDpoReport(days: number): Promise<DpoReportData> {
  return (await apiClient.get("/reports/dpo", { params: { days } })).data;
}

// فاز ۲۷ - وضعیت بسترهای اسکن آنتی‌ویروس (B39-plus)
export interface ScanBackendStatus {
  clamd_configured: boolean;
  clamd_reachable: boolean;
  clamscan_available: boolean;
  fallback: string;
}

export async function fetchScanBackendStatus(): Promise<ScanBackendStatus> {
  return (await apiClient.get("/files/scan-status")).data;
}
