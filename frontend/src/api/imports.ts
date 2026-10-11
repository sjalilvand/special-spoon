import { apiClient } from "./client";

export type ImportType = "users" | "counselors" | "applicants";

export interface ImportPreviewRow {
  row_number: number;
  error?: string | null;
  existing_id?: string | null;
  will_update?: string[];
}

export interface ImportPreview {
  job_id: string;
  summary: { total: number; valid: number; error: number; duplicate: number };
  errors: ImportPreviewRow[];
  duplicates: ImportPreviewRow[];
}

export interface ImportReport {
  job_id: string;
  import_type: string;
  status: string;
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
}

export interface ImportJobRow {
  id: string;
  import_type: string;
  status: string;
  original_filename: string;
  total_rows: number;
  created_rows: number;
  updated_rows: number;
  skipped_rows: number;
  error_rows: number;
  created_at: string | null;
}

export async function downloadTemplate(type: ImportType): Promise<void> {
  const res = await apiClient.get(`/imports/templates/${type}`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rosepsy-${type}-template.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function previewImport(type: ImportType, file: File): Promise<ImportPreview> {
  const form = new FormData();
  form.append("file", file);
  return (await apiClient.post(`/imports/${type}/preview`, form)).data;
}

export async function commitImport(jobId: string, duplicateStrategy: "skip" | "update"): Promise<ImportReport> {
  return (await apiClient.post(`/imports/${jobId}/commit`, { duplicate_strategy: duplicateStrategy })).data;
}

export async function fetchImportJobs(): Promise<{ items: ImportJobRow[] }> {
  return (await apiClient.get("/imports")).data;
}
