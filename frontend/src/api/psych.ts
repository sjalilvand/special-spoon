// فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر (D08: ناظر علمی)
import { apiClient } from "./client";

export interface PsychTest {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  topic_id: string | null;
  topic_name: string | null;
  status: "draft" | "pending_review" | "published" | "rejected";
  review_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  question_count?: number;
  interpretation_count?: number;
  attempt_count?: number;
  created_at: string | null;
}

export interface PsychQuestion {
  id: string;
  test_id: string;
  prompt: string;
  options: { label: string; score: number }[];
  sort_order: number;
}

export interface PsychInterpretation {
  id: string;
  test_id: string;
  score_min: number;
  score_max: number;
  label: string;
  guidance: string | null;
  sort_order: number;
}

export interface PsychAttempt {
  id: string;
  test_id: string;
  user_id: string;
  score: number;
  interpretation_label: string;
  interpretation_guidance: string | null;
  test_title?: string | null;
  created_at: string | null;
}

export async function fetchPsychTests(): Promise<PsychTest[]> {
  const r = await apiClient.get<{ items: PsychTest[] }>("/psych-tests");
  return r.data.items;
}

export async function createPsychTest(payload: Record<string, unknown>): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>("/psych-tests", payload);
  return r.data;
}

export async function updatePsychTest(id: string, payload: Record<string, unknown>): Promise<PsychTest> {
  const r = await apiClient.patch<PsychTest>(`/psych-tests/${id}`, payload);
  return r.data;
}

export async function submitPsychTestForReview(id: string): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>(`/psych-tests/${id}/submit-review`, {});
  return r.data;
}

export async function reviewPsychTest(
  id: string,
  payload: { approve: boolean; note?: string },
): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>(`/psych-tests/${id}/review`, payload);
  return r.data;
}

export async function fetchPsychQuestions(testId: string): Promise<PsychQuestion[]> {
  const r = await apiClient.get<{ items: PsychQuestion[] }>(`/psych-tests/${testId}/questions`);
  return r.data.items;
}

export async function addPsychQuestion(
  testId: string,
  payload: { prompt: string; options: { label: string; score: number }[] },
): Promise<PsychQuestion> {
  const r = await apiClient.post<PsychQuestion>(`/psych-tests/${testId}/questions`, payload);
  return r.data;
}

export async function fetchInterpretations(testId: string): Promise<PsychInterpretation[]> {
  const r = await apiClient.get<{ items: PsychInterpretation[] }>(`/psych-tests/${testId}/interpretations`);
  return r.data.items;
}

export async function addInterpretation(
  testId: string,
  payload: { score_min: number; score_max: number; label: string; guidance?: string },
): Promise<PsychInterpretation> {
  const r = await apiClient.post<PsychInterpretation>(`/psych-tests/${testId}/interpretations`, payload);
  return r.data;
}

export async function fetchPsychAttempts(testId: string): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>(`/psych-tests/${testId}/attempts`);
  return r.data.items;
}

export async function fetchMyPsychResults(): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>("/my/psych-results");
  return r.data.items;
}
