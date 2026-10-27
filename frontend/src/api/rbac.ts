import { apiClient } from "./client";

/** فاز ۵۲ - RBAC گرافیکی: کاتالوگ دسترسی‌ها + نقش‌ها + ماتریس */

export interface PermissionItem {
  code: string;
  title: string;
}

export interface PermissionSection {
  section: string;
  permissions: PermissionItem[];
}

export interface RoleRow {
  code: string;
  title: string;
  data_scope: string;
  data_scope_title: string;
  permissions: string[];
  is_system: boolean;
  member_count?: number;
}

export async function fetchPermissionCatalog(): Promise<PermissionSection[]> {
  const res = await apiClient.get<{ sections: PermissionSection[]; total: number }>("/rbac/permissions");
  return res.data.sections;
}

export async function fetchRoles(): Promise<RoleRow[]> {
  const res = await apiClient.get<{ items: RoleRow[] }>("/rbac/roles");
  return res.data.items;
}

export async function saveRolePermissions(
  code: string,
  payload: { title: string; data_scope: string; permissions: string[] },
): Promise<RoleRow> {
  const res = await apiClient.put<RoleRow>(`/rbac/roles/${encodeURIComponent(code)}`, payload);
  return res.data;
}

export async function createRole(
  code: string,
  payload: { title: string; data_scope: string; permissions: string[] },
): Promise<RoleRow> {
  const res = await apiClient.post<RoleRow>(`/rbac/roles/${encodeURIComponent(code)}`, payload);
  return res.data;
}

export async function deleteRole(code: string): Promise<void> {
  await apiClient.delete(`/rbac/roles/${encodeURIComponent(code)}`);
}

export const DATA_SCOPE_OPTIONS: { value: string; title: string; hint: string }[] = [
  { value: "all", title: "همهٔ داده‌ها", hint: "کاربر همهٔ رکوردهای سامانه را می‌بیند" },
  { value: "assigned", title: "داده‌های تخصیص‌یافته", hint: "فقط پرونده‌ها/نوبت‌های واگذارشده به کاربر" },
  { value: "own", title: "فقط داده‌های خودم", hint: "فقط رکوردهای ثبت‌شده توسط خود کاربر" },
];

export function dataScopeTitle(scope: string): string {
  return DATA_SCOPE_OPTIONS.find((o) => o.value === scope)?.title ?? scope;
}
