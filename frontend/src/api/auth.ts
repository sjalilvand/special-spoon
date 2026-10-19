import { apiClient, paginationOf } from "./client";

export const ROLE_OPTIONS: { code: string; title: string }[] = [
  { code: "SYSTEM_ADMIN", title: "مدیر سامانه" },
  { code: "ORG_MANAGER", title: "مدیر سازمان" },
  { code: "RECEPTION", title: "پذیرش" },
  { code: "COUNSELOR", title: "مشاور" },
  { code: "TECHNICAL_SUPERVISOR", title: "مسئول فنی" },
  { code: "APPLICANT", title: "متقاضی" },
];

export function roleTitle(code: string): string {
  return ROLE_OPTIONS.find((r) => r.code === code)?.title ?? code;
}

export interface Me {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  mobile: string | null;
  status: string;
  must_change_password: boolean;
  roles: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  must_change_password: boolean;
}

export interface UserRow {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  mobile: string | null;
  status: string;
  must_change_password: boolean;
  roles: string[];
  last_login_at: string | null;
  created_at: string | null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await apiClient.post<LoginResponse>("/auth/login", { username, password });
  return res.data;
}

export async function fetchMe(): Promise<Me> {
  const res = await apiClient.get<Me>("/auth/me");
  return res.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout", {});
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function activate(token: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/activate", { token, new_password: newPassword });
}

export async function fetchUsers(params: { search?: string; page: number; page_size: number }): Promise<{
  items: UserRow[];
  total: number;
  page: number;
  page_size: number;
}> {
  const res = await apiClient.get("/users", { params });
  // فاز ۳۹ (v2): data آرایه + total/page/page_size در meta.pagination
  return { items: res.data, ...paginationOf(res) } as {
    items: UserRow[];
    total: number;
    page: number;
    page_size: number;
  };
}

export async function createUser(payload: {
  username: string;
  display_name: string;
  email?: string;
  mobile?: string;
  roles: string[];
}): Promise<UserRow> {
  const res = await apiClient.post("/users", payload);
  return res.data;
}

export async function updateUserStatus(id: string, status: string): Promise<UserRow> {
  const res = await apiClient.patch(`/users/${id}`, { status });
  return res.data;
}

export async function createActivationToken(
  id: string
): Promise<{ token: string; expires_at: string }> {
  const res = await apiClient.post(`/users/${id}/activation-token`);
  return res.data;
}
