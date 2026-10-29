// فاز ۵۹ - کارتابل شخصی هر حساب + نمای مدیریتی سطح دسترسی
import { apiClient } from "./client";

export interface CartableRole {
  code: string;
  title: string;
  data_scope: string;
  data_scope_title: string;
}

export interface CartablePermissionSection {
  section: string;
  permissions: { code: string; title: string }[];
  count: number;
}

export interface CartableOpenWork {
  id: string;
  definition_title: string | null;
  definition_code: string | null;
  subject_label: string | null;
  subject_type: string;
  status: string;
  current_element_name: string | null;
  current_element_id: string | null;
  updated_at: string | null;
}

export interface CartableActivity {
  id: string;
  action: string;
  action_label: string;
  entity_type: string | null;
  entity_id: string | null;
  result: string;
  created_at: string | null;
}

export interface CartableData {
  user: {
    id: string;
    username: string;
    display_name: string;
    email: string | null;
    mobile: string | null;
    status: string;
    last_login_at: string | null;
    created_at: string | null;
  };
  roles: CartableRole[];
  permissions: {
    sections: CartablePermissionSection[];
    total: number;
    wildcard: boolean;
  };
  stats: {
    open_work: number;
    recorded_steps: number;
    audit_events: number;
  };
  open_work: CartableOpenWork[];
  recent_activity: CartableActivity[];
  viewer_is_admin: boolean;
}

/** کارتابل کاربر جاری — همهٔ حساب‌های فعال */
export async function fetchMyCartable(): Promise<CartableData> {
  return (await apiClient.get<CartableData>("/cartable/me")).data;
}

/** کارتابل هر شخص از نقطهٔ نظر خودش — فقط مدیر سامانه (از صفحهٔ کاربران) */
export async function fetchUserCartable(userId: string): Promise<CartableData> {
  return (await apiClient.get<CartableData>(`/cartable/users/${userId}`)).data;
}
