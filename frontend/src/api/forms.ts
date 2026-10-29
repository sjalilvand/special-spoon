import { apiClient } from "./client";

/** فاز ۶۱ - فرم‌ساز و نظرسنجی: انواع فیلد + API مدیریت فرم و تکمیل فرم */

export type FormFieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "select"
  | "radio"
  | "checkbox"
  | "rating"
  | "yesno"
  | "heading";

export const FORM_FIELD_TYPE_LABELS: Record<FormFieldType, string> = {
  text: "متن کوتاه",
  textarea: "متن بلند",
  number: "عدد",
  date: "تاریخ (شمسی)",
  select: "فهرست بسته",
  radio: "چندگزینه‌ای",
  checkbox: "چندانتخابی",
  rating: "امتیاز ۱ تا ۵",
  yesno: "بله / خیر",
  heading: "سرصفحهٔ بخش",
};

export interface FormFieldDef {
  id: string;
  type: FormFieldType;
  label: string;
  required?: boolean;
  options?: string[];
  help?: string;
}

export interface FormTemplate {
  id: string;
  code: string;
  title: string;
  description: string | null;
  kind: "survey" | "intake" | "custom";
  fields: FormFieldDef[];
  is_active: boolean;
  is_default_call_survey: boolean;
  response_count?: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface FormUpsertPayload {
  title: string;
  code?: string;
  description?: string;
  kind: FormTemplate["kind"];
  fields: FormFieldDef[];
  is_active: boolean;
  is_default_call_survey: boolean;
}

export interface FormResponseRow {
  id: string;
  respondent_id: string | null;
  respondent_name: string | null;
  answers: Record<string, unknown>;
  call_id: string | null;
  call_duration_sec: number | null;
  submitted_at: string | null;
}

export interface PendingForm {
  call_id: string;
  template: FormTemplate;
  caller_name: string | null;
  call_ended_at: string | null;
  call_duration_sec: number;
}

export interface MyFormsData {
  pending: PendingForm[];
  history: {
    id: string;
    template_title: string | null;
    template_id: string;
    call_id: string | null;
    submitted_at: string | null;
  }[];
}

// ---------- مدیریت (admin) ----------
export async function fetchFormTemplates(): Promise<FormTemplate[]> {
  const res = await apiClient.get<{ items: FormTemplate[] }>("/form-templates/admin");
  return res.data.items;
}

export async function createFormTemplate(payload: FormUpsertPayload): Promise<FormTemplate> {
  const res = await apiClient.post<FormTemplate>("/form-templates/admin", payload);
  return res.data;
}

export async function updateFormTemplate(id: string, payload: FormUpsertPayload): Promise<FormTemplate> {
  const res = await apiClient.put<FormTemplate>(`/form-templates/admin/${id}`, payload);
  return res.data;
}

export async function deleteFormTemplate(id: string): Promise<void> {
  await apiClient.delete(`/form-templates/admin/${id}`);
}

export async function fetchFormResponses(templateId: string): Promise<{
  template: FormTemplate;
  items: FormResponseRow[];
}> {
  const res = await apiClient.get<{ template: FormTemplate; items: FormResponseRow[] }>(
    `/form-templates/admin/${templateId}/responses`,
  );
  return res.data;
}

// ---------- تکمیل فرم (همهٔ کاربران) ----------
export async function fetchMyForms(): Promise<MyFormsData> {
  const res = await apiClient.get<MyFormsData>("/form-templates/mine");
  return res.data;
}

export async function fetchFormTemplateForFill(templateId: string): Promise<FormTemplate> {
  const res = await apiClient.get<FormTemplate>(`/form-templates/public/${templateId}`);
  return res.data;
}

export async function submitFormResponse(
  templateId: string,
  answers: Record<string, unknown>,
  callId?: string,
): Promise<{ ok: boolean; id: string; template_title: string }> {
  const res = await apiClient.post(`/form-templates/public/${templateId}/responses`, {
    answers,
    call_id: callId || undefined,
  });
  return res.data;
}
