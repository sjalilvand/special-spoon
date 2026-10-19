import { apiClient } from "./client";

export interface FileItem {
  id: string;
  case_id: string | null;
  context: string;
  original_name: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  sensitivity: string;
  scan_status: "pending" | "clean" | "quarantined" | "failed";
  created_at: string | null;
  scan_detail?: string;
}

export async function fetchCaseFiles(caseId: string): Promise<FileItem[]> {
  const { data } = await apiClient.get<{ items: FileItem[] }>("/files", { params: { case_id: caseId } });
  return data.items;
}

export async function uploadCaseFile(caseId: string, file: File): Promise<FileItem> {
  const form = new FormData();
  form.append("file", file);
  form.append("case_id", caseId);
  form.append("context", "case_document");
  const { data } = await apiClient.post<FileItem>("/files/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** بلیت کوتاه‌مدت بگیر و پنجره دانلود را باز کن (B39: لینک امضاشده کوتاه‌مدت) */
export async function downloadFileWithTicket(fileId: string): Promise<void> {
  const { data } = await apiClient.post<{ ticket: string }>(`/files/${fileId}/download-ticket`);
  const base = apiClient.defaults.baseURL ?? "/api/v2";
  window.open(`${base}/files/${fileId}/download?ticket=${encodeURIComponent(data.ticket)}`, "_blank");
}
