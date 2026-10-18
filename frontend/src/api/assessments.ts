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

export interface FormSummary {
  code: string;
  title: string;
  description: string;
  usage: string;
  version: number;
}

export interface FormHead {
  code: string;
  title: string;
  description: string;
  usage: string;
  version: number;
  definition: FormDefinition;
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
  form_code: string | null;
  form_title: string | null;
  form_version: number | null;
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
  form_code: string | null;
  form_title: string | null;
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

export async function fetchForms(): Promise<{ items: FormSummary[] }> {
  return (await apiClient.get("/forms")).data;
}

export async function fetchFormHead(code: string): Promise<FormHead> {
  return (await apiClient.get(`/forms/${encodeURIComponent(code)}`)).data;
}

export async function fetchFormDefinition(code: string = "RS-PS-04-01"): Promise<FormDefinition> {
  const head = await fetchFormHead(code);
  return { code: head.code, version: head.version, sections: head.definition.sections };
}

export async function fetchCaseAssessments(caseId: string): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get(`/cases/${caseId}/assessments`)).data;
}

export async function fetchAssessment(id: string): Promise<AssessmentDetail> {
  return (await apiClient.get(`/assessments/${id}`)).data;
}

export async function createAssessmentDraft(caseId: string, answers: Record<string, unknown>, formCode?: string): Promise<AssessmentDetail> {
  return (await apiClient.post(`/cases/${caseId}/assessments`, { answers, form_code: formCode || null })).data;
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

export interface Level3CartItem extends AssessmentListItem {
  severity_label: string | null;
  person_name: string | null;
  person_phone: string | null;
  risk_types: string[];
  immediate_action: string | null;
  referral_destination: string | null;
  referral_result: string | null;
}

export interface Level3CartResponse {
  items: Level3CartItem[];
  total_level3: number;
}

export async function fetchLevel3Cartable(): Promise<Level3CartResponse> {
  return (await apiClient.get("/worklists/level3")).data;
}

export async function fetchSupervisorWorklist(): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get("/worklists/supervisor")).data;
}

export async function fetchCounselorWorklist(): Promise<{ items: AssessmentListItem[] }> {
  return (await apiClient.get("/worklists/counselor")).data;
}
