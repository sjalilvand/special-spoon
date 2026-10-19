// فاز ۲۹ - B31 سند جامع: مراکز مشاوره و شعب
import { apiClient } from "./client";

export interface Clinic {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  phone: string | null;
  website: string | null;
  is_active: boolean;
  branch_count: number;
  created_at: string | null;
}

export interface BranchServiceRef {
  id: string;
  title: string;
  duration_minutes?: number;
  session_type?: string;
  is_active?: boolean;
}

export interface Branch {
  id: string;
  clinic_id: string;
  name: string;
  province: string | null;
  city: string | null;
  address: string | null;
  postal_code: string | null;
  phone: string | null;
  working_hours: Record<string, unknown> | null;
  latitude: number | null;
  longitude: number | null;
  status: "draft" | "published";
  clinic_name?: string | null;
  services?: BranchServiceRef[];
  created_at: string | null;
}

export interface ServiceLite {
  id: string;
  title: string;
  status: string;
}

export async function fetchClinics(): Promise<Clinic[]> {
  const r = await apiClient.get<{ items: Clinic[] }>("/clinics");
  return r.data.items;
}

export async function createClinic(payload: Record<string, unknown>): Promise<Clinic> {
  const r = await apiClient.post<Clinic>("/clinics", payload);
  return r.data;
}

export async function updateClinic(id: string, payload: Record<string, unknown>): Promise<Clinic> {
  const r = await apiClient.patch<Clinic>(`/clinics/${id}`, payload);
  return r.data;
}

export async function fetchBranches(clinicId: string): Promise<Branch[]> {
  const r = await apiClient.get<{ items: Branch[] }>(`/clinics/${clinicId}/branches`);
  return r.data.items;
}

export async function createBranch(clinicId: string, payload: Record<string, unknown>): Promise<Branch> {
  const r = await apiClient.post<Branch>(`/clinics/${clinicId}/branches`, payload);
  return r.data;
}

export async function updateBranch(id: string, payload: Record<string, unknown>): Promise<Branch> {
  const r = await apiClient.patch<Branch>(`/branches/${id}`, payload);
  return r.data;
}

export async function setBranchOfferings(id: string, serviceIds: string[]): Promise<Branch> {
  const r = await apiClient.put<Branch>(`/branches/${id}/offerings`, { service_ids: serviceIds });
  return r.data;
}

export async function fetchPublicBranches(params?: {
  city?: string;
  service_id?: string;
}): Promise<Branch[]> {
  const q: Record<string, string> = {};
  if (params?.city) q.city = params.city;
  if (params?.service_id) q.service_id = params.service_id;
  const r = await apiClient.get<{ items: Branch[] }>("/public/branches", { params: q });
  return r.data.items;
}

export async function fetchAllServices(): Promise<ServiceLite[]> {
  const r = await apiClient.get<{ items: ServiceLite[] }>("/services", {
    params: { page_size: 100 },
  });
  return r.data.items.map((s) => ({ id: s.id, title: s.title, status: s.status }));
}
