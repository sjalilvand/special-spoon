import { apiClient } from "./client";

export interface SupervisedCaseRow {
  id: string;
  case_number: string;
  applicant_name: string;
  counselor_name: string | null;
  acceptance_date: string;
  status: string;
}

export async function fetchSupervisedCases(): Promise<{ items: SupervisedCaseRow[] }> {
  return (await apiClient.get("/worklists/supervised-cases")).data;
}
