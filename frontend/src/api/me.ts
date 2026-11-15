import { apiClient } from "./client";

export interface MyProfile {
  first_name: string;
  last_name: string;
  national_id: string | null;
  employee_code: string | null;
  mobile: string | null;
  unit_title: string | null;
  service_location_title: string | null;
}

export interface MyCaseRow {
  id: string;
  case_number: string;
  status: string;
  acceptance_date: string;
  counselor_name: string | null;
  consent_status: string;
  service_type: string | null;
}

export interface MyAppointmentRow {
  id: string;
  case_number: string;
  scheduled_at: string;
  status: string;
  location: string | null;
}

export interface MyRecommendationRow {
  id: string;
  case_number: string;
  content: string;
  published_at: string | null;
}

export async function fetchMyProfile(): Promise<MyProfile> {
  return (await apiClient.get("/me/profile")).data;
}

export async function fetchMyCases(): Promise<{ items: MyCaseRow[] }> {
  return (await apiClient.get("/me/cases")).data;
}

export async function fetchMyAppointments(): Promise<{ items: MyAppointmentRow[] }> {
  return (await apiClient.get("/me/appointments")).data;
}

export async function fetchMyRecommendations(): Promise<{ items: MyRecommendationRow[] }> {
  return (await apiClient.get("/me/recommendations")).data;
}

// فاز ۸۷ — آزمون‌های سازمانی من: برنامه‌های فعال سازمانِ کاربر عضو + وضعیت هر آزمون
export interface MyOrgExamTest {
  test_id: string;
  test_slug: string;
  title: string;
  is_required: boolean;
  done: boolean;
  score: number | null;
  interpretation_label: string | null;
  completed_at: string | null;
}

export interface MyOrgExamProgram {
  id: string;
  title: string;
  due_date: string | null;
  tests: MyOrgExamTest[];
}

export async function fetchMyOrgExams(): Promise<{ items: MyOrgExamProgram[] }> {
  return (await apiClient.get("/me/org-exams")).data;
}
