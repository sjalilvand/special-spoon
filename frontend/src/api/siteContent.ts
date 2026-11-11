// فاز ۸۴ — ویرایشگر صفحات عمومی سایت: کلاینت API محتوا
import { apiClient } from "./client";

export interface SiteContentPageMeta {
  page_key: string;
  title: string;
  has_draft: boolean;
  has_published: boolean;
  updated_at: string | null;
  updated_by_name: string | null;
  published_at: string | null;
}

export interface SiteContentDefaults {
  [page_key: string]: Record<string, unknown>;
}

export interface SiteContentAdminList {
  pages: SiteContentPageMeta[];
  defaults: SiteContentDefaults;
}

export interface SiteContentPageDetail {
  page_key: string;
  draft: Record<string, unknown> | null;
  published: Record<string, unknown> | null;
  defaults: Record<string, unknown> | null;
  updated_at: string | null;
  updated_by_name: string | null;
  published_at: string | null;
  published_by_name: string | null;
}

export async function fetchSiteContentAdmin(): Promise<SiteContentAdminList> {
  const r = await apiClient.get("/site-content/admin");
  return r.data as SiteContentAdminList;
}

export async function fetchSiteContentPage(pageKey: string): Promise<SiteContentPageDetail> {
  const r = await apiClient.get(`/site-content/admin/${encodeURIComponent(pageKey)}`);
  return r.data as SiteContentPageDetail;
}

export async function saveSiteContentDraft(
  pageKey: string,
  content: Record<string, unknown>,
): Promise<SiteContentPageDetail> {
  const r = await apiClient.put(`/site-content/admin/${encodeURIComponent(pageKey)}`, { content });
  return r.data as SiteContentPageDetail;
}

export async function publishSiteContent(pageKey: string): Promise<SiteContentPageDetail> {
  const r = await apiClient.post(`/site-content/admin/${encodeURIComponent(pageKey)}/publish`);
  return r.data as SiteContentPageDetail;
}

export async function revertSiteContentDraft(pageKey: string): Promise<SiteContentPageDetail> {
  const r = await apiClient.post(`/site-content/admin/${encodeURIComponent(pageKey)}/revert-draft`);
  return r.data as SiteContentPageDetail;
}

export async function resetSiteContent(pageKey: string): Promise<SiteContentPageDetail> {
  const r = await apiClient.post(`/site-content/admin/${encodeURIComponent(pageKey)}/reset`);
  return r.data as SiteContentPageDetail;
}
