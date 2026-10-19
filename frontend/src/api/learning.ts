// فاز ۳۴ - B33/B34/B35/B36 سند جامع: محتوا، دوره، آزمون و گواهی
import { apiClient } from "./client";

// ---------------------------------------------------------------- B33 محتوا
export interface ContentItem {
  id: string;
  slug: string;
  title: string;
  summary: string | null;
  body: string;
  topic_id: string | null;
  topic_name: string | null;
  status: "draft" | "published";
  published_at: string | null;
  created_at: string | null;
}

export async function fetchContents(includeUnpublished = true): Promise<ContentItem[]> {
  const r = await apiClient.get<{ items: ContentItem[] }>("/contents", {
    params: { include_unpublished: includeUnpublished },
  });
  return r.data.items;
}

export async function createContent(payload: Record<string, unknown>): Promise<ContentItem> {
  const r = await apiClient.post<ContentItem>("/contents", payload);
  return r.data;
}

export async function updateContent(id: string, payload: Record<string, unknown>): Promise<ContentItem> {
  const r = await apiClient.patch<ContentItem>(`/contents/${id}`, payload);
  return r.data;
}

export async function deleteContent(id: string): Promise<void> {
  await apiClient.delete(`/contents/${id}`);
}

// ---------------------------------------------------------------- B34 دوره
export interface CourseSession {
  id: string;
  title: string;
  session_date: string;
  duration_minutes: number;
  sort_order: number;
}

export interface Course {
  id: string;
  slug: string;
  title: string;
  summary: string | null;
  description: string | null;
  topic_id: string | null;
  topic_name: string | null;
  status: "draft" | "published";
  price_amount: number;
  currency: string;
  is_free: boolean;
  capacity: number | null;
  starts_at: string | null;
  enrolled_count?: number;
  remaining_capacity?: number | null;
  sessions?: CourseSession[];
  created_at: string | null;
}

export interface Enrollment {
  id: string;
  course_id: string;
  user_id: string;
  username: string | null;
  display_name: string | null;
  status: "pending" | "active" | "completed" | "cancelled";
  order_id: string | null;
  order_number: string | null;
  order_status: string | null;
  activated_at: string | null;
  created_at: string | null;
}

export async function fetchCourses(includeUnpublished = true): Promise<Course[]> {
  const r = await apiClient.get<{ items: Course[] }>("/courses", {
    params: { include_unpublished: includeUnpublished },
  });
  return r.data.items;
}

export async function createCourse(payload: Record<string, unknown>): Promise<Course> {
  const r = await apiClient.post<Course>("/courses", payload);
  return r.data;
}

export async function updateCourse(id: string, payload: Record<string, unknown>): Promise<Course> {
  const r = await apiClient.patch<Course>(`/courses/${id}`, payload);
  return r.data;
}

export async function deleteCourse(id: string): Promise<void> {
  await apiClient.delete(`/courses/${id}`);
}

export async function createCourseSession(
  courseId: string,
  payload: Record<string, unknown>,
): Promise<CourseSession> {
  const r = await apiClient.post<CourseSession>(`/courses/${courseId}/sessions`, payload);
  return r.data;
}

export async function deleteCourseSession(courseId: string, sessionId: string): Promise<void> {
  await apiClient.delete(`/courses/${courseId}/sessions/${sessionId}`);
}

export async function fetchEnrollments(courseId: string): Promise<Enrollment[]> {
  const r = await apiClient.get<{ items: Enrollment[] }>(`/courses/${courseId}/enrollments`);
  return r.data.items;
}

export async function updateEnrollment(
  id: string,
  payload: Record<string, unknown>,
): Promise<{ id: string; status: string; certificates: Certificate[] }> {
  const r = await apiClient.patch(`/enrollments/${id}`, payload);
  return r.data;
}

// ---------------------------------------------------------------- B35 آزمون
export interface Exam {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  topic_id: string | null;
  topic_name: string | null;
  course_id: string | null;
  course_title: string | null;
  status: "draft" | "published";
  duration_minutes: number;
  pass_percent: number;
  price_amount: number;
  currency: string;
  is_free: boolean;
  max_attempts: number;
  question_count?: number;
  created_at: string | null;
}

export interface ExamQuestion {
  id: string;
  exam_id: string;
  prompt: string;
  options: string[];
  points: number;
  sort_order: number;
  correct_index?: number; // فقط برای کارکنان
}

export interface ExamAttempt {
  id: string;
  exam_id: string;
  user_id: string;
  status: "in_progress" | "passed" | "failed";
  score_percent: number | null;
  started_at: string | null;
  submitted_at: string | null;
}

export async function fetchExams(includeUnpublished = true): Promise<Exam[]> {
  const r = await apiClient.get<{ items: Exam[] }>("/exams", {
    params: { include_unpublished: includeUnpublished },
  });
  return r.data.items;
}

export async function createExam(payload: Record<string, unknown>): Promise<Exam> {
  const r = await apiClient.post<Exam>("/exams", payload);
  return r.data;
}

export async function updateExam(id: string, payload: Record<string, unknown>): Promise<Exam> {
  const r = await apiClient.patch<Exam>(`/exams/${id}`, payload);
  return r.data;
}

export async function deleteExam(id: string): Promise<void> {
  await apiClient.delete(`/exams/${id}`);
}

export async function fetchExamQuestions(examId: string): Promise<ExamQuestion[]> {
  const r = await apiClient.get<{ items: ExamQuestion[] }>(`/exams/${examId}/questions`);
  return r.data.items;
}

export async function createExamQuestion(
  examId: string,
  payload: Record<string, unknown>,
): Promise<ExamQuestion> {
  const r = await apiClient.post<ExamQuestion>(`/exams/${examId}/questions`, payload);
  return r.data;
}

export async function deleteExamQuestion(examId: string, questionId: string): Promise<void> {
  await apiClient.delete(`/exams/${examId}/questions/${questionId}`);
}

export async function fetchExamAttempts(examId: string): Promise<ExamAttempt[]> {
  const r = await apiClient.get<{ items: ExamAttempt[] }>(`/exams/${examId}/attempts`);
  return r.data.items;
}

// ---------------------------------------------------------------- B36 گواهی
export interface Certificate {
  id: string;
  certificate_number: string;
  user_id: string;
  course_id: string | null;
  exam_id: string | null;
  title: string;
  holder_name: string | null;
  revoked: boolean;
  revoked_at: string | null;
  revoke_reason: string | null;
  issued_at: string | null;
}

export async function fetchCertificates(params?: Record<string, unknown>): Promise<Certificate[]> {
  const r = await apiClient.get<{ items: Certificate[] }>("/certificates", { params });
  return r.data.items;
}

export async function issueCertificate(
  payload: Record<string, unknown>,
): Promise<{ certificate: Certificate; already_existed: boolean }> {
  const r = await apiClient.post("/certificates/issue", payload);
  return r.data;
}

export async function revokeCertificate(
  id: string,
  reason?: string,
): Promise<Certificate> {
  const r = await apiClient.post<Certificate>(`/certificates/${id}/revoke`, { reason: reason ?? null });
  return r.data;
}

export async function verifyCertificate(
  number: string,
): Promise<{ valid: boolean; certificate_number: string; title: string; holder_name: string | null; revoked: boolean }> {
  const r = await apiClient.get("/public/certificates/verify", { params: { number } });
  return r.data;
}
