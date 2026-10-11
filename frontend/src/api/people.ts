import { apiClient } from "./client";

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
  work_mobile: string | null;
  email: string | null;
  capacity: number | null;
  service_location_title: string | null;
  status: string;
  has_account: boolean;
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
  return (await apiClient.get("/counselors", { params: { ...params, page_size: 10 } })).data;
}

export async function createCounselor(payload: Record<string, unknown>): Promise<Counselor> {
  return (await apiClient.post("/counselors", payload)).data;
}

export async function updateCounselor(id: string, payload: Record<string, unknown>): Promise<Counselor> {
  return (await apiClient.patch(`/counselors/${id}`, payload)).data;
}

export async function fetchApplicants(params: { search?: string; page: number }): Promise<Paged<Applicant>> {
  return (await apiClient.get("/applicants", { params: { ...params, page_size: 10 } })).data;
}

export async function createApplicant(payload: Record<string, unknown>): Promise<Applicant> {
  return (await apiClient.post("/applicants", payload)).data;
}
