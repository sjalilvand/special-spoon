// فاز ۴۹ - B41/B42: فرایندهای سازمانی نسخه‌دار + مانیتورینگ وضعیت درخواست
import { apiClient, paginationOf } from "./client";

export interface ProcessVersionInfo {
  id: string;
  definition_id: string;
  version_number: number;
  changelog: string | null;
  status: "draft" | "published" | "archived";
  published_at: string | null;
  created_at: string | null;
  bpmn_xml?: string;
}

export interface ProcessDefinitionInfo {
  id: string;
  code: string;
  title: string;
  description: string | null;
  is_active: boolean;
  versions: ProcessVersionInfo[];
  current_version: ProcessVersionInfo | null;
  instances_count: number;
  created_at: string | null;
}

export interface ProcessEventInfo {
  id: string;
  element_id: string | null;
  element_name: string;
  element_type: string | null;
  status: "done" | "active" | "pending" | "skipped" | "failed";
  note: string | null;
  actor_id: string | null;
  occurred_at: string | null;
}

export interface ProcessInstanceInfo {
  id: string;
  definition_id: string;
  definition_code: string | null;
  definition_title: string | null;
  version_number: number | null;
  subject_type: string;
  subject_id: string;
  subject_label: string | null;
  subject_meta: Record<string, unknown> | null;
  status: "running" | "suspended" | "completed" | "cancelled";
  status_label: string;
  current_element_id: string | null;
  current_element_name: string | null;
  note: string | null;
  started_at: string | null;
  finished_at: string | null;
  events?: ProcessEventInfo[];
}

export async function fetchProcesses(): Promise<ProcessDefinitionInfo[]> {
  const r = await apiClient.get<{ items: ProcessDefinitionInfo[] }>("/processes");
  return r.data.items;
}

export async function createProcess(payload: {
  code: string;
  title: string;
  description?: string;
  bpmn_xml: string;
  changelog?: string;
  publish?: boolean;
}): Promise<ProcessDefinitionInfo> {
  return (await apiClient.post("/processes", payload)).data;
}

export async function fetchProcessVersionsXML(versionId: string): Promise<ProcessVersionInfo> {
  return (await apiClient.get(`/processes/versions/${versionId}`)).data;
}

export async function createProcessVersion(definitionId: string, payload: {
  bpmn_xml: string;
  changelog?: string;
  publish?: boolean;
}): Promise<ProcessVersionInfo> {
  return (await apiClient.post(`/processes/${definitionId}/versions`, payload)).data;
}

export async function publishProcessVersion(versionId: string): Promise<ProcessVersionInfo> {
  return (await apiClient.post(`/processes/versions/${versionId}/publish`)).data;
}

export async function archiveProcessVersion(versionId: string): Promise<ProcessVersionInfo> {
  return (await apiClient.post(`/processes/versions/${versionId}/archive`)).data;
}

export async function fetchProcessInstances(params: {
  subject_type?: string;
  subject_id?: string;
  status?: string;
  definition_id?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: ProcessInstanceInfo[]; total: number }> {
  const r = await apiClient.get("/process-instances", { params });
  return { items: r.data, total: Number(paginationOf(r).total ?? 0) };
}

export async function fetchProcessInstance(id: string): Promise<ProcessInstanceInfo> {
  return (await apiClient.get(`/process-instances/${id}`)).data;
}

export async function startProcessInstance(payload: {
  definition_id: string;
  subject_type: string;
  subject_id: string;
  subject_label?: string;
  subject_meta?: Record<string, unknown>;
  note?: string;
}): Promise<ProcessInstanceInfo> {
  return (await apiClient.post("/process-instances", payload)).data;
}

export async function recordProcessEvent(instanceId: string, payload: {
  element_id?: string;
  element_name: string;
  element_type?: string;
  status?: string;
  note?: string;
}): Promise<ProcessInstanceInfo> {
  return (await apiClient.post(`/process-instances/${instanceId}/events`, payload)).data;
}

export async function transitionProcessInstance(instanceId: string, payload: {
  action: "complete" | "cancel" | "suspend" | "resume";
  note?: string;
}): Promise<ProcessInstanceInfo> {
  return (await apiClient.post(`/process-instances/${instanceId}/transition`, payload)).data;
}
