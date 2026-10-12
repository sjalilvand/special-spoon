import { apiClient } from "./client";

export interface DiagnosisRow {
  id: string;
  case_id: string;
  status: string;
  title: string | null;
  code: string | null;
  comorbid: string | null;
  note: string | null;
  recorded_by_name: string | null;
  created_at: string | null;
}

export interface TreatmentPlanRow {
  id: string;
  case_id: string;
  version_no: number;
  status: string;
  goals: string | null;
  approach: string | null;
  approach_note: string | null;
  protocol_name: string | null;
  sessions_count: number | null;
  session_interval: string | null;
  interventions: string | null;
  external_referral: string | null;
  review_date: string | null;
  remarks: string | null;
  recorded_by_name: string | null;
  row_version: number;
  updated_at: string | null;
}

export const DX_STATUS_META: Record<string, string> = {
  confirmed: "قطعی",
  probable: "محتمل",
  under_review: "در حال بررسی",
  none: "ندارد",
};

export const PLAN_APPROACH_LABELS: Record<string, string> = {
  cbt: "شناختی-رفتاری",
  act: "پذیرش و تعهد",
  schema: "طرح‌واره",
  psychodynamic: "روان‌پویشی",
  family: "خانواده‌درمانی",
  medical: "دارودرمانی هماهنگ",
  other: "سایر",
};

export async function fetchDiagnoses(caseId: string): Promise<{ items: DiagnosisRow[] }> {
  return (await apiClient.get(`/cases/${caseId}/diagnoses`)).data;
}

export async function createDiagnosis(caseId: string, payload: Record<string, unknown>): Promise<DiagnosisRow> {
  return (await apiClient.post(`/cases/${caseId}/diagnoses`, payload)).data;
}

export async function fetchTreatmentPlans(caseId: string): Promise<{ items: TreatmentPlanRow[] }> {
  return (await apiClient.get(`/cases/${caseId}/treatment-plans`)).data;
}

export async function createTreatmentPlan(caseId: string, payload: Record<string, unknown>): Promise<TreatmentPlanRow> {
  return (await apiClient.post(`/cases/${caseId}/treatment-plans`, payload)).data;
}

export async function updateTreatmentPlan(id: string, payload: Record<string, unknown>): Promise<TreatmentPlanRow> {
  return (await apiClient.patch(`/treatment-plans/${id}`, payload)).data;
}
