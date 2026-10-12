import { apiClient } from "./client";

export interface FormFieldDef {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "multiselect" | "boolean";
  required: boolean;
  options: { value: string; label: string }[];
}

export interface FormSectionDef {
  key: string;
  title: string;
  fields: FormFieldDef[];
}

export interface FormDefinition {
  code: string;
  version: number;
  sections: FormSectionDef[];
}

export interface ReviewActionRow {
  id: string;
  decision: string;
  comment: string | null;
  reviewer_name: string | null;
  created_at: string | null;
}

export interface AssessmentDetail {
  id: string;
  case_id: string;
  case_number: string | null;
  applicant_name: string | null;
  form_code: string;
  form_version: number;
  form_definition: FormDefinition | null;
  status: string;
  version_no: number;
  row_version: number;
  previous_version_id: string | null;
  author_user_id: string | null;
  author_name: string | null;
  finalized_by_name: string | null;
  finalized_at: string | null;
  answers: Record<string, unknown>;
  review_actions: ReviewActionRow[];
  updated_at: string | null;
}

export interface AssessmentListItem {
  id: string;
  case_id: string;
  case_number: string;
  applicant_name: string | null;
  version_no: number;
  status: string;
  author_name: string | null;
  finalized_at: string | null;
  updated_at: string | null;
}

export const ASSESSMENT_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" | "error" }> = {
  draft: { label: "پیش‌نویس", color: "default" },
  finalized: { label: "نهایی", color: "info" },
  pending_review: { label: "در انتظار بررسی", color: "warning" },
  returned: { label: "برگشت‌خورده", color: "error" },
  approved: { label: "تأییدشده", color: "success" },
};

export async function fetchFormDefinition(): Promise<FormDefinition> {
  return (await apiClient.get("/forms/RS-PS-04-01")).data;
}

export async function fetchCaseAssessments(caseId: string): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get(`/cases/${caseId}/assessments`)).data;
}

export async function fetchAssessment(id: string): Promise<AssessmentDetail> {
  return (await apiClient.get(`/assessments/${id}`)).data;
}

export async function createAssessmentDraft(caseId: string, answers: Record<string, unknown>): Promise<AssessmentDetail> {
  return (await apiClient.post(`/cases/${caseId}/assessments`, { answers })).data;
}

export async function saveAssessmentDraft(id: string, answers: Record<string, unknown>, expectedVersion?: number): Promise<AssessmentDetail> {
  return (await apiClient.patch(`/assessments/${id}`, { answers, expected_version: expectedVersion })).data;
}

export async function finalizeAssessment(id: string, expectedVersion?: number): Promise<AssessmentDetail> {
  return (await apiClient.post(`/assessments/${id}/finalize`, { expected_version: expectedVersion })).data;
}

export async function approveAssessment(id: string, comment?: string): Promise<AssessmentDetail> {
  return (await apiClient.post(`/assessments/${id}/approve`, { comment: comment || null })).data;
}

export async function returnAssessment(id: string, comment: string): Promise<AssessmentDetail> {
  return (await apiClient.post(`/assessments/${id}/return`, { comment })).data;
}

export async function createRevision(id: string): Promise<AssessmentDetail> {
  return (await apiClient.post(`/assessments/${id}/revisions`, {})).data;
}

export async function fetchSupervisorWorklist(): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get("/worklists/supervisor")).data;
}

export async function fetchCounselorWorklist(): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get("/worklists/counselor")).data;
}
