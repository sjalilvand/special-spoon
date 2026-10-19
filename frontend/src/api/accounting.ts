// فاز ۳۱ - B22 سند جامع: کدینگ، سند حسابداری، تسویه، مغایرت و گزارش مالی
// قواعد سند: «سند متوازن و قابل ردیابی به رویداد مالی»
import { apiClient } from "./client";

/* ------------------------------ کدینگ (سرفصل‌ها) ------------------------------ */

export type AccountTypeCode = "asset" | "liability" | "equity" | "revenue" | "expense";

export const ACCOUNT_TYPE_LABEL: Record<string, string> = {
  asset: "دارایی",
  liability: "بدهی",
  equity: "حقوق مالکانه",
  revenue: "درآمد",
  expense: "هزینه",
};

export interface Account {
  id: string;
  code: string;
  name: string;
  type: AccountTypeCode;
  parent_id: string | null;
  description: string | null;
  is_active: boolean;
  is_system: boolean;
  created_at: string | null;
}

export async function fetchAccounts(includeInactive = true): Promise<Account[]> {
  return (
    await apiClient.get<{ items: Account[] }>("/accounts", { params: { include_inactive: includeInactive } })
  ).data.items;
}

export async function createAccount(payload: {
  code: string;
  name: string;
  type: AccountTypeCode;
  parent_id?: string | null;
  description?: string | null;
}): Promise<Account> {
  const r = await apiClient.post<Account>("/accounts", payload);
  return r.data;
}

export async function updateAccount(
  id: string,
  payload: { name?: string; description?: string | null; is_active?: boolean },
): Promise<Account> {
  const r = await apiClient.patch<Account>(`/accounts/${id}`, payload);
  return r.data;
}

/* ------------------------------ اسناد حسابداری ------------------------------ */

export interface JournalLine {
  id: string;
  account_id: string;
  account_code: string | null;
  account_name: string | null;
  debit: number;
  credit: number;
  description: string | null;
}

export interface JournalEntry {
  id: string;
  entry_no: string;
  entry_date: string | null;
  description: string;
  kind: string;
  source_type: "payment" | "refund" | "wallet_adjustment" | "settlement" | "manual" | "reversal";
  source_id: string | null;
  is_reversal: boolean;
  reversal_of_id: string | null;
  created_at: string | null;
  lines: JournalLine[];
}

export const SOURCE_LABEL: Record<string, string> = {
  payment: "پرداخت",
  refund: "استرداد",
  wallet_adjustment: "تعدیل کیف پول",
  settlement: "تسویه",
  manual: "دستی",
  reversal: "سند برگشتی",
};

export const KIND_LABEL: Record<string, string> = {
  payment_gateway: "پرداخت درگاه",
  payment_wallet: "پرداخت از کیف پول",
  payment_topup: "شارژ کیف پول (درگاه)",
  payment_topup_wallet: "شارژ کیف پول (اعتبار)",
  refund_wallet: "استرداد به کیف پول",
  refund_gateway: "استرداد درگاهی",
  wallet_adjustment: "تعدیل کیف پول",
  settlement: "تسویه دوره درگاه",
  manual: "سند دستی",
};

export interface EntryListFilters {
  source_type?: string;
  kind?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}

export async function fetchJournalEntries(filters?: EntryListFilters): Promise<JournalEntry[]> {
  return (await apiClient.get<{ items: JournalEntry[] }>("/journal-entries", { params: filters })).data.items;
}

export async function fetchJournalEntry(id: string): Promise<JournalEntry> {
  return (await apiClient.get<JournalEntry>(`/journal-entries/${id}`)).data;
}

export async function createManualEntry(payload: {
  description: string;
  entry_date?: string;
  lines: { account_id: string; debit: number; credit: number; description?: string }[];
}): Promise<JournalEntry> {
  const r = await apiClient.post<JournalEntry>("/journal-entries", payload);
  return r.data;
}

export async function reverseEntry(id: string, reason?: string): Promise<JournalEntry> {
  const r = await apiClient.post<JournalEntry>(`/journal-entries/${id}/reverse`, null, {
    params: reason ? { reason } : {},
  });
  return r.data;
}

export async function backfillJournalEntries(): Promise<{
  created: { payments: number; refunds: number; wallet_adjustments: number };
}> {
  const r = await apiClient.post("/journal-entries/backfill");
  return r.data;
}

/* ------------------------------ تسویه ------------------------------ */

export interface Settlement {
  id: string;
  settlement_no: string;
  gateway: string;
  period_start: string | null;
  period_end: string | null;
  payments_count: number;
  gross_amount: number;
  fee_amount: number | null;
  net_amount: number | null;
  currency: string;
  status: "draft" | "settled";
  journal_entry_id: string | null;
  journal_entry?: JournalEntry | null;
  note: string | null;
  settled_at: string | null;
  created_at: string | null;
  items?: { payment_id: string; amount: number }[];
}

export async function fetchSettlements(status?: string): Promise<Settlement[]> {
  return (
    await apiClient.get<{ items: Settlement[] }>("/settlements", { params: status ? { status } : {} })
  ).data.items;
}

export async function fetchSettlement(id: string): Promise<Settlement> {
  return (await apiClient.get<Settlement>(`/settlements/${id}`)).data;
}

export async function createSettlementDraft(payload: {
  gateway: "sandbox" | "zarinpal";
  period_start?: string | null;
  period_end?: string | null;
  note?: string | null;
}): Promise<Settlement> {
  const r = await apiClient.post<Settlement>("/settlements", payload);
  return r.data;
}

export async function settleSettlement(id: string, feeAmount: number): Promise<Settlement> {
  const r = await apiClient.post<Settlement>(`/settlements/${id}/settle`, { fee_amount: feeAmount });
  return r.data;
}

/* ------------------------------ گزارش مالی ------------------------------ */

export interface TrialBalanceRow {
  id: string;
  code: string;
  name: string;
  type: AccountTypeCode;
  debit: number;
  credit: number;
  raw_balance: number;
  balance: number;
  is_active: boolean;
}

export interface TrialBalance {
  items: TrialBalanceRow[];
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
}

export interface ReconciliationData {
  events: {
    payments: { total: number; journaled: number; uncovered: number; amount: number };
    refunds: { total: number; journaled: number; uncovered: number; amount: number };
    wallet_adjustments: { total: number; journaled: number; uncovered: number; amount: number };
  };
  ledger: { total_debit: number; total_credit: number; is_balanced: boolean };
  sales_reconciliation: {
    sales_report_amount: number;
    journal_revenue_amount: number;
    difference: number;
    reconciled: boolean;
  };
}

export async function fetchTrialBalance(): Promise<TrialBalance> {
  return (await apiClient.get<TrialBalance>("/reports/trial-balance")).data;
}

export async function fetchReconciliation(): Promise<ReconciliationData> {
  return (await apiClient.get<ReconciliationData>("/reports/financial-reconciliation")).data;
}
