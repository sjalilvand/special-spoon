// فاز ۳۳ - B21 سند جامع: سازمان‌ها، قراردادها و سهم پرداخت
import { apiClient } from "./client";

export interface ActiveContractRef {
  id: string;
  title: string;
  coverage_percent: number;
  valid_from: string;
  valid_to: string | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  national_id: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  note: string | null;
  is_active: boolean;
  contract_count: number;
  active_contract: ActiveContractRef | null;
  created_at: string | null;
}

export interface ContractServiceRef {
  id: string;
  title: string;
}

export interface Contract {
  id: string;
  organization_id: string;
  organization_name: string | null;
  title: string;
  coverage_percent: number;
  coverage_cap_amount: number | null;
  valid_from: string;
  valid_to: string | null;
  status: "draft" | "active" | "terminated";
  notes: string | null;
  services: ContractServiceRef[];
  created_at: string | null;
}

export interface ReceivableRow {
  order_id: string;
  order_number: string;
  title: string;
  amount: number;
  coverage_percent: number | null;
  org_share_amount: number;
  applicant_share_amount: number;
  status: string;
  created_at: string | null;
}

export interface ReceivablesReport {
  organization_id: string;
  organization_name: string;
  paid_orders_with_share: number;
  total_amount: number;
  org_share_total: number;
  applicant_share_total: number;
  note: string;
  items: ReceivableRow[];
}

export async function fetchOrganizations(): Promise<Organization[]> {
  const r = await apiClient.get<{ items: Organization[] }>("/organizations");
  return r.data.items;
}

export async function createOrganization(payload: Record<string, unknown>): Promise<Organization> {
  const r = await apiClient.post<Organization>("/organizations", payload);
  return r.data;
}

export async function updateOrganization(id: string, payload: Record<string, unknown>): Promise<Organization> {
  const r = await apiClient.patch<Organization>(`/organizations/${id}`, payload);
  return r.data;
}

export async function fetchContracts(orgId: string): Promise<Contract[]> {
  const r = await apiClient.get<{ items: Contract[] }>(`/organizations/${orgId}/contracts`);
  return r.data.items;
}

export async function createContract(orgId: string, payload: Record<string, unknown>): Promise<Contract> {
  const r = await apiClient.post<Contract>(`/organizations/${orgId}/contracts`, payload);
  return r.data;
}

export async function updateContract(id: string, payload: Record<string, unknown>): Promise<Contract> {
  const r = await apiClient.patch<Contract>(`/contracts/${id}`, payload);
  return r.data;
}

export async function fetchReceivables(orgId: string): Promise<ReceivablesReport> {
  const r = await apiClient.get<ReceivablesReport>(`/organizations/${orgId}/receivables`);
  return r.data;
}
