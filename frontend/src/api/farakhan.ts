import { apiClient, paginationOf } from "./client";

/** فاز ۸۸ - پنل فراخوان همکاری: فهرست/جزئیات/وضعیت/اکسل ثبت‌نام‌های فرم عمومی */

export interface FarakhanSubmissionRow {
  id: string;
  tracking_code: string;
  first_name: string;
  last_name: string;
  national_code: string;
  gender: string;
  gender_label: string;
  birth_date_jalali: string;
  military_status: string | null;
  military_status_label: string | null;
  education_degree: string;
  education_degree_label: string;
  education_field: string;
  license_status: string;
  license_status_label: string;
  license_number: string | null;
  license_description: string | null;
  center_ownership: string;
  center_ownership_label: string;
  province_name: string;
  county_name: string;
  phone: string;
  mobile_number: string | null;
  postal_code: string | null;
  address: string | null;
  individual_rooms: number;
  group_rooms: number;
  child_rooms: number;
  counselors_count: number;
  has_waiting_space: boolean;
  accepts_company_pattern: boolean;
  has_accessibility: boolean;
  status: "new" | "reviewed" | "accepted" | "rejected";
  status_label: string;
  review_note: string | null;
  reviewed_at: string | null;
  submit_ip: string | null;
  file_count: number;
  created_at: string | null;
}

export interface FarakhanFileRow {
  id: string;
  file_id: string;
  field_key: string;
  field_label: string;
  original_name: string;
  size_bytes: number;
}

export type FarakhanSubmissionDetail = FarakhanSubmissionRow & { files: FarakhanFileRow[] };

export interface FarakhanFilters {
  q?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function fetchFarakhanSubmissions(
  filters: FarakhanFilters,
): Promise<{ items: FarakhanSubmissionRow[]; total: number; page: number; page_size: number }> {
  const res = await apiClient.get<FarakhanSubmissionRow[]>("/farakhan/admin/submissions", { params: filters });
  const pag = paginationOf(res);
  const items = Array.isArray(res.data) ? res.data : [];
  return {
    items,
    total: Number(pag.total ?? items.length),
    page: Number(pag.page ?? 1),
    page_size: Number(pag.page_size ?? 20),
  };
}

export async function fetchFarakhanSubmission(id: string): Promise<FarakhanSubmissionDetail> {
  const res = await apiClient.get<FarakhanSubmissionDetail>(`/farakhan/admin/submissions/${id}`);
  return res.data;
}

export async function setFarakhanSubmissionStatus(
  id: string,
  status: string,
  note?: string,
): Promise<FarakhanSubmissionRow> {
  const res = await apiClient.put<FarakhanSubmissionRow>(`/farakhan/admin/submissions/${id}/status`, {
    status,
    note: note || null,
  });
  return res.data;
}

/** دانلود امن فایل فراخوان با بلیت کوتاه‌مدت (الگوی B39 مسیر اختصاصی فراخوان) */
export async function downloadFarakhanFile(fileId: string): Promise<void> {
  const { data } = await apiClient.post<{ ticket: string }>(`/farakhan/admin/files/${fileId}/download-ticket`);
  const base = apiClient.defaults.baseURL ?? "/api/v2";
  window.open(`${base}/farakhan/admin/files/${fileId}/download?ticket=${encodeURIComponent(data.ticket)}`, "_blank");
}

export async function exportFarakhanSubmissions(status: string): Promise<void> {
  const res = await apiClient.get("/farakhan/admin/export", {
    params: status ? { status } : {},
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([res.data as unknown as BlobPart]));
  const link = document.createElement("a");
  link.href = url;
  link.download = "farakhan-submissions.xlsx";
  link.click();
  window.URL.revokeObjectURL(url);
}
