import { apiClient, paginationOf } from "./client";

export interface IdName {
  id: string;
  code: string;
  title: string;
}

export interface Counselor {
  id: string;
  counselor_code: string;
  first_name: string;
  last_name: string;
  national_id: string | null;
  professional_title: string | null;
  degree: string | null;
  specialty: string | null;
  license_number: string | null;
  license_expiry_date: string | null;
  license_verified?: boolean;
  work_mobile: string | null;
  email: string | null;
  capacity: number | null;
  service_location_title: string | null;
  // فاز ۶۴: فیلدهای فایل ورود مشاوران شرکت رز
  province_code?: string | null;
  province_name?: string | null;
  professional_rank?: string | null;
  contract_number?: string | null;
  sheba_number?: string | null;
  detailed_code?: string | null;
  status: string;
  has_account: boolean;
  // فاز ۲۸ - B05: وضعیت صلاحیت برای فهرست قابل رزرو
  bookable?: boolean;
  approved_credentials?: number;
  pending_credentials?: number;
}

export interface Applicant {
  id: string;
  external_id: string | null;
  employee_code: string | null;
  national_id: string | null;
  first_name: string;
  last_name: string;
  birth_date: string | null;
  gender: string | null;
  mobile: string | null;
  unit_title: string | null;
  organization_id: string | null;
  organization_name: string | null;
  service_location_title: string | null;
  referral_source: string | null;
  status: string;
  record_source: string;
  has_account: boolean;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchOrgUnits(): Promise<IdName[]> {
  return (await apiClient.get("/org/units")).data.items;
}

export async function fetchServiceLocations(): Promise<IdName[]> {
  return (await apiClient.get("/org/locations")).data.items;
}

export async function fetchCounselors(params: { search?: string; page: number }): Promise<Paged<Counselor>> {
  // فاز ۳۹ (v2): پاسخ صفحه‌بندی‌شده → data آرایه + total/page در meta.pagination
  const r = await apiClient.get("/counselors", { params: { ...params, page_size: 10 } });
  return { items: r.data, ...paginationOf(r) } as Paged<Counselor>;
}

export async function createCounselor(payload: Record<string, unknown>): Promise<Counselor> {
  return (await apiClient.post("/counselors", payload)).data;
}

export async function updateCounselor(id: string, payload: Record<string, unknown>): Promise<Counselor> {
  return (await apiClient.patch(`/counselors/${id}`, payload)).data;
}

export async function fetchApplicants(params: { search?: string; page: number }): Promise<Paged<Applicant>> {
  const r = await apiClient.get("/applicants", { params: { ...params, page_size: 10 } });
  return { items: r.data, ...paginationOf(r) } as Paged<Applicant>;
}

export async function createApplicant(payload: Record<string, unknown>): Promise<Applicant> {
  return (await apiClient.post("/applicants", payload)).data;
}

// ---------------- فاز ۸۷: حساب/توکن/درخواست/پروندهٔ الکترونیکی متقاضی ----------------

export async function createApplicantAccount(id: string, username: string): Promise<{ ok: boolean; username: string }> {
  return (await apiClient.post(`/applicants/${id}/account`, { username })).data;
}

export async function createApplicantActivationLink(id: string): Promise<{ username: string; activation_path: string; expires_at: string }> {
  return (await apiClient.post(`/applicants/${id}/activation-link`)).data;
}

export async function createApplicantRequest(
  id: string,
  payload: { topic: string; message?: string; preferred_date?: string; request_type?: string; city?: string },
): Promise<Record<string, unknown>> {
  return (await apiClient.post(`/applicants/${id}/requests`, payload)).data;
}

export async function enrollApplicantOrgPrograms(id: string): Promise<{ ok: boolean; programs: number; added: number }> {
  return (await apiClient.post(`/applicants/${id}/enroll-org-programs`)).data;
}

export interface ApplicantSummary {
  applicant: Applicant;
  organization_name: string | null;
  unit_title: string | null;
  user: { id: string; username: string; status: string; token_hours: number | null } | null;
  requests: { id: string; topic: string; status: string; request_type: string | null; created_at: string | null; case_id: string | null }[];
  intakes: { id: string; request_id: string; status: string; created_at: string | null }[];
  cases: { id: string; case_number: string; status: string; acceptance_date: string | null }[];
  timeline: { kind: string; id: string; title: string; at: string | null; status?: string; [k: string]: unknown }[];
}

export async function fetchApplicantSummary(id: string): Promise<ApplicantSummary> {
  return (await apiClient.get(`/applicants/${id}/summary`)).data;
}

// ---------------- فاز ۶۴: استان‌های پایه (کد رسمی ۰۱..۳۱) + ورود گروهی مشاوران ----------------

export interface Province {
  code: string;
  name: string;
  capital: string | null;
  area_code: string | null;
  is_active: boolean;
}

export async function fetchProvinces(): Promise<Province[]> {
  return (await apiClient.get("/provinces")).data.items;
}

export interface CounselorImportResult {
  total: number;
  created: number;
  updated: number;
  failed: number;
  errors: { row: number; message: string }[];
}

/** دانلود قالب اکسل ورود مشاوران (همان ستون‌های فایل «اسامی مشاورین») */
export async function downloadCounselorsTemplate(): Promise<void> {
  const res = await apiClient.get("/counselors/import-template", { responseType: "blob" });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "rosepsy-counselors-import-template.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

export async function importCounselors(file: File): Promise<CounselorImportResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiClient.post("/counselors/import", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}
